# Voice Journal · BeLiving

Record your voice → see the transcript → get your journal.

The journal covers:
1. **Food habits**: meals, cheat meal and how guilty you felt (0–5)
2. **Fitness goals**: achieved / unachieved, and why
3. **Mental health**: mood, handling emotions (able / partly / unable), triggers
4. **ADHD**: focus, starting tasks, distractions, what helped

## Run it
1. Double-click **setup.bat** (first time only)
2. Double-click **run.bat** → the journal opens in your browser
3. Tap the mic, talk about your day, tap again to stop → **Make my journal** → **Save**

The API key: uses the Gemini key from `Desktop\chatbot\.env`. Nothing to set up.
Saved journals go in the `entries` folder.

## For the senior / app team
Everything is in two functions:

```python
from voice_journal import transcribe, make_journal

text = transcribe(audio_bytes, "note.m4a")    # voice note -> plain text
journal = make_journal(text)                   # plain text -> journal
```

`make_journal` always returns the same shape:
```json
{"date": "2026-10-07", "summary": "...",
 "food": {"meals": [{"slot": "breakfast", "items": "poha"}],
          "cheat_meal": {"had_cheat_meal": true, "what": "biryani", "guilt_0_to_5": 3, "kind_note": "..."}},
 "fitness": {"goals": [{"goal": "8,000 steps", "status": "not_achieved", "reason": "desk all day"}]},
 "mind": {"mood_1_to_5": 3, "mood_word": "okay", "emotions": ["low"], "handled_emotions": "partly",
          "triggers": ["Work stress"]},
 "adhd": {"focus_1_to_5": 2, "task_start": "hard", "distractions": ["Instagram"], "what_helped": ["timer"]},
 "reflection": "...", "needs_support": false, "transcript": "..."}
```
If `needs_support` is true, show a support card (Tele-MANAS: 14416, free, 24x7).

Keep `keys.env` private. Never upload it to GitHub.
