"""HTTP service tests: auth, limits, error codes, concurrency. Offline (fake vision provider)."""
import base64
import hashlib
import hmac
import io
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from food_macros import FoodAnalyzer, api
from food_macros.analyzer import ProviderUnavailable
from test_analyzer import BREAKFAST, FakeProvider, make_image

SECRET = "test-secret"


def jwt(claims, secret=SECRET, alg="HS256"):
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
    head, body = enc({"alg": alg, "typ": "JWT"}), enc(claims)
    sig = hmac.new(secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest()
    return f"{head}.{body}." + base64.urlsafe_b64encode(sig).rstrip(b"=").decode()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "_analyzer", FoodAnalyzer(provider=FakeProvider([BREAKFAST])))
    monkeypatch.setattr(api, "limiter", api.DailyLimiter(40))
    monkeypatch.setattr(api, "AUTH_SECRET", "")
    monkeypatch.setattr(api, "ALLOW_ANON", True)
    return TestClient(api.app)


def post(client, data=None, headers=None, name="meal.png", ctype="image/png"):
    return client.post("/api/food/analyze", files={"image": (name, data if data is not None else make_image(), ctype)},
                       headers=headers or {})


def test_happy_path_contract(client):
    res = post(client)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True and body["is_food"] is True and len(body["items"]) == 3
    item = body["items"][0]
    for key in ("name", "canonical_key", "size", "macros", "per_100g", "confidence", "needs_confirmation"):
        assert key in item
    assert set(item["size"]) == {"grams", "ml", "pieces", "piece_g", "description", "category", "servings"}
    assert res.headers["X-Scans-Left"] == "39"
    assert res.headers["Cache-Control"] == "no-store"


def test_error_codes(client):
    assert post(client, data=b"").json()["error"] == "EMPTY_FILE"
    r = post(client, data=b"hello", name="x.txt", ctype="text/plain")
    assert (r.status_code, r.json()["error"]) == (415, "NOT_AN_IMAGE")
    r = post(client, data=b"definitely not a jpeg")
    assert (r.status_code, r.json()["error"]) == (422, "BAD_IMAGE")


def test_too_large(client, monkeypatch):
    monkeypatch.setattr(api, "MAX_UPLOAD_MB", 0.001)
    r = post(client)
    assert (r.status_code, r.json()["error"]) == (413, "TOO_LARGE")


def test_provider_down_is_503_and_not_charged(client, monkeypatch):
    class Down:
        def analyze(self, *a, **k):
            raise ProviderUnavailable("503 overloaded")

    monkeypatch.setattr(api, "_analyzer", Down())
    r = post(client, headers={"X-User-Id": "u1"})
    assert (r.status_code, r.json()["error"]) == (503, "PROVIDER_UNAVAILABLE")
    assert r.headers["Retry-After"] == "30"
    assert client.get("/api/food/limits", headers={"X-User-Id": "u1"}).json()["used"] == 0


def test_daily_limit(client, monkeypatch):
    monkeypatch.setattr(api, "limiter", api.DailyLimiter(2))
    h = {"X-User-Id": "u2"}
    assert post(client, headers=h).status_code == 200
    assert post(client, headers=h).status_code == 200
    r = post(client, headers=h)
    assert (r.status_code, r.json()["error"]) == (429, "DAILY_LIMIT")
    assert post(client, headers={"X-User-Id": "someone-else"}).status_code == 200
    assert client.get("/api/food/limits", headers=h).json() == {
        "ok": True, "day": api.limiter.status("u2")["day"], "used": 2, "limit": 2, "left": 0}


def test_auth_required_in_production(client, monkeypatch):
    monkeypatch.setattr(api, "AUTH_SECRET", SECRET)
    monkeypatch.setattr(api, "ALLOW_ANON", False)
    assert post(client).status_code == 401
    assert post(client, headers={"X-User-Id": "spoof"}).status_code == 401
    good = {"Authorization": "Bearer " + jwt({"sub": "user-42", "exp": time.time() + 60})}
    assert post(client, headers=good).status_code == 200
    expired = {"Authorization": "Bearer " + jwt({"sub": "u", "exp": time.time() - 1})}
    assert post(client, headers=expired).json()["message"] == "Token expired"
    forged = {"Authorization": "Bearer " + jwt({"sub": "u"}, secret="wrong")}
    assert post(client, headers=forged).json()["message"] == "Bad signature"
    none_alg = {"Authorization": "Bearer " + jwt({"sub": "u"}, alg="none")}
    assert post(client, headers=none_alg).status_code == 401
    assert client.get("/").status_code == 404  # test page hidden in production


def test_health_and_docs(client):
    assert client.get("/healthz").json()["ok"] is True
    assert client.get("/api/docs").status_code == 200
    assert "/api/food/analyze" in client.get("/api/openapi.json").json()["paths"]
    assert client.get("/").status_code == 200  # test page in dev


def test_old_path_still_works(client):
    r = client.post("/v1/food/analyze", files={"image": ("m.png", make_image(), "image/png")})
    assert r.status_code == 200


def test_slow_scan_does_not_block_other_requests(client, monkeypatch):
    gate = threading.Event()

    class Slow:
        def analyze(self, *a, **k):
            gate.wait(5)
            return FoodAnalyzer(provider=FakeProvider([BREAKFAST])).analyze(make_image())

    monkeypatch.setattr(api, "_analyzer", Slow())
    t = threading.Thread(target=lambda: post(client))
    t.start()
    time.sleep(0.2)
    started = time.perf_counter()
    assert client.get("/healthz").status_code == 200
    assert time.perf_counter() - started < 1.0  # health answered while the scan was still running
    gate.set()
    t.join()


def test_heic_photo_accepted(client):
    pillow_heif = pytest.importorskip("pillow_heif")
    img = Image.new("RGB", (300, 200), (200, 150, 90))
    heif = pillow_heif.from_pillow(img)
    buf = io.BytesIO()
    heif.save(buf, quality=80)
    r = post(client, data=buf.getvalue(), name="IMG_0001.HEIC", ctype="image/heic")
    assert r.status_code == 200, r.text


def test_decompression_bomb_rejected(client, monkeypatch):
    from food_macros import analyzer
    monkeypatch.setattr(analyzer, "MAX_PIXELS", 1000)
    r = post(client, data=make_image((100, 100)))
    assert (r.status_code, r.json()["error"]) == (422, "BAD_IMAGE")


def test_dishes_endpoint(client):
    body = client.get("/api/food/dishes").json()
    keys = {d["key"]: d for d in body["dishes"]}
    assert len(keys) >= 70 and keys["naan"]["piece_g"] == 100 and keys["dal_makhani"]["per_100g"]["kcal"] == 150

