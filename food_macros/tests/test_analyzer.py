"""Offline tests: a fake provider stands in for Gemini/OpenAI, so these run with no API key.

Run: python -m pytest -q
"""
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from food_macros import AnalysisError, FoodAnalyzer
from food_macros.providers import VisionProvider


def make_image(size=(2000, 1500), mode="RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, (200, 150, 90) if mode == "RGB" else (200, 150, 90, 255)).save(buf, format="PNG")
    return buf.getvalue()


class FakeProvider(VisionProvider):
    name = "fake"

    def __init__(self, responses):
        super().__init__("fake-model")
        self.responses = list(responses)
        self.calls = 0
        self.last_image = None

    def complete(self, image, mime, system, user):
        self.calls += 1
        self.last_image = image
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, str) else json.dumps(r)


def item(name, key, grams, conf=0.9, per=None, portion=""):
    return {
        "name": name, "canonical_key": key, "portion_description": portion,
        "estimated_grams": grams, "confidence": conf,
        "per_100g": per or {"kcal": 100, "protein_g": 5, "carbs_g": 15, "fat_g": 2, "fiber_g": 1},
        "notes": "",
    }


BREAKFAST = {
    "is_food": True,
    "items": [
        item("Idli", "idli", 120, portion="3 idlis"),
        item("Sambar", "sambar", 150),
        item("Coconut Chutney", "coconut_chutney", 40),
    ],
}


def test_db_values_override_model_and_totals_add_up():
    a = FoodAnalyzer(provider=FakeProvider([BREAKFAST]))
    r = a.analyze(make_image())
    assert [i.macro_source for i in r.items] == ["food_db"] * 3
    idli = r.items[0]
    assert idli.macros.kcal == pytest.approx(140 * 1.2, abs=0.1)
    assert idli.portion == "3 idlis"
    assert r.totals.kcal == pytest.approx(sum(i.macros.kcal for i in r.items), abs=0.3)


def test_size_output():
    resp = {"is_food": True, "items": [
        item("Idli", "idli", 160, portion="4 idlis"),                       # db serving 80 -> 2x -> large
        {**item("Sambar", "sambar", 100), "estimated_ml": 100},            # db serving 150 -> 0.67 -> small
        {**item("Neer Dosa", "neer_dosa", 90), "typical_serving_g": 90},  # not in db -> model serving
    ]}
    r = FoodAnalyzer(provider=FakeProvider([resp])).analyze(make_image())
    idli, sambar, neer = (i.size for i in r.items)
    assert (idli.category, idli.servings, idli.description) == ("large", 2.0, "4 idlis")
    assert (sambar.category, sambar.ml) == ("small", 100)
    assert (neer.category, neer.servings, neer.ml) == ("regular", 1.0, None)


def test_alias_match():
    resp = {"is_food": True, "items": [item("Uppittu", "uppittu", 200)]}
    r = FoodAnalyzer(provider=FakeProvider([resp])).analyze(make_image())
    assert r.items[0].canonical_key == "upma" and r.items[0].macro_source == "food_db"


def test_unknown_dish_uses_model_and_fixes_bad_energy():
    bad = {"kcal": 500, "protein_g": 10, "carbs_g": 20, "fat_g": 5, "fiber_g": 2}  # macros say 165
    resp = {"is_food": True, "items": [item("Neer Dosa", "neer_dosa", 100, per=bad)]}
    r = FoodAnalyzer(provider=FakeProvider([resp])).analyze(make_image())
    lab = r.items[0]
    assert lab.macro_source == "model"
    assert lab.per_100g.kcal == pytest.approx(165)
    assert any("recomputed" in w for w in r.warnings)


def test_low_confidence_flagged_and_grams_clamped():
    resp = {"is_food": True, "items": [item("Some curry", "mystery_curry", 9000, conf=0.4)]}
    r = FoodAnalyzer(provider=FakeProvider([resp])).analyze(make_image())
    lab = r.items[0]
    assert lab.needs_confirmation is True
    assert lab.grams == 1500
    assert any("clamped" in w for w in r.warnings)


def test_not_food():
    r = FoodAnalyzer(provider=FakeProvider([{"is_food": False, "items": []}])).analyze(make_image())
    assert r.is_food is False and r.items == [] and r.totals.kcal == 0


def test_markdown_wrapped_json_and_retry_on_garbage():
    p = FakeProvider(["sorry I can't", "```json\n" + json.dumps(BREAKFAST) + "\n```"])
    r = FoodAnalyzer(provider=p).analyze(make_image())
    assert p.calls == 2 and len(r.items) == 3


def test_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr("food_macros.analyzer.time.sleep", lambda s: None)
    p = FakeProvider([RuntimeError("429 rate limited")])
    with pytest.raises(AnalysisError):
        FoodAnalyzer(provider=p).analyze(make_image())
    assert p.calls == 5


def test_cache_avoids_second_paid_call():
    p = FakeProvider([BREAKFAST])
    a = FoodAnalyzer(provider=p)
    img = make_image()
    a.analyze(img)
    r2 = a.analyze(img)
    assert p.calls == 1 and r2.cached is True


def test_image_is_downscaled_and_rgba_ok():
    p = FakeProvider([BREAKFAST])
    FoodAnalyzer(provider=p).analyze(make_image((4000, 3000), mode="RGBA"))
    sent = Image.open(io.BytesIO(p.last_image))
    assert max(sent.size) <= 1024 and sent.format == "JPEG"


def test_bad_image_rejected():
    with pytest.raises(AnalysisError):
        FoodAnalyzer(provider=FakeProvider([BREAKFAST])).analyze(b"not an image")


def test_api_endpoint(monkeypatch):
    from food_macros import api

    monkeypatch.setattr(api, "_analyzer", FoodAnalyzer(provider=FakeProvider([BREAKFAST])))
    client = TestClient(api.app)
    res = client.post("/api/food/analyze", files={"image": ("meal.png", make_image(), "image/png")},
                      data={"hint": "home cooked"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 3 and body["totals"]["kcal"] > 0
    assert body["items"][0]["size"]["category"] in {"small", "regular", "large"}
    assert client.get("/").status_code == 200

    res = client.post("/api/food/analyze", files={"image": ("x.txt", b"hello", "text/plain")})
    assert res.status_code == 415


def test_retry_wait_honours_rate_limit_hint():
    from food_macros.analyzer import _retry_wait
    assert _retry_wait("429 RESOURCE_EXHAUSTED ... Please retry in 11.4s.", 0) == pytest.approx(12.4)
    assert _retry_wait("{'retryDelay': '30s'}", 0) == 31
    assert _retry_wait("503 UNAVAILABLE overloaded", 0) == 2


def test_no_retry_on_wrong_model(monkeypatch):
    monkeypatch.setattr("food_macros.analyzer.time.sleep", lambda s: None)
    p = FakeProvider([RuntimeError("404 NOT_FOUND model no longer available")])
    with pytest.raises(AnalysisError):
        FoodAnalyzer(provider=p).analyze(make_image())
    assert p.calls == 1


def test_sloppy_model_output_is_tolerated():
    resp = {"is_food": True, "items": [
        {**item("Idli", "idli", 80), "confidence": 92, "notes": None, "estimated_ml": 0,
         "per_100g": {"kcal": 140, "protein_g": 4.5, "carbs_g": 29, "fat_g": 0.5, "fiber_g": None}},
        {**item("Pickle", "mango_pickle", 0)},  # 0 g -> invalid, should be skipped not crash
    ]}
    r = FoodAnalyzer(provider=FakeProvider([resp])).analyze(make_image())
    assert [i.name for i in r.items] == ["Idli"]
    assert r.items[0].confidence == 0.92 and r.items[0].size.ml is None
    assert any("Skipped Pickle" in w for w in r.warnings)


def test_gemini3_config_has_no_low_temperature():
    from google.genai import types
    from food_macros.providers import GeminiProvider
    g = GeminiProvider(model="gemini-3.8-flash", api_key="x")
    cfg = g._config(types, "sys", "gemini-3.8-flash")
    assert cfg.temperature is None and cfg.thinking_config.thinking_level is not None
    assert g._client._api_client._http_options.timeout == 25000
    assert g.models == ["gemini-3.8-flash", "gemini-3.5-flash-lite"]


def test_gemini_falls_back_to_backup_model():
    from food_macros.providers import GeminiProvider
    g = GeminiProvider(model="gemini-3.8-flash", api_key="x")
    calls = []

    class Resp:
        text = '{"is_food": false, "items": []}'

    def fake_generate(model, contents, config):
        calls.append(model)
        if model == "gemini-3.8-flash":
            raise TimeoutError("read timed out")
        return Resp()

    g._client.models.generate_content = fake_generate
    assert g.complete(b"x", "image/jpeg", "s", "u") == Resp.text
    assert calls == ["gemini-3.8-flash", "gemini-3.5-flash-lite"] and g.model == "gemini-3.5-flash-lite"


def test_food_db_values_are_self_consistent():
    """Every dish: kcal within 12% of 4P+4C+9F, has a serving size, no alias points to two dishes."""
    raw = json.loads((Path(__file__).resolve().parents[1] / "food_macros" / "food_db.json").read_text())
    seen = {}
    for key, row in raw.items():
        if key.startswith("_"):
            continue
        energy = 4 * row["protein_g"] + 4 * row["carbs_g"] + 9 * row["fat_g"]
        assert abs(energy - row["kcal"]) / row["kcal"] <= 0.12, key
        assert row["serving_g"] > 0, key
        for alias in [key, *row["aliases"]]:
            assert seen.setdefault(alias, key) == key, f"{alias} used by {seen[alias]} and {key}"


def test_paratha_maps_to_plain_not_aloo():
    resp = {"is_food": True, "items": [item("Paratha", "paratha", 70), item("Onion slices", "onion", 30),
                                       item("Lemon", "lemon_wedge", 10)]}
    r = FoodAnalyzer(provider=FakeProvider([resp])).analyze(make_image())
    assert [i.canonical_key for i in r.items] == ["plain_paratha", "onion_salad", "lemon_wedge"]
    assert all(i.macro_source == "food_db" for i in r.items)


def test_backup_model_used_first_after_main_model_overloads():
    from food_macros.providers import GeminiProvider
    g = GeminiProvider(model="gemini-3.8-flash", api_key="x")
    calls = []

    class Resp:
        text = '{"is_food": false, "items": []}'

    def fake_generate(model, contents, config):
        calls.append(model)
        if model == "gemini-3.8-flash":
            raise RuntimeError("503 UNAVAILABLE high demand")
        return Resp()

    g._client.models.generate_content = fake_generate
    g.complete(b"x", "image/jpeg", "s", "u")
    g.complete(b"x", "image/jpeg", "s", "u")
    assert calls == ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.5-flash-lite"]


def test_demo_path_cleaning(tmp_path, monkeypatch):
    import demo
    img = tmp_path / "meal.jpg"
    img.write_bytes(make_image())
    assert demo.clean_path(f'  "{img}"  ') == img
    monkeypatch.setattr(demo, "DESKTOP", tmp_path)
    assert demo.clean_path("meal.jpg") == img


def test_count_first_portions_fix_restaurant_thali():
    """Replays the real mistake: model counted 2 naans but weighed them at 90 g total."""
    resp = {"is_food": True, "items": [
        {**item("Naan", "naan", 90, portion="2 folded naans"), "pieces": 2},
        {**item("Papad", "papad", 20, portion="4 roasted papads"), "pieces": 4},
        {**item("Dal Makhani", "dal_makhani", 150), "estimated_ml": 150},
        {**item("Neer Dosa", "neer_dosa", 120, portion="3 neer dosas"), "pieces": 3},  # not in table
    ]}
    r = FoodAnalyzer(provider=FakeProvider([resp])).analyze(make_image())
    naan, papad, dal, neer = r.items
    assert (naan.size.pieces, naan.size.piece_g, naan.grams) == (2, 100, 200)
    assert naan.macros.kcal == pytest.approx(580, abs=1)
    assert (papad.size.pieces, papad.grams) == (4, 52)
    assert dal.canonical_key == "dal_makhani" and dal.size.pieces is None
    assert (neer.size.pieces, neer.size.piece_g, neer.grams) == (3, 40, 120)  # model grams split per piece


def test_bad_piece_counts_ignored():
    resp = {"is_food": True, "items": [{**item("Idli", "idli", 80), "pieces": "lots"},
                                       {**item("Roti", "chapati", 80), "pieces": 0}]}
    r = FoodAnalyzer(provider=FakeProvider([resp])).analyze(make_image())
    assert [i.size.pieces for i in r.items] == [None, None]
    assert [i.grams for i in r.items] == [80, 80]
