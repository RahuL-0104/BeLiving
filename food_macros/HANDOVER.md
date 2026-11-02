# Hand-over: BeLiving Food Scan module

**Status: v1.0, ship-ready.** A reference screen for all of this is the Food tab in `beliving_sample/home.html`. 35 automated tests pass, and the module has been run live against Gemini on real thali and
biryani photos. The only thing left to set before launch is the production key (see §4).

---

## 1. How it fits together
```
 BeLiving app (Flutter / React Native / web)
   │  user takes or picks a meal photo
   │  POST /api/food/analyze  (multipart: image, optional hint)   Authorization: Bearer <JWT>
   ▼
 app.py → food_macros/api.py  (FastAPI)
   ├── POST /api/food/analyze   photo → items[] with label, size, macros + meal totals
   ├── GET  /api/food/limits    scans used / left today for the signed-in user
   ├── GET  /api/food/dishes    the food table, for the "+ add item" search
   ├── GET  /healthz
   └── GET  /api/docs           full OpenAPI schema
 food_macros/analyzer.py   resize (≤1024 px JPEG) → vision model → validate → fix → macros
 food_macros/providers.py  Gemini (main + backup model) or OpenAI, chosen by FOOD_PROVIDER
 food_macros/food_db.json  71 Indian dishes: per-100 g macros, typical serving, weight per piece (overrides model guesses)
```
Photos are processed in memory only. They are **never stored or logged**, which keeps the module out of
DPDP Act storage obligations for images. Logs carry a hashed user id, item count, kcal, model and latency.

## 2. Settings (`.env`; see `.env.example`)
| Variable | Production value |
|---|---|
| `GEMINI_API_KEY` | **Required.** A key from a Google Cloud project **with billing on**. The free tier allows 5 requests/min and the main model is often overloaded for free users. |
| `GEMINI_MODEL` / `GEMINI_FALLBACK_MODEL` | `gemini-3.8-flash` / `gemini-3.5-flash-lite`. If the main model is busy, the service switches to the backup for 5 minutes. |
| `FOOD_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL` | Only to use OpenAI instead. The model must accept images. |
| `AUTH_SECRET` | **Required.** The same HS256 secret the Meditation service uses. The user id is the JWT `sub`. |
| `ALLOW_ANON` | Leave empty. It turns off automatically once `AUTH_SECRET` is set, which also hides the test page. |
| `CORS_ORIGINS` | The app's web origin(s), only if a browser calls the API from another domain. |
| `FOOD_DAILY_LIMIT` | Scans per user per IST day (default 40). This is your cost cap. |

To use RS256 or a provider SDK (Firebase, Cognito, Clerk), change the one function `current_user()` in
`food_macros/api.py`.

## 3. The API contract
`POST /api/food/analyze`, multipart form: `image` (JPG / PNG / WEBP / **HEIC**, ≤10 MB), `hint` (optional, ≤300 chars,
e.g. "home cooked, less oil").

```jsonc
{
  "ok": true, "is_food": true,
  "items": [{
    "name": "Chicken Biryani", "canonical_key": "chicken_biryani",
    "size": { "grams": 350, "ml": null, "pieces": null, "piece_g": null,   // pieces set for naan, roti, idli, papad…
              "description": "1 plate of chicken biryani",
              "category": "regular",          // small | regular | large vs a normal serving
              "servings": 1.17 },
    "macros":   { "kcal": 609, "protein_g": 28, "carbs_g": 77, "fat_g": 21, "fiber_g": 3.5 },
    "per_100g": { "kcal": 174, "protein_g": 8,  "carbs_g": 22, "fat_g": 6,  "fiber_g": 1 },
    "confidence": 0.95, "needs_confirmation": false,
    "macro_source": "food_db",               // food_db = verified table, model = AI estimate
    "notes": ""
  }],
  "totals": { "kcal": 609, "protein_g": 28, "carbs_g": 77, "fat_g": 21, "fiber_g": 3.5 },
  "warnings": [], "provider": "gemini", "model": "gemini-3.5-flash-lite",
  "latency_ms": 8200, "cached": false, "disclaimer": "…"
}
```
Response header `X-Scans-Left` gives the scans the user has left today.

**Errors** always use the form `{"ok": false, "error": CODE, "message": "…"}`. Show `message` to the user.

| HTTP | `error` | App should |
|---|---|---|
| 400 | `EMPTY_FILE` | ask for the photo again |
| 401 | `UNAUTHORIZED` | refresh the token / sign in |
| 413 | `TOO_LARGE` | compress the photo (or resize to ~1600 px before upload, recommended anyway) |
| 415 | `NOT_AN_IMAGE` | ask for a photo |
| 422 | `BAD_IMAGE` | ask the user to retake / pick another photo |
| 422 | `ANALYSIS_FAILED` | "couldn't read this meal", offer manual entry |
| 429 | `DAILY_LIMIT` | show "limit reached, resets at midnight" |
| 503 | `PROVIDER_UNAVAILABLE`, `BUSY` | retry after the `Retry-After` header, or offer manual entry |
| 503 | `NOT_CONFIGURED` | server key missing (ops issue) |

A failed scan never counts against the user's daily limit.

### UI rules (important for trust)
1. **Always show a confirm screen before logging.** If `size.pieces` is set (naan, roti, idli, papad…), show
   −/+ on the count and use `grams = pieces × piece_g`. Otherwise show an editable grams field or an S/M/L chip.
   Recalculate locally as `per_100g × grams / 100`, with no second API call.
2. If `needs_confirmation` is true, ask "Is this *X*?" with a quick swap option.
3. Give the user a "+ add item" control backed by `GET /api/food/dishes`. Small sides (onion, lemon, pickle) are sometimes missed, especially on the backup model.
4. Use `size.category` for a simple S / M / L chip. Users fix size faster with chips than with grams.
5. Total time is typically 5–10 s on a paid key. Show a progress state and let the user cancel.

## 4. Before launch, the work that's left
| # | Item | Owner | Why |
|---|---|---|---|
| 1 | Put the production `GEMINI_API_KEY` (billing on) in the server's secret store. | Founder | The free tier caps at 5 scans/min and is overloaded. |
| 2 | Set `AUTH_SECRET` to match login. | App team | Stops anonymous use of a paid API. |
| 3 | With more than one server, move `DailyLimiter` to Redis (`INCR user:day` + `EXPIREAT`). | App team | The limit is per worker in memory. With N workers a user can get N × limit. |
| 4 | **Verify `food_db.json` against IFCT 2017 (NIN)** or a nutritionist. | Nutrition | The values are typical-preparation approximations. |
| 5 | Accuracy run: photograph 50 weighed meals and compare grams + kcal. | Founder | This gives you a real error number for marketing claims. |
| 6 | Log which `canonical_key`s come back with `macro_source: "model"` and add the top ones to `food_db.json`. | Ongoing | Each added dish makes its numbers consistent. |

## 5. Cost (₹, approx.; check current Gemini pricing before budgeting)
A 1024 px photo plus the prompt is roughly ₹0.05–0.15 per scan on Gemini Flash-class models. 10,000 scans ≈ ₹1,000.
Repeat uploads of the same photo are served from cache for free. The `FOOD_DAILY_LIMIT` of 40 caps the worst case
at about ₹6 per user per day.

## 6. Run, deploy, test
```
setup.bat            # once: venv + packages + .env
run.bat              # python app.py → http://localhost:8006 (test page) + /api/docs
scan.bat             # CLI: asks for photo paths, prints the breakdown (dev tool, demo.py)
test.bat             # 35 tests: pipeline, auth (valid/expired/forged/alg=none), limits, every error code,
                     #   HEIC, oversized images, a slow scan not blocking other requests

docker build -t beliving-food .
docker run -p 8006:8006 --env-file .env beliving-food
```
The Docker image runs as a non-root user, has a `/healthz` healthcheck, and never contains `.env`.
