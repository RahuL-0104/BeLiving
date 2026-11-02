"""
BeLiving - Voice Journal
Voice note -> plain text (transcript) -> journal.

The journal covers:
  1) Food habits + cheat meals and guilt
  2) Fitness goals: achieved / unachieved
  3) Mental health: mood, handling emotions (able / partly / unable), triggers
  4) ADHD: focus, starting tasks, distractions, what helped

Try it in the terminal:
  python voice_journal.py                       type your day, get the journal
  python voice_journal.py my_voice_note.m4a     transcribe a voice note, then journal it
"""
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

from google import genai
from google.genai import errors, types

# ---------------------------------------------------------------- settings
# Reads keys.env from this folder. If the key isn't there, uses the chatbot's .env
# (Desktop\chatbot\.env), so both share the same Gemini key.
_here = Path(__file__).resolve().parent
for _env in (_here / "keys.env", _here / ".env", _here.parent / "chatbot" / ".env"):
    if not _env.exists():
        continue
    for line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            if v.strip() and "paste" not in v:
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
BACKUP_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.8-flash")
TIMEOUT_SECONDS = 45

AUDIO_TYPES = {".wav": "audio/wav", ".mp3": "audio/mp3", ".m4a": "audio/mp4", ".mp4": "audio/mp4",
               ".aac": "audio/aac", ".ogg": "audio/ogg", ".opus": "audio/ogg", ".webm": "audio/webm",
               ".flac": "audio/flac"}

# ---------------------------------------------------------------- the prompts
TRANSCRIBE_PROMPT = """Transcribe this voice note word for word.
- The speaker is from India and may mix English with Hindi or Kannada, and name Indian dishes
  (idli, dosa, ragi mudde, biryani, poha, chapati, dal, curd rice...). Spell dish names correctly.
- Write Hindi/Kannada words in English letters (Hinglish style).
- Remove filler sounds (um, uh) but keep every real word. Do not summarise.
- Output only the transcript text. If there is no speech, output nothing."""

JOURNAL_PROMPT = """You turn a spoken voice note from a user in India into their personal journal page for the
BeLiving wellness app.

Reply with ONLY this JSON shape:
{
  "title": "a short, warm title for the day, 3-6 words",
  "entry": "the journal entry, written AS the user in first person",
  "food": {
    "meals": [{"slot": "breakfast|lunch|snacks|dinner|other", "items": "what they ate"}],
    "cheat_meal": {"had_cheat_meal": false, "what": null, "guilt_0_to_5": null, "kind_note": null}
  },
  "fitness": {"goals": [{"goal": "Gym", "status": "achieved|not_achieved", "reason": null}]},
  "mind": {"mood_1_to_5": null, "mood_word": null, "emotions": [],
           "handled_emotions": "able|partly|unable|null", "triggers": []},
  "adhd": {"focus_1_to_5": null, "task_start": "easy|hard|null", "distractions": [], "what_helped": []},
  "reflection": "one short, kind line from BeLiving to the user",
  "needs_support": false
}

The entry (most important):
- Write it as the user's own diary: first person ("I", "my"), past tense, warm and natural, like a real
  journal page. 3 to 6 short sentences. Never use their name and never "he/she/they".
- Keep their feelings and their way of saying things. Tidy the grammar, but don't make it formal.
- Only what they said. Don't add events, feelings or lessons they didn't mention.

The rest:
- Use ONLY what they said. null, false or [] for anything not mentioned. Never invent anything.
- title: like a diary heading, e.g. "Cheese, fries and a lazy gym day". No names.
- meals: regular meals only. If something was the cheat meal, put it ONLY in cheat_meal, not in meals.
- cheat_meal: true only if they call something a cheat meal, treat, binge or indulgence, or felt guilty
  about food. guilt_0_to_5: their number if given, else judge from their words (0 = no guilt at all).
  kind_note: only if guilt is 2 or more: one warm line. NEVER mention calories, burning it off,
  compensating or skipping meals.
- Fitness: every planned activity they mention, achieved or not_achieved. goal: 1-4 words, capitalised.
  reason: only if they gave one, in a few words.
- mood_1_to_5: 1 awful, 2 low, 3 okay, 4 good, 5 great. mood_word: ONE word that matches that number.
- emotions: up to 4 single words they felt (e.g. happy, lazy, anxious). Don't repeat the mood word.
- handled_emotions: able = managed them, partly = struggled but recovered, unable = overwhelmed.
  null if they didn't talk about difficult feelings.
- triggers: 1-4 short labels for what set off difficult feelings, like Work stress, Poor sleep, Family,
  Relationship, Social media, Money, Loneliness, Comparison, Deadlines, Health worry. [] if none.
- adhd: only what they said about focus, starting tasks, distractions or what helped. If they say they
  were focused on something (even gaming), set focus_1_to_5. Never diagnose.
- reflection: second person ("you"), no name, 1 sentence, about something they actually said. No advice
  lists, no lecturing.
- needs_support: true ONLY if they mention wanting to hurt themselves, not wanting to live, or feeling unsafe.
- Write everything in English, even if they spoke Hinglish or Kannada.

Today's date: <<DATE>>
Voice note:
\"\"\"<<TEXT>>\"\"\""""


# ---------------------------------------------------------------- talking to Gemini
def _warn(msg):
    print(f"\n  ⚠⚠  {msg}\n")


def _gemini(contents, json_mode: bool) -> str:
    """Asks Gemini, with retries and a backup model. Never waits forever."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("No GEMINI_API_KEY found in keys.env or Desktop\\chatbot\\.env")
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000))

    last_error = None
    for model in dict.fromkeys([MODEL, BACKUP_MODEL]):
        config = types.GenerateContentConfig(
            temperature=0.2 if json_mode else 0,
            max_output_tokens=4000 if json_mode else 8000,
            response_mime_type="application/json" if json_mode else None,
            thinking_config=types.ThinkingConfig(thinking_level="low"),       # faster
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        for attempt in range(3):
            started = time.time()
            try:
                text = "".join(c.text or "" for c in
                               client.models.generate_content_stream(model=model, contents=contents, config=config))
                print(f"  ✓  {model} answered in {time.time() - started:.1f}s")
                if text.strip():
                    return text
                last_error = RuntimeError("Gemini returned an empty reply")
                break
            except errors.APIError as e:
                last_error = e
                if e.code in (401, 403):
                    _warn("Gemini API key isn't working. Check GEMINI_API_KEY.")
                    raise
                if e.code in (429, 500, 502, 503, 504):             # busy -> wait 1s, 2s, 4s
                    print(f"  …  {model} busy ({e.code}), retrying")
                    time.sleep(2 ** attempt)
                    continue
                if e.code == 400 and "thinking" in str(e).lower() and config.thinking_config:
                    config.thinking_config = None
                    continue
                print(f"  …  {model} error {e.code}, trying backup")
                break
            except Exception as e:                                    # timeout / network
                last_error = e
                print(f"  …  {model} failed after {time.time() - started:.0f}s ({type(e).__name__})")
                break
    raise last_error


# ---------------------------------------------------------------- step 1: voice -> text
def transcribe(audio: bytes, filename: str = "note.wav") -> str:
    """Voice note bytes -> plain text."""
    mime = AUDIO_TYPES.get(Path(filename).suffix.lower())
    if not mime:
        raise ValueError(f"Unsupported audio type. Use: {', '.join(AUDIO_TYPES)}")
    if len(audio) < 1000:
        raise ValueError("The recording is empty or too short.")
    text = _gemini([types.Part.from_bytes(data=audio, mime_type=mime), TRANSCRIBE_PROMPT], json_mode=False).strip()
    if not text:
        raise ValueError("No speech found in the recording. Try again a bit closer to the mic.")
    return text


# ---------------------------------------------------------------- step 2: text -> journal
def _num(v, lo, hi):
    try:
        return max(lo, min(hi, round(float(v))))
    except (TypeError, ValueError):
        return None


def _words(v):
    if not v:
        return []
    if isinstance(v, str):
        v = [v]
    return [str(x).strip() for x in v if str(x).strip()]


def _pick(v, allowed):
    v = str(v or "").lower().strip().replace(" ", "_")
    return v if v in allowed else None


def make_journal(text: str, day: str | None = None) -> dict:
    """Plain text -> journal dict (always the same shape, safe defaults for anything missing)."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Nothing to journal: the text is empty.")
    day = day or date.today().isoformat()

    raw = _gemini(JOURNAL_PROMPT.replace("<<DATE>>", day).replace("<<TEXT>>", text[:20000]), json_mode=True)
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE)
    d = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])

    food, cm = d.get("food") or {}, (d.get("food") or {}).get("cheat_meal") or {}
    mind, adhd = d.get("mind") or {}, d.get("adhd") or {}
    slots = ("breakfast", "lunch", "snacks", "dinner")
    handled = str(mind.get("handled_emotions") or "").lower()

    return {
        "date": day,
        "title": str(d.get("title") or d.get("summary") or "Today"),
        "entry": str(d.get("entry") or ""),
        "food": {
            "meals": [{"slot": _pick(m.get("slot"), slots) or "other", "items": str(m["items"])}
                      for m in food.get("meals") or [] if isinstance(m, dict) and m.get("items")],
            "cheat_meal": {
                "had_cheat_meal": bool(cm.get("had_cheat_meal")),
                "what": cm.get("what"),
                "guilt_0_to_5": _num(cm.get("guilt_0_to_5"), 0, 5),
                "kind_note": cm.get("kind_note"),
            },
        },
        "fitness": {"goals": [
            {"goal": str(g["goal"]),
             "status": "achieved" if str(g.get("status", "")).lower() in ("achieved", "hit", "done", "yes") else "not_achieved",
             "reason": g.get("reason")}
            for g in (d.get("fitness") or {}).get("goals") or [] if isinstance(g, dict) and g.get("goal")]},
        "mind": {
            "mood_1_to_5": _num(mind.get("mood_1_to_5"), 1, 5),
            "mood_word": mind.get("mood_word"),
            "emotions": _words(mind.get("emotions")),
            "handled_emotions": "able" if handled in ("able", "yes") else "partly" if handled.startswith("part")
                                else "unable" if handled in ("unable", "no") else None,
            "triggers": _words(mind.get("triggers")),
        },
        "adhd": {
            "focus_1_to_5": _num(adhd.get("focus_1_to_5"), 1, 5),
            "task_start": _pick(adhd.get("task_start"), ("easy", "hard")),
            "distractions": _words(adhd.get("distractions")),
            "what_helped": _words(adhd.get("what_helped")),
        },
        "reflection": str(d.get("reflection") or ""),
        "summary": str(d.get("title") or d.get("summary") or ""),          # short line for the past-journals list
        "needs_support": bool(d.get("needs_support")),
        "transcript": text,
    }


# ---------------------------------------------------------------- try it in the terminal
if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        print(f"\n  🎙  Transcribing {path.name}...")
        text = transcribe(path.read_bytes(), path.name)
    else:
        text = input("\n  📝  Tell me about your day (food, workout, mood, focus):\n  > ")

    print(f"\n  TRANSCRIPT\n  {text}\n\n  Writing your journal...")
    print(json.dumps(make_journal(text), indent=2, ensure_ascii=False))
