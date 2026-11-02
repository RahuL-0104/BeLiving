"""Core pipeline: image -> preprocess -> vision model -> validate -> correct -> labels + macros.

Design choices (why this beats "just ask the LLM for calories"):
  * The model only does what vision models are good at: naming dishes and estimating grams.
  * Per-100g numbers come from food_db.json when the dish is known, so idli is always idli.
  * Model-supplied numbers are energy-checked (4P + 4C + 9F) and fixed when they don't add up.
  * Grams are clamped to sane bounds; low-confidence items are flagged for the user to confirm.
  * Same photo twice (double tap, retry) hits an in-memory cache instead of the paid API.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Union

from PIL import Image, ImageOps
from pydantic import ValidationError

from .prompt import SYSTEM_PROMPT, build_user_prompt
from .providers import VisionProvider, get_provider
from .schema import FoodLabel, FoodSize, LLMFoodItem, LLMResponse, Macros, MealResult

log = logging.getLogger("food_macros")

MAX_SIDE = int(os.getenv("FOOD_MAX_SIDE", "1024"))      # px; bigger = slower + costlier, not more accurate
CONFIRM_BELOW = float(os.getenv("FOOD_CONFIRM_BELOW", "0.6"))
MIN_GRAMS, MAX_GRAMS = 3.0, 1500.0
ENERGY_TOLERANCE = 0.25
RETRIES = int(os.getenv("FOOD_RETRIES", "4"))
DEADLINE_S = float(os.getenv("FOOD_DEADLINE_S", "60"))  # total time budget per photo, incl. retries
MAX_PIXELS = int(os.getenv("FOOD_MAX_PIXELS", str(50_000_000)))  # refuse decompression bombs
CACHE_SIZE = int(os.getenv("FOOD_CACHE_SIZE", "256"))
DB_PATH = Path(os.getenv("FOOD_DB_PATH", Path(__file__).with_name("food_db.json")))

ImageInput = Union[str, Path, bytes]


class AnalysisError(RuntimeError):
    """Base error. `code` is a stable machine-readable string for the app."""

    code = "ANALYSIS_FAILED"


class ImageError(AnalysisError):
    """The upload is not a usable image (user can fix it: retake / pick another photo)."""

    code = "BAD_IMAGE"


class ProviderUnavailable(AnalysisError):
    """The vision API is down, overloaded, out of quota or misconfigured (retry later)."""

    code = "PROVIDER_UNAVAILABLE"


Image.MAX_IMAGE_PIXELS = MAX_PIXELS
try:  # iPhone photos are HEIC; Flutter/RN pickers often hand them over unconverted
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:  # pragma: no cover
    HEIC_SUPPORTED = False


# ---------- food table ----------

def _norm(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def load_food_db(path: Path = DB_PATH) -> dict:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    index = {}
    for key, row in raw.items():
        if key.startswith("_"):
            continue
        values = {k: float(row[k]) for k in ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g")}
        if "serving_g" in row:
            values["_serving_g"] = float(row["serving_g"])
        if "piece_g" in row:
            values["_piece_g"] = float(row["piece_g"])
        index[_norm(key)] = (key, values)
        for alias in row.get("aliases", []):
            index.setdefault(_norm(alias), (key, values))
    return index


# ---------- image ----------

def prepare_image(data: bytes) -> tuple[bytes, str]:
    """Fix phone rotation, drop alpha, downscale, re-encode as JPEG. Never stores the photo."""
    try:
        with Image.open(io.BytesIO(data)) as src:
            if src.width * src.height > MAX_PIXELS:
                raise ImageError("Image is too large")
            img = ImageOps.exif_transpose(src)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((MAX_SIDE, MAX_SIDE))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
    except ImageError:
        raise
    except Image.DecompressionBombError as exc:
        raise ImageError("Image is too large") from exc
    except Exception as exc:  # noqa: BLE001  (truncated, corrupt, unsupported format)
        raise ImageError("Not a readable image. Use a JPG, PNG, WEBP or HEIC photo.") from exc
    return buf.getvalue(), "image/jpeg"


def _read(image: ImageInput) -> bytes:
    if isinstance(image, (bytes, bytearray)):
        return bytes(image)
    return Path(image).read_bytes()


# ---------- parsing & correction ----------

def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start : end + 1])


def _energy(p: float, c: float, f: float) -> float:
    return 4 * p + 4 * c + 9 * f


def _round(m: dict) -> Macros:
    return Macros(**{k: round(v, 1) for k, v in m.items()})


def _to_label(item: LLMFoodItem, db: dict, warnings: list[str]) -> FoodLabel:
    hit = db.get(_norm(item.canonical_key)) or db.get(_norm(item.name))
    db_serving = piece_g = None
    if hit:
        canonical, per100 = hit[0], dict(hit[1])
        db_serving = per100.pop("_serving_g", None)
        piece_g = per100.pop("_piece_g", None)
        source = "food_db"
    else:
        canonical = _norm(item.canonical_key) or _norm(item.name)
        per100 = item.per_100g.model_dump()
        source = "model"
        expected = _energy(per100["protein_g"], per100["carbs_g"], per100["fat_g"])
        if expected > 0 and abs(per100["kcal"] - expected) / expected > ENERGY_TOLERANCE:
            warnings.append(
                f"{item.name}: model kcal {per100['kcal']:.0f}/100g didn't match its macros, "
                f"recomputed to {expected:.0f}"
            )
            per100["kcal"] = expected

    # Portion: for countable foods, trust the COUNT from the photo and the WEIGHT from the table.
    # Vision models count well but guess weights badly (they under-weighed 2 naans as 90 g).
    pieces = item.pieces
    grams = item.estimated_grams
    if pieces and piece_g:
        grams = pieces * piece_g
    elif pieces and not piece_g:
        piece_g = grams / pieces
    if not MIN_GRAMS <= grams <= MAX_GRAMS:
        clamped = min(max(grams, MIN_GRAMS), MAX_GRAMS)
        warnings.append(f"{item.name}: portion {grams:.0f} g looked unrealistic, clamped to {clamped:.0f} g")
        grams = clamped

    serving = db_serving or item.typical_serving_g or grams
    servings = grams / serving
    category = "small" if servings < 0.75 else "large" if servings > 1.35 else "regular"
    ml = item.estimated_ml if item.estimated_ml and item.estimated_ml > 0 else None
    portion = item.portion_description or f"~{grams:.0f} g"
    size = FoodSize(
        grams=round(grams, 1),
        ml=round(ml) if ml else None,
        pieces=pieces,
        piece_g=round(piece_g, 1) if pieces and piece_g else None,
        description=portion,
        category=category,
        servings=round(servings, 2),
    )

    factor = grams / 100.0
    portion_macros = {k: v * factor for k, v in per100.items()}

    return FoodLabel(
        name=item.name.strip(),
        canonical_key=canonical,
        size=size,
        portion=portion,
        grams=round(grams, 1),
        macros=_round(portion_macros),
        per_100g=_round(per100),
        confidence=round(item.confidence, 2),
        needs_confirmation=item.confidence < CONFIRM_BELOW,
        macro_source=source,
        notes=item.notes,
    )


def _retry_wait(msg: str, attempt: int) -> float:
    """Honour the provider's 'retry in Ns' hint on rate limits (Gemini free tier = 5 req/min)."""
    m = re.search(r"retry in ([\d.]+)\s*s", msg, re.I) or re.search(r"retryDelay['\"]?:\s*['\"]?(\d+)", msg)
    if m:
        return min(float(m.group(1)) + 1, 65)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return 20.0
    return float(min(2 ** (attempt + 1), 15))  # 503 overloaded / network blips


# ---------- public API ----------

class FoodAnalyzer:
    def __init__(self, provider: Optional[VisionProvider] = None, use_food_db: bool = True):
        self.provider = provider or get_provider()
        self.db = load_food_db() if use_food_db else {}
        self._cache: "OrderedDict[str, MealResult]" = OrderedDict()
        self._lock = threading.Lock()  # the API serves several requests at once

    def analyze(self, image: ImageInput, hint: Optional[str] = None) -> MealResult:
        raw = _read(image)
        if not raw:
            raise ImageError("Empty image")

        key = hashlib.sha256(raw + (hint or "").encode()).hexdigest()
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None:
                self._cache.move_to_end(key)
                return hit.model_copy(update={"cached": True})

        img, mime = prepare_image(raw)
        started = time.perf_counter()
        parsed = self._call_with_retries(img, mime, build_user_prompt(hint))
        latency = int((time.perf_counter() - started) * 1000)

        warnings: list[str] = []
        items = []
        for raw_item in parsed.items if parsed.is_food else []:
            try:
                items.append(_to_label(LLMFoodItem.model_validate(raw_item), self.db, warnings))
            except ValidationError as exc:
                name = raw_item.get("name", "an item") if isinstance(raw_item, dict) else "an item"
                warnings.append(f"Skipped {name}: model returned unusable values")
                log.warning("skipped item %r: %s", raw_item, exc)
        if parsed.is_food and not items:
            warnings.append("Food detected but no items could be identified")
        if not parsed.is_food:
            warnings.append("No food detected in the image")

        totals = {k: sum(getattr(i.macros, k) for i in items) for k in Macros.model_fields}
        result = MealResult(
            is_food=parsed.is_food,
            items=items,
            totals=_round(totals),
            warnings=warnings,
            provider=self.provider.name,
            model=self.provider.model,
            latency_ms=latency,
        )

        with self._lock:
            self._cache[key] = result
            if len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        return result

    def _call_with_retries(self, img: bytes, mime: str, user_prompt: str) -> LLMResponse:
        last_err: Exception | None = None
        provider_failed = False
        prompt = user_prompt
        deadline = time.monotonic() + DEADLINE_S
        for attempt in range(RETRIES + 1):
            if attempt and time.monotonic() >= deadline:
                break
            try:
                text = self.provider.complete(img, mime, SYSTEM_PROMPT, prompt)
                return LLMResponse.model_validate(_extract_json(text))
            except (ValueError, ValidationError) as exc:  # bad JSON / bad shape: ask again, stricter
                last_err = exc
                prompt = user_prompt + "\nYour previous answer was not valid. Return ONLY the JSON object in the exact shape."
                log.warning("invalid model output (attempt %d): %s", attempt + 1, exc)
            except Exception as exc:  # network / rate limit / auth
                last_err = exc
                provider_failed = True
                msg = str(exc)
                if any(s in msg for s in ("404", "NOT_FOUND", "API key not valid", "PERMISSION_DENIED", "401", "403")):
                    break  # retrying won't fix a wrong model name or key
                wait = _retry_wait(msg, attempt)
                if attempt < RETRIES and time.monotonic() + wait < deadline:
                    log.warning("provider busy (attempt %d), retrying in %.0fs", attempt + 1, wait)
                    time.sleep(wait)
                else:
                    break
            else:
                provider_failed = False
        if provider_failed:
            raise ProviderUnavailable(f"Food recognition service is busy or unavailable: {str(last_err)[:300]}")
        raise AnalysisError(f"Model returned unusable output: {str(last_err)[:300]}")


_default: Optional[FoodAnalyzer] = None


def analyze_food_image(image: ImageInput, hint: Optional[str] = None) -> MealResult:
    """One-liner for the app: analyze_food_image('lunch.jpg') -> MealResult."""
    global _default
    if _default is None:
        _default = FoodAnalyzer()
    return _default.analyze(image, hint=hint)
