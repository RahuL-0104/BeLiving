"""
BeLiving - Beat the Clock
Type a task you're avoiding -> get tiny steps to start it.

Run:  python beat_the_clock.py
"""
import json
import os
import re
import sys
import time
from pathlib import Path

from openai import OpenAI

# ---------------------------------------------------------------- settings
# Reads .env (or keys.env) from this folder
_here = Path(__file__).resolve().parent
for _env in (_here / ".env", _here / "keys.env"):
    if not _env.exists():
        continue
    for line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

PROVIDER = os.getenv("PROVIDER", "gemini").lower()


def _make(name):
    """Build one AI connection. Returns None if there's no key for it."""
    if name == "gemini" and os.getenv("GEMINI_API_KEY"):
        return {"name": "gemini",
                "client": OpenAI(api_key=os.getenv("GEMINI_API_KEY"), timeout=15, max_retries=0,
                                 base_url="https://generativelanguage.googleapis.com/v1beta/openai/"),
                "model": os.getenv("MODEL") or "gemini-3.1-flash-lite",
                # Gemini "thinks" before answering by default; task breakdown doesn't need it -> faster.
                "reasoning": os.getenv("REASONING_EFFORT", "low")}
    if name == "openai" and os.getenv("OPENAI_API_KEY"):
        return {"name": "openai",
                "client": OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=15, max_retries=0),
                "model": os.getenv("MODEL") or "gpt-4o-mini",
                "reasoning": os.getenv("REASONING_EFFORT", "")}
    if name == "groq" and os.getenv("GROQ_API_KEY"):
        return {"name": "groq",
                "client": OpenAI(api_key=os.getenv("GROQ_API_KEY"), timeout=15, max_retries=0,
                                 base_url="https://api.groq.com/openai/v1"),
                "model": os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile",
                "reasoning": ""}
    return None


if PROVIDER not in ("gemini", "openai"):
    sys.exit(f"PROVIDER must be 'gemini' or 'openai' in keys.env (got '{PROVIDER}')")

# Order to try: main AI first, then any backup that has a key.
AIS = [a for a in (_make(PROVIDER), _make("groq"), _make("openai" if PROVIDER == "gemini" else "gemini")) if a]
MODEL = AIS[0]["model"] if AIS else "none"

# ---------------------------------------------------------------- the prompt
SYSTEM_PROMPT = """You are the Beat the Clock coach in BeLiving, a wellness app for Indian users.
Your only job: help someone who is procrastinating START a task by breaking it into tiny steps.

Rules:
- Give 5 to 8 steps, in order.
- Every step starts with a concrete action verb: Open, Write, List, Find, Read, Pick, Send, Put, Set.
- Step size depends on stuck_level (1 = slightly stuck, 5 = totally frozen):
  - 1-2: each step 5 to 10 minutes
  - 3:   each step 3 to 7 minutes
  - 4-5: each step 1 to 3 minutes, and step 1 must be almost embarrassingly easy
- Step 1 is always the smallest possible way in (e.g. "Open a blank doc and type the title").
- Mark exactly ONE step as start_here: the easiest, lowest-friction step.
- Each step under 15 words. Simple English. No motivational fluff, no emojis.
- The user may write in Hinglish. Understand it, reply in simple English.
- If the task is too vague to break down (e.g. "life", "everything"), set vague=true and give no steps.
- If the task is harmful or illegal, set unsafe=true and give no steps.

Return ONLY JSON in exactly this shape:
{"vague": false, "unsafe": false, "steps": [{"text": "...", "minutes": 2, "start_here": true}]}
"""

MAX_MINUTES = {1: 10, 2: 10, 3: 7, 4: 3, 5: 3}


# ---------------------------------------------------------------- ready-made steps (last resort)
def _offline_steps(task: str, stuck_level: int) -> list:
    """Used only if every AI fails, so the user still gets useful steps instantly."""
    cap = MAX_MINUTES[stuck_level]
    short = task if len(task) <= 40 else task[:37].rstrip() + "..."
    texts = [
        f"Open whatever you need for: {short}",
        "Write one line: what does 'done' look like?",
        "List the 3 smallest parts of this task",
        "Pick the easiest part and do it badly, no editing",
        "Do the next part",
        "Read through once and fix just one thing",
    ]
    mins = [1, 2, 3, cap, cap, 3]
    return [{"id": i + 1, "text": t, "minutes": max(1, min(m, cap)), "start_here": i == 0}
            for i, (t, m) in enumerate(zip(texts, mins))]


def _warn(msg):
    print(f"\n  ⚠⚠  {msg}\n")


def _ask(ai: dict, task: str, stuck_level: int) -> dict:
    """One request to one AI. Returns the parsed JSON or raises."""
    request = dict(
        model=ai["model"],
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Task: {task[:500]}\nstuck_level: {stuck_level}"},
        ],
    )
    if ai["reasoning"]:
        request["reasoning_effort"] = ai["reasoning"]
    try:
        resp = ai["client"].chat.completions.create(**request)
    except Exception as e:
        # This model doesn't accept the thinking setting: drop it (and remember) and ask again.
        if ai["reasoning"] and type(e).__name__ == "BadRequestError" and "reasoning" in str(e).lower():
            ai["reasoning"] = ""
            request.pop("reasoning_effort", None)
            resp = ai["client"].chat.completions.create(**request)
        else:
            raise
    raw = resp.choices[0].message.content or ""
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE)
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])


def _clean(data: dict, stuck_level: int) -> list:
    cap = MAX_MINUTES[stuck_level]
    steps = []
    for s in data.get("steps", [])[:8]:
        text = str(s.get("text", "")).strip()
        if not text:
            continue
        try:
            mins = int(s.get("minutes", cap))
        except (TypeError, ValueError):
            mins = cap
        steps.append({"text": text, "minutes": max(1, min(mins, cap)), "start_here": bool(s.get("start_here"))})
    if len(steps) < 3:
        raise ValueError("AI returned too few steps")
    star = next((i for i, s in enumerate(steps) if s["start_here"]), 0)
    for i, s in enumerate(steps):
        s["start_here"] = i == star
        s["id"] = i + 1
    return [{"id": s["id"], "text": s["text"], "minutes": s["minutes"], "start_here": s["start_here"]} for s in steps]


# ---------------------------------------------------------------- core function
def break_down(task: str, stuck_level: int = 3) -> dict:
    """
    Always gives the user steps. Tries: main AI (2 tries) -> backup AI -> ready-made steps.

    Returns:
      {"ok": True, "steps": [{"id", "text", "minutes", "start_here"}], "total_minutes": int,
       "source": "gemini" | "openai" | "groq" | "offline"}
    or, only when the TASK itself needs changing (never because the AI failed):
      {"ok": False, "error": "TASK_TOO_VAGUE" | "TASK_NOT_SUPPORTED", "message": str}
    """
    task = (task or "").strip()
    try:
        stuck_level = max(1, min(5, int(stuck_level)))
    except (TypeError, ValueError):
        stuck_level = 3
    if len(task) < 3:
        return {"ok": False, "error": "TASK_TOO_VAGUE", "message": "Tell me a bit more about the task."}

    started = time.time()
    for ai in AIS:
        tries = 2 if ai is AIS[0] else 1
        for attempt in range(tries):
            try:
                data = _ask(ai, task, stuck_level)
                if data.get("unsafe"):
                    return {"ok": False, "error": "TASK_NOT_SUPPORTED",
                            "message": "This one isn't something we can help break down."}
                if data.get("vague"):
                    return {"ok": False, "error": "TASK_TOO_VAGUE",
                            "message": "Make it a bit more specific, like 'finish chapter 3 notes'."}
                steps = _clean(data, stuck_level)
                print(f"  ⏱  Broke down in {time.time() - started:.1f}s via {ai['name']} ({len(steps)} steps)")
                return {"ok": True, "steps": steps, "total_minutes": sum(s["minutes"] for s in steps),
                        "source": ai["name"]}
            except Exception as e:
                kind = type(e).__name__
                if kind in ("AuthenticationError", "PermissionDeniedError"):
                    _warn(f"{ai['name']}: API key isn't working. Fix it in keys.env.")
                    break  # retrying won't help, move to backup
                if kind == "NotFoundError":
                    _warn(f"{ai['name']}: model '{ai['model']}' not found. Change MODEL in keys.env.")
                    break
                print(f"  …  {ai['name']} attempt {attempt + 1} failed ({kind})")

    # Every AI failed (or no key at all): user still gets steps.
    if not AIS:
        _warn("No API key found in keys.env. Showing ready-made steps.")
    else:
        _warn("All AIs failed. Showing ready-made steps so the user isn't blocked.")
    steps = _offline_steps(task, stuck_level)
    return {"ok": True, "steps": steps, "total_minutes": sum(s["minutes"] for s in steps), "source": "offline"}


# ---------------------------------------------------------------- try it in the terminal
if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if not AIS:
        print("\n  ⚠  No key found in keys.env, so you'll get ready-made steps only.\n")
    print(f"\n  ⏱  Beat the Clock  ({' → '.join(a['name'] for a in AIS) or 'offline'})")
    print("  Type the task you're avoiding. Type 'exit' to quit.\n")

    while True:
        task = input("  What are you avoiding? > ").strip()
        if task.lower() in ("exit", "quit", "q"):
            break
        if not task:
            continue
        lvl = input("  How stuck? 1 (a little) to 5 (frozen) [Enter = 3] > ").strip()
        lvl = int(lvl) if lvl in ("1", "2", "3", "4", "5") else 3

        print("  Thinking...")
        result = break_down(task, lvl)

        if not result["ok"]:
            print(f"\n  ⚠  {result['message']}\n")
            continue

        print()
        for s in result["steps"]:
            mark = "⭐" if s["start_here"] else "  "
            print(f"  {mark} {s['id']}. {s['text']}  ({s['minutes']} min)")
        print(f"\n  Total: ~{result['total_minutes']} min.  Start with the ⭐ one.\n")
