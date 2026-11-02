# BeLiving Food Scan

Meal photo in → every food item with its **label, portion size (g / ml / S-M-L / servings) and macros**, plus meal totals.
Built for Indian food. Uses a vision API now; your own EfficientNet + Grounding DINO pipeline can take over later
behind the same API.

**Integrating it into the app? Read [HANDOVER.md](HANDOVER.md).**

## Quick start (Windows)
1. Double-click **setup.bat**.
2. Open `.env` and paste your `GEMINI_API_KEY`.
3. Double-click **run.bat**. The browser opens a test page where you upload a meal photo. API docs are at `/api/docs`.

To try photos from the terminal, run **scan.bat** (or ▷ Run on `demo.py` in VS Code) and paste a photo path.

## Use it from Python
```python
from food_macros import analyze_food_image
meal = analyze_food_image("lunch.jpg", hint="home cooked")
for item in meal.items:
    print(item.name, item.size.grams, item.size.category, item.macros.kcal)
print(meal.totals)
```

## How it stays accurate
| Step | What it does |
|---|---|
| Preprocess | Fixes phone rotation, reads iPhone HEIC, resizes to a 1024 px JPEG (cheaper and faster, same accuracy) |
| Vision model | Names every item, including sides, and estimates grams from thali / katori / tumbler cues |
| Count-first portions | For naan, roti, idli, papad and the like, the model only counts pieces; the weight per piece comes from the table, because models count well but guess weight badly |
| `food_db.json` | 71 dishes with fixed per-100 g values, typical servings and piece weights, so idli is always idli |
| Energy check | For unknown dishes, kcal is recomputed if it isn't close to 4P + 4C + 9F |
| Guards | Grams are clamped to 3–1500 g, confidence under 0.6 sets `needs_confirmation`, and a broken item is skipped rather than failing the meal |
| Resilience | Retries with Google's wait hints, falls back to a backup model, has a 60 s total budget, and caches repeat photos |

## Tests
`test.bat` or `python -m pytest -q` (offline: uses a fake vision provider, no key needed).
