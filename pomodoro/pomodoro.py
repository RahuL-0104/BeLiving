"""
BeLiving - Focus Lock (Pomodoro)
Pick a time (25 / 45 / 50 / 90 min or your own), the app locks you in, and you earn
leaves for every round you finish without leaving the app.

How the lock works
  - Leave the app and a 15 second countdown starts.
  - Come back in time = 1 slip. You get 2 slips per round.
  - A 3rd slip, or staying away longer than 15 s = the lock breaks, no leaves for that round.

Rewards (leaves)
  - Focus time:   1 leaf per minute  (x1.25 for 45-59 min, x1.5 for 60+ min)
  - Clean lock:   +10 if you never left the app
  - Task done:    +15 when you tick off the task you were working on (once per session)
  - Full set:     +20 for finishing every round of a 2+ round session
  - Daily streak: +5 per streak day (max +35) on your first finished round of the day
  Leaves grow your level (Seed -> Sprout -> Sapling -> Tree -> Forest) and unlock badges.

Try it in the terminal:  python pomodoro.py
"""
import json
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from threading import Lock

# ---------------------------------------------------------------- settings
DATA_FILE = Path(__file__).resolve().parent / "data" / "focus.json"

PRESETS = {25: 5, 45: 10, 50: 10, 90: 20}      # focus minutes -> break minutes
MIN_MINUTES, MAX_MINUTES = 5, 480          # 5 min to 8 hours
MAX_ROUNDS = 4
MAX_BREAKS = 3            # breaks the user can pick per lock (0-3)
BREAK_LEN = 5             # minutes per break; the lock timer pauses during a break
GRACE_SECONDS = 15        # how long you can be out of the app before the lock breaks
MAX_SLIPS = 2             # times you can leave (and come back in time) per round
EARLY_TOLERANCE = 10      # seconds; a round can't be finished earlier than this

LEVELS = [(0, "Seed", "🌰"), (150, "Sprout", "🌱"), (400, "Sapling", "🌿"),
          (900, "Tree", "🌳"), (2000, "Forest", "🌲")]

BADGES = {
    "first_lock":  ("🔒", "First Lock",   "Finish your first focus round"),
    "clean_3":     ("✨", "Untouchable",  "3 clean rounds in a row"),
    "deep_diver":  ("🌊", "Deep Diver",   "Finish a 50+ minute round"),
    "full_set":    ("🍅", "Full Set",     "Finish all 4 rounds in one session"),
    "streak_3":    ("🔥", "On Fire",      "3-day focus streak"),
    "streak_7":    ("⚡", "Unstoppable",  "7-day focus streak"),
    "ten_hours":   ("⏳", "10 Hour Club", "10 hours of total focus"),
    "task_slayer": ("🗡️", "Task Slayer", "Finish 10 tasks"),
}

_lock = Lock()


# ---------------------------------------------------------------- storage
def _load() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {}


def _save(data: dict):
    DATA_FILE.parent.mkdir(exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(DATA_FILE)


def _user(data: dict, user: str) -> dict:
    return data.setdefault(user, {
        "points": 0, "rounds_done": 0, "rounds_broken": 0, "focus_minutes": 0,
        "tasks_done": 0, "clean_run": 0, "streak": 0, "last_day": None,
        "badges": [], "history": [], "active": None,
    })


# ---------------------------------------------------------------- helpers
def _today() -> date:
    return date.today()


def break_minutes(minutes: int) -> int:
    if minutes in PRESETS:
        return PRESETS[minutes]
    return 5 if minutes < 40 else 10 if minutes < 75 else 20


def focus_points(minutes: int) -> int:
    mult = 1.5 if minutes >= 60 else 1.25 if minutes >= 45 else 1.0
    return int(minutes * mult + 0.5)          # rounds .5 up, same as the app screen


def level_of(points: int) -> dict:
    cur = LEVELS[0]
    for lv in LEVELS:
        if points >= lv[0]:
            cur = lv
    i = LEVELS.index(cur)
    nxt = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
    return {
        "name": cur[1], "emoji": cur[2], "number": i + 1,
        "next_name": nxt[1] if nxt else None,
        "next_at": nxt[0] if nxt else None,
        "to_next": (nxt[0] - points) if nxt else 0,
        "progress": 1.0 if not nxt else round((points - cur[0]) / (nxt[0] - cur[0]), 3),
    }


def _live_streak(u: dict) -> int:
    """Streak as the user sees it today (0 if they missed yesterday)."""
    if not u["last_day"]:
        return 0
    last = date.fromisoformat(u["last_day"])
    return u["streak"] if last >= _today() - timedelta(days=1) else 0


def _session_view(s: dict) -> dict:
    left = max(0, s["minutes"] * 60 - int(time.time() - s["round_started"]))
    return {k: s[k] for k in ("id", "task", "minutes", "break_minutes", "rounds", "round", "task_done", "breaks")} | {
        "break_len": BREAK_LEN,
        "seconds_left": left, "grace_seconds": GRACE_SECONDS, "max_slips": MAX_SLIPS,
        "points_if_finished": focus_points(s["minutes"]),
    }


# ---------------------------------------------------------------- core functions
def start(task: str, minutes: int = 25, rounds: int = 1, user: str = "me", breaks: int = 0) -> dict:
    """Start a locked focus session. Any session already running is counted as broken."""
    task = (task or "").strip()[:120] or "Deep focus"
    try:
        minutes, rounds = int(minutes), int(rounds)
    except (TypeError, ValueError):
        return {"ok": False, "error": "BAD_INPUT", "message": "Minutes and rounds must be numbers."}
    if not MIN_MINUTES <= minutes <= MAX_MINUTES:
        return {"ok": False, "error": "BAD_MINUTES",
                "message": f"Pick between {MIN_MINUTES} minutes and {MAX_MINUTES // 60} hours."}
    rounds = max(1, min(MAX_ROUNDS, rounds))
    try:
        breaks = max(0, min(MAX_BREAKS, int(breaks or 0)))
    except (TypeError, ValueError):
        breaks = 0

    with _lock:
        data = _load()
        u = _user(data, user)
        if u["active"]:
            _break(u, u["active"], "started_new")
        s = {"id": uuid.uuid4().hex[:12], "task": task, "minutes": minutes,
             "break_minutes": break_minutes(minutes), "rounds": rounds, "round": 1, "breaks": breaks,
             "round_started": time.time(), "task_done": False, "earned": 0}
        u["active"] = s
        _save(data)
    return {"ok": True, "session": _session_view(s)}


def finish_round(session_id: str, slips: int = 0, task_done: bool = False, user: str = "me",
                 breaks_used: int = 0) -> dict:
    """Timer hit zero. Checks the time really passed, then pays out the round's leaves."""
    with _lock:
        data = _load()
        u = _user(data, user)
        s = u["active"]
        if not s or s["id"] != session_id:
            return {"ok": False, "error": "NO_SESSION", "message": "This session isn't running any more."}

        elapsed = time.time() - s["round_started"]
        if elapsed < s["minutes"] * 60 - EARLY_TOLERANCE:
            return {"ok": False, "error": "TOO_EARLY",
                    "message": "The timer isn't done yet.",
                    "seconds_left": int(s["minutes"] * 60 - elapsed)}

        slips = max(0, int(slips or 0))
        breaks_used = max(0, int(breaks_used or 0))
        if breaks_used > s.get("breaks", 0):
            result = _break(u, s, "too_many_breaks")
            _save(data)
            return result
        if slips > MAX_SLIPS:
            result = _break(u, s, "too_many_slips")
            _save(data)
            return result

        # ---- rewards
        rows = [{"label": f"{s['minutes']} min focus", "points": focus_points(s["minutes"])}]
        if slips == 0:
            rows.append({"label": "Clean lock (never left)", "points": 10})
        if s.get("breaks", 0) and breaks_used == 0:
            rows.append({"label": "Skipped your breaks", "points": 5})
        if task_done and not s["task_done"]:
            s["task_done"] = True
            u["tasks_done"] += 1
            rows.append({"label": "Task done", "points": 15})
        last_round = s["round"] >= s["rounds"]
        if last_round and s["rounds"] > 1:
            rows.append({"label": f"Full set ({s['rounds']} rounds)", "points": 20})

        today = _today()
        last = date.fromisoformat(u["last_day"]) if u["last_day"] else None
        if last != today:
            u["streak"] = u["streak"] + 1 if last == today - timedelta(days=1) else 1
            u["last_day"] = today.isoformat()
            rows.append({"label": f"Day {u['streak']} streak", "points": min(u["streak"], 7) * 5})

        earned = sum(r["points"] for r in rows)
        level_before = level_of(u["points"])["number"]
        u["points"] += earned
        u["rounds_done"] += 1
        u["focus_minutes"] += s["minutes"]
        u["clean_run"] = u["clean_run"] + 1 if slips == 0 else 0
        s["earned"] += earned

        # ---- badges
        earned_now = {
            "first_lock": True,
            "clean_3": u["clean_run"] >= 3,
            "deep_diver": s["minutes"] >= 50,
            "full_set": last_round and s["rounds"] >= 4,
            "streak_3": u["streak"] >= 3,
            "streak_7": u["streak"] >= 7,
            "ten_hours": u["focus_minutes"] >= 600,
            "task_slayer": u["tasks_done"] >= 10,
        }
        new_badges = [k for k, ok in earned_now.items() if ok and k not in u["badges"]]
        u["badges"] += new_badges

        u["history"] = ([{"day": today.isoformat(), "task": s["task"], "minutes": s["minutes"],
                          "round": s["round"], "result": "done", "points": earned, "slips": slips, "breaks_used": breaks_used}]
                        + u["history"])[:50]

        if last_round:
            u["active"] = None
        else:
            s["round"] += 1
            s["round_started"] = None          # starts when the user taps "start next round"
        _save(data)

        lv = level_of(u["points"])
        return {
            "ok": True, "earned": earned, "breakdown": rows,
            "total_points": u["points"], "level": lv, "level_up": lv["number"] > level_before,
            "streak": u["streak"],
            "new_badges": [_badge(k, True) for k in new_badges],
            "session_done": last_round,
            "next": None if last_round else {"round": s["round"], "rounds": s["rounds"],
                                             "break_minutes": s["break_minutes"]},
        }


def next_round(session_id: str, user: str = "me") -> dict:
    """After the break: start the next round's timer."""
    with _lock:
        data = _load()
        u = _user(data, user)
        s = u["active"]
        if not s or s["id"] != session_id:
            return {"ok": False, "error": "NO_SESSION", "message": "This session isn't running any more."}
        s["round_started"] = time.time()
        _save(data)
    return {"ok": True, "session": _session_view(s)}


def give_up(session_id: str, reason: str = "quit", user: str = "me") -> dict:
    """The lock broke (left the app too long / too many slips) or the user quit."""
    with _lock:
        data = _load()
        u = _user(data, user)
        s = u["active"]
        if not s or s["id"] != session_id:
            return {"ok": False, "error": "NO_SESSION", "message": "This session isn't running any more."}
        result = _break(u, s, reason)
        _save(data)
    return result


def _break(u: dict, s: dict, reason: str) -> dict:
    focused = int(time.time() - s["round_started"]) // 60 if s.get("round_started") else 0
    focused = min(focused, s["minutes"])
    u["rounds_broken"] += 1
    u["clean_run"] = 0
    u["active"] = None
    u["history"] = ([{"day": _today().isoformat(), "task": s["task"], "minutes": s["minutes"],
                      "round": s["round"], "result": reason, "points": 0, "focused": focused}]
                    + u["history"])[:50]
    messages = {
        "left_app": "You left the app for too long, so the lock broke.",
        "too_many_slips": "You left the app 3 times, so the lock broke.",
        "too_many_breaks": "You took more breaks than you picked, so the lock broke.",
        "break_overrun": "You didn't come back after your break, so the lock broke.",
        "quit": "You ended the session early.",
        "started_new": "A new session was started.",
    }
    return {"ok": True, "broken": True, "reason": reason,
            "message": messages.get(reason, "The lock broke."),
            "focused_minutes": focused, "kept_points": s["earned"],
            "total_points": u["points"]}


def _badge(key: str, earned: bool) -> dict:
    emoji, name, how = BADGES[key]
    return {"id": key, "emoji": emoji, "name": name, "how": how, "earned": earned}


def stats(user: str = "me") -> dict:
    """Everything the home screen needs: leaves, level, streak, badges, today's focus."""
    with _lock:
        data = _load()
        u = _user(data, user)
        today = _today().isoformat()
        today_rows = [h for h in u["history"] if h["day"] == today and h["result"] == "done"]
        return {
            "points": u["points"], "level": level_of(u["points"]),
            "streak": _live_streak(u),
            "today": {"rounds": len(today_rows), "minutes": sum(h["minutes"] for h in today_rows)},
            "totals": {"rounds_done": u["rounds_done"], "rounds_broken": u["rounds_broken"],
                       "focus_minutes": u["focus_minutes"], "tasks_done": u["tasks_done"]},
            "badges": [_badge(k, k in u["badges"]) for k in BADGES],
            "history": u["history"][:10],
            "active": _session_view(u["active"]) if u["active"] and u["active"].get("round_started") else None,
            "presets": [{"minutes": m, "break_minutes": b, "points": focus_points(m)} for m, b in PRESETS.items()],
            "rules": {"grace_seconds": GRACE_SECONDS, "max_slips": MAX_SLIPS,
                      "min_minutes": MIN_MINUTES, "max_minutes": MAX_MINUTES, "max_rounds": MAX_ROUNDS,
                      "max_breaks": MAX_BREAKS, "break_len": BREAK_LEN},
        }


# ---------------------------------------------------------------- try it in the terminal
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    st = stats()
    lv = st["level"]
    print(f"\n  {lv['emoji']}  {lv['name']} · {st['points']} leaves · 🔥 {st['streak']}-day streak")
    print("  For the full lock screen run:  python app.py\n")
    task = input("  What are you working on? > ").strip()
    mins = input("  Minutes? 25 / 45 / 50 / 90 [Enter = 25] > ").strip() or "25"
    r = start(task, int(mins))
    if not r["ok"]:
        sys.exit(f"  ⚠  {r['message']}")
    s = r["session"]
    print(f"\n  🔒 Locked in for {s['minutes']} min. Ctrl + C to give up.\n")
    try:
        end = time.time() + s["minutes"] * 60
        while (left := int(end - time.time())) > 0:
            print(f"\r  ⏳ {left // 60:02d}:{left % 60:02d}  ", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n  🥀 " + give_up(s["id"], "quit")["message"] + "\n")
        sys.exit()
    done = input("\n\n  Time! Did you finish the task? (y/n) > ").strip().lower() == "y"
    res = finish_round(s["id"], 0, done)
    print(f"\n  🍃 +{res['earned']} leaves")
    for row in res["breakdown"]:
        print(f"     {row['label']:<28} +{row['points']}")
    for b in res["new_badges"]:
        print(f"  {b['emoji']}  New badge: {b['name']}")
    print(f"\n  {res['level']['emoji']} {res['level']['name']} · {res['total_points']} leaves\n")
