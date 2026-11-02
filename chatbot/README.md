# BeLiving Coach – Chatbot Backend

AI wellness chatbot (nutrition, fitness, mindfulness, longevity) for the BeLiving app.
Built as a standalone API so the app UI can plug in later.

## Files
| File | What it does |
|---|---|
| `prompts.py` | The coach's personality (friend-style), scope, formatting and safety rules. Edit this to change answers. |
| `bot.py` | Calls the LLM (OpenAI GPT-5.6 Luna / Gemini / Claude) with streaming, retries and automatic backup provider. `stream_reply()` / `get_reply()` |
| `server.py` | API server with `POST /chat`, the endpoint the app calls |
| `test_5_messages.py` | Sends 5 test questions and prints answers |
| `chat_cli.py` | Chat with the bot in the terminal |

## Setup (Windows, once)
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
Copy `.env.example`, rename the copy to `.env`, and paste your API keys.

- **Testing (free):** set `LLM_PROVIDER=gemini` and add a free Gemini key from aistudio.google.com
- **Production:** `LLM_PROVIDER=openai` (GPT-5.6 Luna) with `LLM_FALLBACK_PROVIDER=gemini` as automatic backup

## Run
```
python test_5_messages.py        # quick 5-message test
python chat_cli.py               # chat in terminal
uvicorn server:app --reload      # start API -> open http://127.0.0.1:8000/docs
```

## For UI integration
`POST /chat`
```json
{
  "message": "give me a high protein veg breakfast",
  "profile": {"age": 24, "goal": "fat loss", "diet": "veg", "activity_level": "sedentary"},
  "history": [
    {"role": "user", "content": "previous question"},
    {"role": "assistant", "content": "previous answer"}
  ]
}
```
Response: `{"reply": "..."}`

**Recommended for the app:** `POST /chat/stream` (same body). It returns plain text streamed word-by-word, so the user sees the reply start in ~1-2s instead of waiting for the full answer. Replies are in markdown (bold, bullets), so render them as markdown in the UI.

- The app keeps the chat history and sends the last messages with each request (the server is stateless).
- The API key stays on the server only. Never put it inside the app.
- Switch models/providers only via `.env` (`LLM_PROVIDER`, `OPENAI_MODEL`, `GEMINI_MODEL`); no code changes needed.
- `.env` is never committed (see `.gitignore`). Keep API keys out of the repo.

## Before production
- Lock CORS in `server.py` to the app's domain
- Add user auth and per-user daily message limits
- Use a paid tier (the Gemini free tier may use data for training, so it's not OK for real user health data)
- Log conversations (with consent) to review answer quality
