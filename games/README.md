# BeLiving · Mind Gym (brain games module)

Five 1-minute brain games in one shippable folder, in the BeLiving yellow & white theme.
Same setup as Beat the Clock: one `app.py`, open in VS Code and run.

| Game | What it trains | How it gets harder |
|---|---|---|
| **Mandala Rush** | Focus, visual memory | 60s. Random named sketch each round, match the reference colours. Finish one → next sketch (+5s). From sketch 3 the reference hides (peek = −3s). Calm mode = untimed colouring |
| **Pattern Recall** | Spatial memory | 60s. Perfect round = level up. Level 5+: purple decoy tiles. Level 8+: shorter flashes. Wrong tap = −3s |
| **Ivory** | Melody memory | 3 hearts, 3s per note, tempo speeds up, every 4th round is played backwards (2× points) |
| **Power Memory** | Working memory (digit span) | 3 hearts, answer timer, faster flashes, Mixed mode switches forward/backward (backward 1.5×) |
| **Snap Match** | Processing speed | 60s, 3 levels: 1-back → colour/rotation tricks (×2) → 2-back (×3) |

All five score in **points**, so they can sit on one leaderboard.

## Daily Challenge + leaderboard

- **Daily**: everyone gets the *same* puzzle today (seeded by date). Your **first** daily run counts for the leaderboard. Replays are saved as practice.
- **Practice**: new random puzzle every time. Never on the leaderboard.
- **Calm** (Mandala only): no timer, no score.
- Leaderboard screen: trophy icon on the home screen. Today / This week / All time, per game. Players set a display name.

## Run it

**Windows:** double-click `run.bat`
**Mac / Linux:** `python3 app.py` (the browser opens by itself)

If Windows blocks port 8090, the app picks a free port automatically and prints the link in the terminal.

No `pip install` needed. Python 3.9+ standard library only. No API key.

Tests: `python -m unittest discover tests` (9 tests)

## Folder

```
brain_games/
├── app.py                  ← server + score API (stdlib only)
├── run.bat                 ← double-click to run on Windows
├── static/
│   ├── index.html          ← hub screen ("Your Mind Gym")
│   ├── css/theme.css       ← ALL colours live in :root at the top
│   └── js/
│       ├── core.js         ← hub, sound, haptics, confetti, result sheet, scores
│       └── games/          ← one file per game, self-contained
│           ├── mandala.js
│           ├── pattern_recall.js
│           ├── ivory.js
│           ├── power_memory.js
│           └── speed_match.js
├── tests/test_app.py
└── data/brain_games.db     ← created on first run (SQLite)
```

## For the app team (integration)

**Open one game directly:** add the game id to the URL hash
`http://host:8090/#ivory` · `#mandala` · `#pattern_recall` · `#power_memory` · `#speed_match`
So a single tile in the app can open a WebView straight into one game.

**User id:** pass `?user=<id>` in the URL. It's sent as the `x-user-id` header to the API.

**Offline-safe:** if the API is unreachable, scores save to the phone (localStorage) and the games keep working.

**Sound:** generated live with Web Audio. No audio files, no licences to track.
**Haptics:** uses `navigator.vibrate` (Android). iOS ignores it silently.

### API

| Method | Path | Body / returns |
|---|---|---|
| GET | `/health` | `{ok, games}` |
| GET | `/api/scores` | `{best, plays_today, minutes_today, streak_days, daily_done, recent, name}` |
| POST | `/api/score` | body `{game, score, mode, level?, duration_s?, meta?}` → `{ok, best, is_best, plays_today, rank?, players?}` |
| POST | `/api/name` | body `{name}` (2–20 chars) → `{ok, name}` |
| GET | `/api/leaderboard?game=ivory&period=today` | `{top:[{rank,name,score,me}], me:{rank,score}, players}`. period = today / week / all. Daily runs only |

`game` must be one of the five ids. `mode` is `daily`, `practice` or `calm`. Bad input returns `422 {error}`. Scores above a per-game cap are rejected.

Env vars: `PORT` (default 8090), `BRAIN_GAMES_DB` (SQLite path), `CORS_ORIGIN` (default `*`, set it to the app's domain in production).

### Adding a 6th game

Copy any file in `static/js/games/`, change the `id`, add a `<script>` line in `index.html`, and add the id to `GAMES` and `MAX_SCORE` in `app.py`. Use `api.rng` (not `Math.random`) for puzzle content so Daily mode stays identical for everyone, and `BL.timer(api, 60, {el, onEnd})` for the clock. Each game calls `BL.register({...})` with `start(body, api)` and ends with `api.finish({score, ...})`. The hub card, intro screen, result sheet, confetti and score saving come for free.

### Changing the brand look

Everything is in the `:root` block at the top of `static/css/theme.css` (`--yellow`, `--bg`, `--ink`, etc).

## Before production

- **Leaderboard trust:** scores are calculated in the browser, so a determined user could fake one. For a public leaderboard, have the server replay the daily seed + the user's moves (the seed system is already in place) or keep the per-game score caps tight.

- Set `CORS_ORIGIN` to the real app domain.
- Swap the header `x-user-id` for your real auth token check (one function: `_user()` in `app.py`). Until then each device gets its own random id.
- SQLite is fine for a pilot. For scale, point the same two queries at Postgres.
- The font (Outfit) loads from Google Fonts. If the app already bundles a font, remove the `<link>` in `index.html`.

## Names

"Memorado" and "Speed Match" are other companies' product names, so the shipped names are **Pattern Recall** and **Snap Match**. Same mechanics, no trademark risk. Rename in each game file's `name:` field if you want.
