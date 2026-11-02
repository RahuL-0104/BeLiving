"""Vision providers. Swap with one env var: FOOD_PROVIDER=gemini | openai.

Each provider takes image bytes + prompts and returns the raw JSON text.
Validation happens in analyzer.py, so providers stay dumb and swappable.
"""
from __future__ import annotations

import base64
import logging
import os
import time
from abc import ABC, abstractmethod


log = logging.getLogger("food_macros")


class ProviderError(RuntimeError):
    pass


class VisionProvider(ABC):
    name: str = "base"

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def complete(self, image: bytes, mime: str, system: str, user: str) -> str: ...


class GeminiProvider(VisionProvider):
    name = "gemini"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        super().__init__(model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))
        backup = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
        self.models = list(dict.fromkeys(m for m in (self.model, backup) if m))
        self._prefer_backup_until = 0.0
        from google import genai

        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ProviderError("GEMINI_API_KEY is not set")
        from google.genai import types

        timeout_ms = int(float(os.getenv("FOOD_TIMEOUT_S", "25")) * 1000)
        self._client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=timeout_ms))

    def complete(self, image: bytes, mime: str, system: str, user: str) -> str:
        """Try the main model, then the backup (same pattern as the BeLiving chatbot)."""
        from google.genai import types

        last: Exception | None = None
        order = self.models
        if time.monotonic() < self._prefer_backup_until and len(order) > 1:
            order = order[1:] + order[:1]  # main model was overloaded recently: go straight to backup
        for model in order:
            try:
                resp = self._client.models.generate_content(
                    model=model,
                    contents=[types.Part.from_bytes(data=image, mime_type=mime), user],
                    config=self._config(types, system, model),
                )
                if not resp.text:
                    raise ProviderError(f"{model} returned an empty response")
                self.model = model  # report the model that actually answered
                return resp.text
            except Exception as exc:  # timeout / busy / quota / retired model -> try backup
                log.warning("%s failed (%s), trying backup model", model, str(exc)[:120])
                if model == self.models[0]:
                    self._prefer_backup_until = time.monotonic() + 300  # skip it for 5 minutes
                last = exc
        raise last  # type: ignore[misc]

    def _config(self, types, system: str, model: str):
        cfg = dict(system_instruction=system, response_mime_type="application/json")
        if model.startswith("gemini-2"):
            cfg["temperature"] = 0.2
        else:
            # Gemini 3.x: keep default temperature (low values can cause looping) and use
            # low thinking so a photo comes back in seconds, not a minute.
            cfg["thinking_config"] = types.ThinkingConfig(thinking_level="low")
        return types.GenerateContentConfig(**cfg)


class OpenAIProvider(VisionProvider):
    name = "openai"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        model = model or os.getenv("OPENAI_MODEL")
        if not model:
            raise ProviderError("OPENAI_MODEL is not set (put your deployment model id in .env)")
        super().__init__(model)
        from openai import OpenAI

        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ProviderError("OPENAI_API_KEY is not set")
        self._client = OpenAI(api_key=key, timeout=float(os.getenv("FOOD_TIMEOUT_S", "25")))

    def complete(self, image: bytes, mime: str, system: str, user: str) -> str:
        b64 = base64.b64encode(image).decode()
        resp = self._client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                },
            ],
        )
        text = resp.choices[0].message.content
        if not text:
            raise ProviderError("OpenAI returned an empty response")
        return text


def get_provider(name: str | None = None) -> VisionProvider:
    name = (name or os.getenv("FOOD_PROVIDER", "gemini")).lower()
    if name == "gemini":
        return GeminiProvider()
    if name == "openai":
        return OpenAIProvider()
    raise ProviderError(f"Unknown provider '{name}'. Use gemini or openai.")
