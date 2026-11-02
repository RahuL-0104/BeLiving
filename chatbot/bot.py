"""
Core chatbot logic.
  stream_reply()  -> yields the answer piece by piece as it's written (fast feel)
  get_reply()     -> returns the full answer at once

Providers: openai (GPT-5.6 Luna), gemini, claude.
Set LLM_PROVIDER (main) and LLM_FALLBACK_PROVIDER (backup) in the .env file.
If the main provider is down or busy, the backup answers automatically.
"""

import os
import time
from typing import Iterator

from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT, build_profile_block

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
FALLBACK_PROVIDER = os.getenv("LLM_FALLBACK_PROVIDER", "gemini").lower()
MAX_HISTORY_TURNS = 10        # how many past messages to send (keeps cost low)
MAX_OUTPUT_TOKENS = 3000      # caps answer length (and cost); room for full plans
RETRY_CODES = (429, 500, 502, 503, 504)

KEY_NAMES = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY", "claude": "ANTHROPIC_API_KEY"}


def _system_text(profile: dict | None) -> str:
    return SYSTEM_PROMPT + "\n\n" + build_profile_block(profile)


def _trim(history: list[dict] | None) -> list[dict]:
    """history = [{"role": "user"|"assistant", "content": "..."}]"""
    return (history or [])[-MAX_HISTORY_TURNS:]


def _has_key(provider: str) -> bool:
    key = os.getenv(KEY_NAMES.get(provider, ""), "")
    return bool(key) and "paste" not in key


# ---------- OpenAI (GPT-5.6 Luna) ----------
def _openai_stream(message: str, profile, history) -> Iterator[str]:
    import openai

    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=3)
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

    messages = [{"role": "system", "content": _system_text(profile)}]
    messages += [{"role": t["role"], "content": t["content"]} for t in _trim(history)]
    messages.append({"role": "user", "content": message})

    kwargs = dict(model=model, messages=messages, stream=True,
                  max_completion_tokens=MAX_OUTPUT_TOKENS,
                  reasoning_effort="low")          # faster + cheaper for chat
    try:
        stream = client.chat.completions.create(**kwargs)
    except openai.BadRequestError as e:
        if "reasoning" not in str(e).lower():
            raise
        kwargs.pop("reasoning_effort")             # model doesn't support it
        stream = client.chat.completions.create(**kwargs)

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# ---------- Gemini ----------
def _gemini_stream(message: str, profile, history) -> Iterator[str]:
    from google import genai
    from google.genai import errors, types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    primary = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    backup = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.8-flash")

    contents = []
    for turn in _trim(history):
        role = "model" if turn["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

    config = types.GenerateContentConfig(
        system_instruction=_system_text(profile),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=0.85,                 # higher = more natural, varied replies
        thinking_config=types.ThinkingConfig(thinking_level="low"),  # faster + cheaper
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    last_error = None
    for model in dict.fromkeys([primary, backup]):     # main model, then backup model
        for attempt in range(3):
            started = False
            try:
                for chunk in client.models.generate_content_stream(
                    model=model, contents=contents, config=config
                ):
                    if chunk.text:
                        started = True
                        yield chunk.text
                return
            except errors.APIError as e:
                if started:
                    raise
                last_error = e
                if e.code in RETRY_CODES:                  # busy -> wait 1s, 2s, 4s and retry
                    time.sleep(2 ** attempt)
                    continue
                if e.code == 400 and "thinking" in str(e).lower():
                    config.thinking_config = None
                    continue
                break                                      # other error -> try backup model
    raise last_error


# ---------- Claude ----------
def _claude_stream(message: str, profile, history) -> Iterator[str]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=3)
    model = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")

    messages = [{"role": t["role"], "content": t["content"]} for t in _trim(history)]
    messages.append({"role": "user", "content": message})

    with client.messages.stream(
        model=model,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=[{"type": "text", "text": _system_text(profile),
                 "cache_control": {"type": "ephemeral"}}],
        messages=messages,
    ) as stream:
        yield from stream.text_stream


STREAMERS = {"openai": _openai_stream, "gemini": _gemini_stream, "claude": _claude_stream}


# ---------- Public functions ----------
def stream_reply(message: str, profile: dict | None = None,
                 history: list[dict] | None = None) -> Iterator[str]:
    """Yields the answer piece by piece. Uses the backup provider if the main one fails."""
    if not message or not message.strip():
        yield "Ask me anything about food, workouts, sleep or stress."
        return

    order = [p for p in dict.fromkeys([PROVIDER, FALLBACK_PROVIDER]) if p in STREAMERS]
    usable = [p for p in order if _has_key(p)]
    if not usable:
        raise RuntimeError(f"No API key found in .env for: {', '.join(order)}")

    written = ""            # what the user has already seen
    last_error = None
    for round_no in range(3):                     # up to 3 rounds through main + backup
        for provider in usable:
            if written:
                # The answer broke halfway -> ask the model to carry on from that point.
                msg = ("Your previous reply got cut off. Continue EXACTLY from where it "
                       "stopped. Do not repeat anything already written, no intro.")
                hist = (history or []) + [{"role": "user", "content": message},
                                          {"role": "assistant", "content": written}]
            else:
                msg, hist = message, history
            try:
                for piece in STREAMERS[provider](msg, profile, hist):
                    written += piece
                    yield piece
                return
            except Exception as e:
                last_error = e                    # try the next provider / round
        time.sleep(2 * (round_no + 1))            # give the servers a breather
    raise last_error


def get_reply(message: str, profile: dict | None = None,
              history: list[dict] | None = None) -> str:
    """Returns the full answer at once."""
    return "".join(stream_reply(message, profile, history)).strip()
