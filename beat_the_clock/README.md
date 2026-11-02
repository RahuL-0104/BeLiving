# Beat the Clock · BeLiving

Type a task you're avoiding → get tiny steps to start it.

## Run it
1. Get a free Gemini key: https://aistudio.google.com/apikey
2. Paste it in `keys.env` after `GEMINI_API_KEY=` and save.
3. In the terminal:
   ```
   pip install -r requirements.txt
   python beat_the_clock.py
   ```

## Switch to OpenAI for launch
In `keys.env`: set `PROVIDER=openai`, paste `OPENAI_API_KEY=`, and optionally set `MODEL=`.

## For the senior / app team
Everything is in one function:

```python
from beat_the_clock import break_down

result = break_down("write my project report", stuck_level=4)   # stuck_level 1-5
```

Success:
```json
{"ok": true, "total_minutes": 11, "steps": [
  {"id": 1, "text": "Open a blank doc and type the title", "minutes": 1, "start_here": true},
  {"id": 2, "text": "List 3 points the report must cover", "minutes": 3, "start_here": false}
]}
```

It never fails because of the AI. Order it tries:
1. Main AI (Gemini), 2 attempts
2. Backup AI (Groq, if `GROQ_API_KEY` is in keys.env), 1 attempt
3. Ready-made steps built around the task, so the user is never blocked

`"source"` in the result says which one answered: `gemini`, `groq`, `openai` or `offline`.

It only returns `ok: false` when the *task* needs changing:
```json
{"ok": false, "error": "TASK_TOO_VAGUE" | "TASK_NOT_SUPPORTED", "message": "show this to the user"}
```

Guarantees: 3–8 steps, exactly one `start_here`, minutes capped by stuck level
(1–2 → max 10, 3 → max 7, 4–5 → max 3). Problems like a bad key are printed loudly in the
server terminal, never shown to users.

Keep `keys.env` private. Never upload it to GitHub.
