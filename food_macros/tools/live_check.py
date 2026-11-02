"""Live end-to-end check of the HTTP API with a real photo and the real vision model.

Run: python tools/live_check.py [photo.jpg]      (default: thali_restaurant.jpg, else thali.jpg, on the Desktop)
Uses food_macros/.env; if no key is there yet, borrows GEMINI_API_KEY from ../chatbot/.env (read locally,
never printed). Goes through the full stack: HTTP routing, auth, upload checks, worker thread, model, JSON.
Dev tool only (excluded from the Docker image).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

venv_py = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
try:
    import fastapi, httpx, multipart, google.genai, dotenv  # noqa: F401,E401
except ImportError:
    if venv_py.exists() and Path(sys.executable).resolve() != venv_py.resolve():
        sys.exit(subprocess.call([str(venv_py), __file__, *sys.argv[1:]]))
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", str(ROOT / "requirements-dev.txt")])

from dotenv import dotenv_values  # noqa: E402

local = dotenv_values(ROOT / ".env") if (ROOT / ".env").exists() else {}
if not (local.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")):
    borrowed = dotenv_values(DESKTOP / "chatbot" / ".env").get("GEMINI_API_KEY")
    if borrowed:
        os.environ["GEMINI_API_KEY"] = borrowed
        print("(no key in food_macros/.env yet: borrowing the chatbot's Gemini key for this check)\n")
os.environ.setdefault("GEMINI_MODEL", local.get("GEMINI_MODEL") or "gemini-3.8-flash")
os.environ["ALLOW_ANON"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from food_macros.api import app  # noqa: E402

default = next((DESKTOP / n for n in ("thali_restaurant.jpg", "thali.jpg") if (DESKTOP / n).exists()), None)
photo = Path(sys.argv[1]) if len(sys.argv) > 1 else default
out = ROOT / "live_check_output.txt"
lines = []


def say(s=""):
    print(s)
    lines.append(s)


with TestClient(app) as client:
    say(f"GET /healthz -> {client.get('/healthz').json()}")
    with open(photo, "rb") as f:
        res = client.post("/api/food/analyze", files={"image": (photo.name, f, "image/jpeg")},
                          headers={"X-User-Id": "live-check"})
    say(f"POST /api/food/analyze ({photo.name}) -> HTTP {res.status_code}, X-Scans-Left={res.headers.get('x-scans-left')}")
    body = res.json()
    if res.status_code == 200:
        for i in body["items"]:
            s, m = i["size"], i["macros"]
            ml = f"/{s['ml']:.0f}ml" if s["ml"] else ""
            cnt = f"{s['pieces']:g} x {s['piece_g']:g}g = " if s["pieces"] else ""
            say(f"  {i['name']:<24} {s['category']:<8} {cnt:>14}{s['grams']:>5.0f}g{ml:<7} {m['kcal']:>5.0f} kcal  "
                f"P{m['protein_g']:>5.1f} C{m['carbs_g']:>6.1f} F{m['fat_g']:>5.1f}  ({i['macro_source']})")
        t = body["totals"]
        say(f"  {'TOTAL':<46} {t['kcal']:>5.0f} kcal  P{t['protein_g']:>5.1f} C{t['carbs_g']:>6.1f} F{t['fat_g']:>5.1f}")
        say(f"  model={body['model']}  latency={body['latency_ms'] / 1000:.1f}s  warnings={body['warnings']}")
    else:
        say(json.dumps(body, indent=2))
    bad = client.post("/api/food/analyze", files={"image": ("x.txt", b"hi", "text/plain")})
    say(f"POST text file -> HTTP {bad.status_code} {bad.json()['error']}")
    say(f"GET /api/food/limits -> {client.get('/api/food/limits', headers={'X-User-Id': 'live-check'}).json()}")

out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"\nSaved to {out.name}")
