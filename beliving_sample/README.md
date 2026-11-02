# BeLiving · sample app

All BeLiving modules in one phone-style app, in the BeLiving Home design
(cream screen, navy tab bar, yellow highlights).

| Tab / card | Module folder | Port |
|---|---|---|
| Coach (chat screen built here) | `chatbot` | 8010 |
| Beat the Clock | `beat_the_clock` | 8000 |
| Journal | `voice_journal` | 8001 |
| Focus | `pomodoro` | 8002 |
| Calm | `box_breathing` | 8003 |
| Food (screen built here) | `food_macros` | 8006 |
| **This app (Home)** | `beliving_sample` | **8080** |

## Run it
Double-click **BeLiving App.bat** on the Desktop, or in this folder:
```
python app.py
```
It starts every module in the background and opens http://localhost:8080.
Keep the window open. **Ctrl + C** stops the app and all modules together.

- The module folders must stay on the Desktop next to `beliving_sample`.
- Each module still runs on its own exactly as before. Nothing inside them was changed.
- If a module is already running in another window, the app just uses it.
- A module with its own `venv` (like `chatbot`) is started with that venv's Python.
  The others use the Python you start this app with, so that Python needs their packages
  (`openai`, `google-genai`), the same as when you run them yourself.

## Home screen
- **Day streak** counts a day if you did any Box Breathing, Focus Lock or Journal that day.
- **Week dots** show which days this week you showed up.
- **Today's numbers**: calm minutes (Box Breathing), focus minutes (Focus Lock), journal entries (Voice Journal).
- **Your apps**: each card shows if the module is ready. Tap it to open it inside the phone.
  Modules stay open in the background, so a breathing or focus session keeps running when you switch tabs.

## Food tab
Snap or upload a meal photo. The Food Scan API finds every item with its portion and macros. Tap − / + to fix
a count or portion, ✕ to remove an item, or **Add something we missed** to pick from the food table. Then tap
**Log meal**. Today's meals and kcal show at the top of the tab (stored in this browser for the demo; the real
app saves them to the backend).
- Food Scan runs from `food_macros` with its own `.venv` (run `food_macros\setup.bat` once).
- Its key goes in `food_macros\.env` (`GEMINI_API_KEY`). Until you add one, the app reuses the Coach's key
  from `chatbot\.env` so it works straight away.

## If a module won't open
The app shows "didn't start" with the error and a **Try again** button.
The full error is in `beliving_sample\logs\<module>.log`. Usual causes:
- **Coach**: missing key in `chatbot\.env`, or its venv isn't set up (`pip install -r requirements.txt` inside the chatbot venv)
- **Beat the Clock / Journal**: missing key in their `keys.env`, or `openai` / `google-genai` not installed
- **Food Scan**: run `food_macros\setup.bat` once, and check the key (see Food tab above)
- **Port in use**: another program is using that port. Close it and tap Try again.

## For the senior / app team
- `app.py` starts the modules (`MODULES` list at the top: folder, port, start command) and serves the
  Home screen plus `GET /api/status`, `GET /api/summary` and `POST /api/restart/<module>`.
- `home.html` is the whole app screen. The Coach tab talks straight to the chatbot API (`POST /chat/stream`).
  The Food tab calls `/food/api/food/analyze` and `/food/api/food/dishes` on this app, which forwards them to the
  Food Scan API (same address for the page, so no CORS setup);
  see `food_macros\HANDOVER.md` for the contract.
- In the real mobile app, each module becomes a native screen calling the same Python functions or endpoints
  documented in each module's own README.
