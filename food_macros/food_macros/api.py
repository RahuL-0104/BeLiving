"""BeLiving Food Scan service: photo in -> food labels, portion size and macros out.

Run locally:   python app.py                 -> http://localhost:8006 (test page) and /api/docs
Production:    uvicorn app:app --host 0.0.0.0 --port 8006 --workers 2
               (or: docker build -t beliving-food . && docker run -p 8006:8006 --env-file .env beliving-food)

Endpoints
  POST /api/food/analyze   multipart: image=<file>, hint=<optional text>  -> MealResult JSON
  GET  /api/food/limits    the caller's scans used / left today
  GET  /api/food/dishes    the food table (for a manual "+ add item" search)
  GET  /healthz            liveness (no external calls)
  GET  /api/docs           OpenAPI docs
  GET  /                   test page (only when ALLOW_ANON is on, i.e. dev)

Settings: see .env.example. Auth works exactly like the Meditation service (HS256 JWT, `sub` = user id).
Photos are processed in memory and never stored or logged.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import __version__
from .analyzer import DB_PATH, AnalysisError, FoodAnalyzer, ImageError, ProviderUnavailable
from .providers import ProviderError
from .schema import MealResult

log = logging.getLogger("food_macros.api")

AUTH_SECRET = os.environ.get("AUTH_SECRET", "")
ALLOW_ANON = os.environ.get("ALLOW_ANON", "0" if AUTH_SECRET else "1") == "1"
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
MAX_UPLOAD_MB = float(os.environ.get("FOOD_MAX_UPLOAD_MB", "10"))
DAILY_LIMIT = int(os.environ.get("FOOD_DAILY_LIMIT", "40"))  # scans per user per day (0 = unlimited)
MAX_CONCURRENT = int(os.environ.get("FOOD_MAX_CONCURRENT", "8"))  # vision calls in flight per worker
IST = timezone(timedelta(hours=5, minutes=30))
STATIC = Path(__file__).with_name("static")

app = FastAPI(title="BeLiving Food Scan", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=1024)
if CORS_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST"],
                       allow_headers=["Authorization", "Content-Type", "X-User-Id"])


@app.middleware("http")
async def no_store(request: Request, call_next):
    res = await call_next(request)
    if request.url.path.startswith("/api/"):
        res.headers["Cache-Control"] = "no-store"
    return res


# ---------------------------------------------------------------- errors
class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, headers: Optional[dict] = None):
        super().__init__(message)
        self.status, self.code, self.message, self.headers = status, code, message, headers or {}


@app.exception_handler(ApiError)
async def _api_error(request, exc: ApiError):
    return JSONResponse({"ok": False, "error": exc.code, "message": exc.message},
                        status_code=exc.status, headers=exc.headers)


# ---------------------------------------------------------------- auth (same as Meditation)
def _b64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify_jwt(token: str, secret: str) -> dict:
    """Minimal HS256 JWT check: signature, exp and nbf. Returns the claims."""
    def fail(msg):
        raise ApiError(401, "UNAUTHORIZED", msg)

    try:
        head, body, sig = token.split(".")
        header = json.loads(_b64(head))
        claims = json.loads(_b64(body))
        good = hmac.new(secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest()
        signature_ok = hmac.compare_digest(good, _b64(sig))
    except Exception:  # noqa: BLE001
        fail("Malformed token")
    if header.get("alg") != "HS256":
        fail("Unsupported token")
    if not signature_ok:
        fail("Bad signature")
    now = time.time()
    if "exp" in claims and now > float(claims["exp"]):
        fail("Token expired")
    if "nbf" in claims and now < float(claims["nbf"]):
        fail("Token not yet valid")
    if not claims.get("sub"):
        fail("Token has no sub")
    return claims


def current_user(request: Request) -> str:
    """Swap this one function if your login uses RS256 / Firebase / Cognito / Clerk."""
    auth = request.headers.get("authorization", "")
    if AUTH_SECRET and auth.lower().startswith("bearer "):
        return str(verify_jwt(auth[7:].strip(), AUTH_SECRET)["sub"])
    if ALLOW_ANON:
        return request.headers.get("x-user-id") or "anon"
    raise ApiError(401, "UNAUTHORIZED", "Sign in required")


# ---------------------------------------------------------------- daily scan limit (cost control)
class DailyLimiter:
    """Scans per user per IST day. In-memory per worker process: with N workers a user can get up to
    N x limit. Swap for Redis (INCR + EXPIREAT) when you run more than one server."""

    def __init__(self, limit: int):
        self.limit = limit
        self._lock = threading.Lock()
        self._day = ""
        self._counts: dict[str, int] = {}

    def _today(self) -> str:
        day = datetime.now(IST).strftime("%Y-%m-%d")
        if day != self._day:
            self._day, self._counts = day, {}
        return day

    def take(self, user: str) -> int:
        """Use one scan. Returns scans left. Raises 429 when the user is out."""
        if self.limit <= 0:
            return -1
        with self._lock:
            self._today()
            used = self._counts.get(user, 0)
            if used >= self.limit:
                raise ApiError(429, "DAILY_LIMIT", f"Daily limit of {self.limit} scans reached. Resets at midnight IST.")
            self._counts[user] = used + 1
            return self.limit - used - 1

    def give_back(self, user: str) -> None:
        """Failed scans (our fault or the provider's) don't count against the user."""
        with self._lock:
            if self._counts.get(user):
                self._counts[user] -= 1

    def status(self, user: str) -> dict:
        with self._lock:
            day = self._today()
            used = self._counts.get(user, 0)
        return {"day": day, "used": used, "limit": self.limit or None,
                "left": None if self.limit <= 0 else max(self.limit - used, 0)}


limiter = DailyLimiter(DAILY_LIMIT)
_slots = threading.BoundedSemaphore(MAX_CONCURRENT)

# ---------------------------------------------------------------- analyzer (created on first use)
_analyzer: Optional[FoodAnalyzer] = None
_analyzer_lock = threading.Lock()


def get_analyzer() -> FoodAnalyzer:
    global _analyzer
    if _analyzer is None:
        with _analyzer_lock:
            if _analyzer is None:
                try:
                    _analyzer = FoodAnalyzer()
                except ProviderError as exc:
                    log.error("food scan not configured: %s", exc)
                    raise ApiError(503, "NOT_CONFIGURED", "Food scan is not configured on the server") from exc
    return _analyzer


def _analyze_blocking(data: bytes, hint: Optional[str]) -> MealResult:
    """Runs in a worker thread so one slow photo never blocks other requests."""
    if not _slots.acquire(timeout=30):
        raise ApiError(503, "BUSY", "Too many scans in progress, please retry", {"Retry-After": "5"})
    try:
        return get_analyzer().analyze(data, hint=hint)
    finally:
        _slots.release()


# ---------------------------------------------------------------- API
@app.post("/api/food/analyze", response_model=MealResult, responses={
    400: {"description": "EMPTY_FILE"}, 401: {"description": "UNAUTHORIZED"}, 413: {"description": "TOO_LARGE"},
    415: {"description": "NOT_AN_IMAGE"}, 422: {"description": "BAD_IMAGE / ANALYSIS_FAILED"},
    429: {"description": "DAILY_LIMIT"}, 503: {"description": "PROVIDER_UNAVAILABLE / BUSY / NOT_CONFIGURED"}})
async def analyze(request: Request, image: UploadFile = File(...), hint: Optional[str] = Form(None)):
    """Upload one meal photo. Returns every food item with its size and macros, plus meal totals."""
    user = current_user(request)
    ctype = (image.content_type or "").lower()
    if ctype and not (ctype.startswith("image/") or ctype == "application/octet-stream"):
        raise ApiError(415, "NOT_AN_IMAGE", "Upload a photo (JPG, PNG, WEBP or HEIC)")
    data = await image.read(int(MAX_UPLOAD_MB * 1024 * 1024) + 1)
    if not data:
        raise ApiError(400, "EMPTY_FILE", "The uploaded file is empty")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise ApiError(413, "TOO_LARGE", f"Photo is larger than {MAX_UPLOAD_MB:g} MB")
    if hint is not None:
        hint = hint.strip()[:300] or None

    left = limiter.take(user)
    started = time.perf_counter()
    try:
        result = await run_in_threadpool(_analyze_blocking, data, hint)
    except ImageError as exc:
        limiter.give_back(user)
        raise ApiError(422, exc.code, str(exc)) from exc
    except ProviderUnavailable as exc:
        limiter.give_back(user)
        log.warning("provider unavailable: %s", exc)
        raise ApiError(503, exc.code, "Food recognition is busy right now, please try again in a minute",
                       {"Retry-After": "30"}) from exc
    except AnalysisError as exc:
        limiter.give_back(user)
        log.warning("analysis failed: %s", exc)
        raise ApiError(422, exc.code, "Couldn't read this meal, please try another photo") from exc
    except ApiError:
        limiter.give_back(user)
        raise

    log.info("scan user=%s items=%d kcal=%.0f model=%s cached=%s ms=%d",
             hashlib.sha256(user.encode()).hexdigest()[:10], len(result.items), result.totals.kcal,
             result.model, result.cached, int((time.perf_counter() - started) * 1000))
    headers = {} if left < 0 else {"X-Scans-Left": str(left)}
    return JSONResponse(result.model_dump(mode="json"), headers=headers)


@app.get("/api/food/limits")
def limits(request: Request):
    """How many scans the signed-in user has left today."""
    return {"ok": True, **limiter.status(current_user(request))}


_dishes_cache: Optional[list] = None


@app.get("/api/food/dishes")
def dishes():
    """Every dish in the food table, for the app's "+ add item" search. Same numbers the scanner uses."""
    global _dishes_cache
    if _dishes_cache is None:
        raw = json.loads(DB_PATH.read_text(encoding="utf-8"))
        _dishes_cache = sorted((
            {"key": k, "name": k.replace("_", " ").title(), "aliases": [a.replace("_", " ") for a in v.get("aliases", [])],
             "per_100g": {m: v[m] for m in ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g")},
             "serving_g": v.get("serving_g"), "piece_g": v.get("piece_g")}
            for k, v in raw.items() if not k.startswith("_")), key=lambda d: d["name"])
    return {"ok": True, "dishes": _dishes_cache}


@app.get("/healthz")
def healthz():
    return {"ok": True, "version": __version__}


# Old path from v0 kept so nothing breaks; use /api/food/analyze.
app.add_api_route("/v1/food/analyze", analyze, methods=["POST"], include_in_schema=False)


@app.get("/", include_in_schema=False)
def home():
    if not ALLOW_ANON:
        raise ApiError(404, "NOT_FOUND", "Not found")
    return FileResponse(STATIC / "index.html")
