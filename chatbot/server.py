"""
API server your senior will connect the app UI to.

Run:   uvicorn server:app --reload
Docs:  http://127.0.0.1:8000/docs   (try requests right in the browser)

Endpoint: POST /chat
{
  "message": "give me a high protein veg breakfast",
  "profile": {"age": 24, "goal": "fat loss", "diet": "veg"},
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
}
-> {"reply": "..."}

Endpoint: POST /chat/stream  (same body)
-> plain text, streamed word-by-word as it is written (use this in the app for a fast feel)
"""

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from bot import get_reply, stream_reply, PROVIDER

app = FastAPI(title="BeLiving Coach API")

# Open for local dev. Lock this to the app's domain before going live.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Profile(BaseModel):
    name: str | None = None
    age: int | None = None
    gender: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    goal: str | None = None              # fat loss / muscle gain / energy / sleep ...
    diet: str | None = None              # veg / egg / non-veg / jain / vegan
    activity_level: str | None = None    # sedentary / light / active
    allergies: list[str] | None = None
    health_conditions: list[str] | None = None
    city: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    profile: Profile | None = None
    history: list[Turn] = []


class ChatResponse(BaseModel):
    reply: str


@app.get("/health")
def health():
    return {"status": "ok", "provider": PROVIDER}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        reply = get_reply(
            req.message,
            profile=req.profile.model_dump(exclude_none=True) if req.profile else None,
            history=[t.model_dump() for t in req.history],
        )
    except KeyError as e:
        raise HTTPException(500, f"Missing API key in .env: {e}")
    except Exception as e:
        raise HTTPException(502, f"LLM call failed: {e}")
    return ChatResponse(reply=reply)


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """Same as /chat but sends the answer piece by piece (feels instant in the app)."""
    gen = stream_reply(
        req.message,
        profile=req.profile.model_dump(exclude_none=True) if req.profile else None,
        history=[t.model_dump() for t in req.history],
    )

    def safe():
        try:
            yield from gen
        except Exception:
            yield "\n\nSorry, I'm having trouble right now. Please try again in a moment."

    return StreamingResponse(safe(), media_type="text/plain; charset=utf-8")
