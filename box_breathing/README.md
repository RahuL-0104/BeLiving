# Box Breathing · BeLiving

Breathe in, hold, breathe out, hold. Four equal sides, guided by a calm voice over soft ocean waves.
The box fills with yellow as you breathe in and drains as you breathe out.

## Run it
1. Double-click **setup.bat** (first time only)
2. Double-click **run.bat**. Box Breathing opens in your browser at http://localhost:8003
3. Pick seconds per side (3 / 4 / 5 / 6) and a length (1 / 3 / 5 min or Open), then tap **Begin**

No API key needed, and nothing to install besides Python. Progress is saved in the `data` folder.

## How a session runs
1. A slow voice: *"Sit comfortably, and relax your shoulders. Let your breath settle."*
2. A short pause, then a silent on-screen countdown: **3, 2, 1** (1.5 s each)
3. Box after box, one word per side: **Inhale, Hold, Exhale, Hold**
4. At the end: *"Well done. Let your breath return to normal."*

Soft ocean waves play underneath the whole time. Voice and ocean have separate volume sliders.

## Audio
All voice clips are in `audio/` (WAV, 22 kHz mono), already levelled to a calm volume (about -21 LUFS):

| File | Says | Length |
|---|---|---|
| `intro.wav` | Sit comfortably, and relax your shoulders. Let your breath settle. | 6.1 s |
| `inhale.wav` | Inhale | 1.1 s |
| `hold.wav` | Hold | 0.9 s |
| `exhale.wav` | Exhale | 0.8 s |
| `outro.wav` | Well done. Let your breath return to normal. | 2.3 s |

The ocean is generated live in the browser, so there's no file for it.
These are AI-generated placeholder voices. For launch, record a real teacher saying the same
lines (English, Hindi, Kannada) and drop the files in with the same names.

### Timing rules (important for the mobile app)
- Schedule every sound on the **audio clock**, not with timers, and draw the animation from that
  same clock. That's what keeps voice and visuals in sync with no lag.
- Play each word **60 ms before** its corner (`voice_lead` in the plan). The ear hears a word's beat
  slightly after its first sound, so this makes it land exactly on the corner.
- Pause = suspend the audio clock, so sound and animation freeze together.

## For the senior / app team
All settings and the session rules live in `box_breathing.py`.

```python
import box_breathing

p = box_breathing.plan(pace=4, minutes=3)
# -> {"ok": true, "pace": 4, "minutes": 3, "boxes": 11, "seconds": 176, "breaths_per_min": 3.75,
#     "phases": [{"key": "inhale", "label": "Breathe in", "voice": "Inhale", "audio": "audio/inhale.wav", "seconds": 4}, ...],
#     "voice_lead": 0.06,
#     "intro": {"audio": "audio/intro.wav", "text": "...", "pause_after": 0.8, "countdown": [3, 2, 1], "countdown_step": 1.5},
#     "outro": {"audio": "audio/outro.wav", "text": "..."}, "background": "ocean"}
#    minutes=0 -> open session, "boxes": null
#    bad input -> {"ok": false, "error": "BAD_PACE" | "BAD_LENGTH" | "BAD_INPUT", "message": "..."}

box_breathing.record(seconds=176, boxes=11, pace=4, completed=True, user="user_123")
# -> {"ok": true, "saved": true, "stats": {...}}   (under 20 s -> "saved": false, "reason": "TOO_SHORT")

box_breathing.stats(user="user_123")
# -> {"minutes_today": 3, "sessions": 12, "total_minutes": 41, "streak": 4, "last": {...}}
```

HTTP endpoints in `app.py` (same shapes): `GET /api/plan?pace=4&minutes=3`, `GET /api/stats`,
`POST /api/session` with `{"seconds", "boxes", "pace", "completed"}`, and `GET /audio/<name>.wav`.

Terminal demo (2 boxes): `python box_breathing.py`

`data/` holds personal progress. Keep it out of GitHub (already in `.gitignore`).
