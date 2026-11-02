# BeLiving

AI-powered behavioral wellness app for India: nutrition, fitness and mindfulness in one place.

| Folder | What it is | Port |
|---|---|---|
| `beliving_sample` | **The main app.** Phone-style Home screen that starts and combines every module below, including the new Food / calorie tracker tab | 8080 |
| `food_macros` | Food Scan API: photo of a meal -> items, portions, macros (powers the Food tab) | 8006 |
| `chatbot` | Coach: AI wellness chatbot | 8010 |
| `beat_the_clock` | Beat the Clock | 8000 |
| `voice_journal` | Voice Journal: speak -> text -> journal entry | 8001 |
| `pomodoro` | Focus Lock (Pomodoro) | 8002 |
| `box_breathing` | Calm: guided box breathing | 8003 |
| `games` | Mind Gym brain games (mandala, Ivory, Power Memory, Pattern Recall, Speed Match) | see its README |

## Run
Double-click **BeLiving App.bat**, or:
```
cd beliving_sample
python app.py
```
Then open http://localhost:8080. Each module also runs on its own; see the README inside its folder.

## API keys
Keys are **not** in this repo. Copy the example file in each module and add your own key:
- `chatbot/.env.example` -> `chatbot/.env`
- `food_macros/.env.example` -> `food_macros/.env`
- `beat_the_clock/keys.env.example` -> `beat_the_clock/keys.env`
- `voice_journal/keys.env.example` -> `voice_journal/keys.env`
