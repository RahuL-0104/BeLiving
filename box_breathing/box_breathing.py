"""
BeLiving - Box Breathing
Breathe in, hold, breathe out, hold. Four equal sides, guided by a calm voice
over soft ocean waves.

How a session runs
  1. A slow voice says "Sit comfortably, and relax your shoulders. Let your breath settle."
  2. A short pause, then a silent on-screen countdown: 3, 2, 1 (1.5 s each).
  3. Box after box: "Inhale", "Hold", "Exhale", "Hold", one word per side.
  4. "Well done. Let your breath return to normal."

Everything the app needs (timings, audio files, wording) comes from plan().
Finished sessions are saved with record(), and the home screen reads stats().

Try it in the terminal:  python box_breathing.py
"""
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Lock

# ---------------------------------------------------------------- settings
HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / "data" / "breathing.json"
AUDIO_DIR = HERE / "audio"

PACES = (3, 4, 5, 6)          # seconds per side
DEFAULT_PACE = 4
LENGTHS = (1, 3, 5, 0)        # session minutes; 0 = open (no end, user stops it)
DEFAULT_LENGTH = 3
INTRO_PAUSE = 0.8             # seconds of quiet after the intro voice
COUNTDOWN = (3, 2, 1)         # shown on screen only, no voice
COUNTDOWN_STEP = 1.5          # seconds per countdown number
VOICE_LEAD = 0.06             # play each word this early so it lands on the corner
MIN_SECONDS_TO_SAVE = 20      # shorter sessions are not counted
KEEP_SESSIONS = 500           # per user

INTRO_TEXT = "Sit comfortably, and relax your shoulders. Let your breath settle."
OUTRO_TEXT = "Well done. Let your breath return to normal."

PHASES = [
    {"key": "inhale",      "label": "Breathe in",  "voice": "Inhale", "audio": "audio/inhale.wav"},
    {"key": "hold_top",    "label": "Hold",        "voice": "Hold",   "audio": "audio/hold.wav"},
    {"key": "exhale",      "label": "Breathe out", "voice": "Exhale", "audio": "audio/exhale.wav"},
    {"key": "hold_bottom", "label": "Hold",        "voice": "Hold",   "audio": "audio/hold.wav"},
]

_lock = Lock()


# ---------------------------------------------------------------- session plan
def plan(pace=DEFAULT_PACE, minutes=DEFAULT_LENGTH):
    """Everything the screen needs to run one session."""
    try:
        pace, minutes = int(pace), int(minutes)
    except (TypeError, ValueError):
        return {"ok": False, "error": "BAD_INPUT", "message": "Pace and minutes must be numbers."}
    if pace not in PACES:
        return {"ok": False, "error": "BAD_PACE", "message": f"Pace must be one of {list(PACES)} seconds."}
    if minutes not in LENGTHS:
        return {"ok": False, "error": "BAD_LENGTH", "message": f"Length must be one of {list(LENGTHS)} minutes (0 = open)."}

    box_seconds = 4 * pace
    boxes = max(1, round(minutes * 60 / box_seconds)) if minutes else None
    return {
        "ok": True,
        "pace": pace,
        "minutes": minutes,
        "boxes": boxes,                                   # None = open session
        "seconds": boxes * box_seconds if boxes else None,
        "breaths_per_min": round(60 / box_seconds, 2),
        "phases": [dict(p, seconds=pace) for p in PHASES],
        "voice_lead": VOICE_LEAD,
        "intro": {"audio": "audio/intro.wav", "text": INTRO_TEXT, "pause_after": INTRO_PAUSE,
                  "countdown": list(COUNTDOWN), "countdown_step": COUNTDOWN_STEP},
        "outro": {"audio": "audio/outro.wav", "text": OUTRO_TEXT},
        "background": "ocean",
    }


# ---------------------------------------------------------------- storage
def _load():
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"users": {}}


def _save(db):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(db, indent=1), encoding="utf-8")
    tmp.replace(DATA_FILE)


def _streak(days):
    n, d = 0, date.today()
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def _stats_from(sessions):
    today = date.today().isoformat()
    days = {s["date"] for s in sessions}
    return {
        "minutes_today": round(sum(s["seconds"] for s in sessions if s["date"] == today) / 60),
        "sessions": len(sessions),
        "total_minutes": round(sum(s["seconds"] for s in sessions) / 60),
        "streak": _streak(days),
        "last": sessions[-1] if sessions else None,
    }


# ---------------------------------------------------------------- public API
def record(seconds, boxes=0, pace=DEFAULT_PACE, completed=False, user="me"):
    """Save a session the user just did (finished or ended early)."""
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return {"ok": False, "error": "BAD_INPUT", "message": "Seconds must be a number."}
    if seconds < MIN_SECONDS_TO_SAVE:
        return {"ok": True, "saved": False, "reason": "TOO_SHORT", "stats": stats(user)}
    with _lock:
        db = _load()
        sessions = db["users"].setdefault(str(user), {"sessions": []})["sessions"]
        sessions.append({
            "date": date.today().isoformat(),
            "at": datetime.now().isoformat(timespec="seconds"),
            "seconds": round(min(seconds, 6 * 3600)),
            "boxes": int(boxes or 0),
            "pace": int(pace),
            "completed": bool(completed),
        })
        del sessions[:-KEEP_SESSIONS]
        _save(db)
        return {"ok": True, "saved": True, "stats": _stats_from(sessions)}


def stats(user="me"):
    """Home screen numbers: minutes today, sessions, day streak."""
    db = _load()
    return _stats_from(db["users"].get(str(user), {}).get("sessions", []))


# ---------------------------------------------------------------- terminal demo
if __name__ == "__main__":
    p = plan(4, 1)
    print(f"\n  Box breathing: {p['pace']}s a side, {p['boxes']} boxes, {p['breaths_per_min']} breaths/min\n")
    print(f"  {INTRO_TEXT}\n")
    time.sleep(2)
    for n in COUNTDOWN:
        print(f"  Starting in {n}")
        time.sleep(COUNTDOWN_STEP)
    start = time.time()
    try:
        for b in range(2):
            for ph in p["phases"]:
                for s in range(1, p["pace"] + 1):
                    print(f"\r  Box {b + 1}  {ph['label']:<12} {s}", end="", flush=True)
                    time.sleep(1)
        print(f"\n\n  {OUTRO_TEXT}")
    except KeyboardInterrupt:
        print("\n  Stopped.")
    r = record(time.time() - start, 2, 4, True)
    print("  Saved:", r["saved"], "| today:", r["stats"]["minutes_today"], "min | streak:", r["stats"]["streak"])
