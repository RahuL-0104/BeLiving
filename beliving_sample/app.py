"""
BeLiving - sample app (all modules in one place)
Run:  python app.py      -> opens in your browser at http://localhost:8080

Starts every BeLiving module in the background and shows them as one phone app:
  Coach chat      (chatbot folder,        API on port 8010)
  Beat the Clock  (beat_the_clock folder, port 8000)
  Voice Journal   (voice_journal folder,  port 8001)
  Focus Lock      (pomodoro folder,       port 8002)
  Box Breathing   (box_breathing folder,  port 8003)
  Food Scan       (food_macros folder,    API on port 8006)

The module folders must sit next to this folder (all on the Desktop).
Each module still works on its own too. Nothing inside them is changed.
"""
import atexit
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 8080
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # the Desktop: module folders live here
LOGS = HERE / "logs"

# Starts a module's own app.py without it opening an extra browser tab
NO_TAB = ("import runpy, sys, webbrowser; webbrowser.open = lambda *a, **k: True; "
          "sys.argv = ['app.py']; runpy.run_path('app.py', run_name='__main__')")

MODULES = {
    "coach":   {"name": "Coach", "folder": "chatbot", "port": 8010,
                "cmd": ["-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8010"],
                "check": "/health", "needs": "API key in chatbot\\.env"},
    "clock":   {"name": "Beat the Clock", "folder": "beat_the_clock", "port": 8000,
                "cmd": ["-c", NO_TAB], "check": "/", "needs": "Gemini key in beat_the_clock\\keys.env"},
    "journal": {"name": "Voice Journal", "folder": "voice_journal", "port": 8001,
                "cmd": ["-c", NO_TAB], "check": "/", "needs": "API keys in voice_journal\\keys.env"},
    "focus":   {"name": "Focus Lock", "folder": "pomodoro", "port": 8002,
                "cmd": ["-c", NO_TAB], "check": "/", "needs": "nothing extra"},
    "calm":    {"name": "Box Breathing", "folder": "box_breathing", "port": 8003,
                "cmd": ["-c", NO_TAB], "check": "/", "needs": "nothing extra"},
    "food":    {"name": "Food Scan", "folder": "food_macros", "port": 8006,
                "cmd": ["-c", NO_TAB], "check": "/healthz", "needs": "Gemini key in food_macros\\.env",
                # the Food tab reaches it through this app's /food/ pass-through (see proxy_food)
                "env": {"HOST": "127.0.0.1", "PORT": "8006"},
                "borrow_key": True},
}

_procs = {}          # id -> Popen
_state = {}          # id -> {"state": starting|running|stopped|missing, "message": str}


# ---------------------------------------------------------------- module processes
def _port_open(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _python_for(folder):
    """Use the module's own venv (venv or .venv) if it has one, otherwise this Python."""
    for v in ("venv", ".venv"):
        for p in (folder / v / "Scripts" / "python.exe", folder / v / "bin" / "python"):
            if p.exists():
                return str(p)
    return sys.executable


def _env_value(path, key):
    """Read KEY=value from a .env file (without printing or storing it anywhere)."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def _module_env(m, folder):
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", **m.get("env", {}))
    # Dev convenience: until Food Scan has its own key, reuse the Coach's Gemini key from chatbot\.env.
    if m.get("borrow_key") and not _env_value(folder / ".env", "GEMINI_API_KEY") and not env.get("GEMINI_API_KEY"):
        key = _env_value(ROOT / "chatbot" / ".env", "GEMINI_API_KEY")
        if key:
            env["GEMINI_API_KEY"] = key
    return env


def _tail(mid, n=6):
    try:
        lines = (LOGS / f"{mid}.log").read_text(encoding="utf-8", errors="replace").strip().splitlines()
        return "\n".join(lines[-n:])
    except FileNotFoundError:
        return ""


def start_module(mid):
    m = MODULES[mid]
    folder = ROOT / m["folder"]
    if _port_open(m["port"]):
        _state[mid] = {"state": "running", "message": "Already running"}
        return
    if not folder.exists():
        _state[mid] = {"state": "missing", "message": f"Folder not found: {folder}"}
        return
    LOGS.mkdir(exist_ok=True)
    log = open(LOGS / f"{mid}.log", "w", encoding="utf-8")
    env = _module_env(m, folder)
    try:
        _procs[mid] = subprocess.Popen([_python_for(folder)] + m["cmd"], cwd=folder, env=env,
                                       stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        _state[mid] = {"state": "starting", "message": "Starting..."}
    except OSError as e:
        _state[mid] = {"state": "stopped", "message": str(e)}


def refresh(mid):
    m, st = MODULES[mid], _state.get(mid, {})
    if st.get("state") == "missing":
        return st
    if _port_open(m["port"]):
        st = {"state": "running", "message": "Running"}
    else:
        p = _procs.get(mid)
        if p is not None and p.poll() is not None:
            st = {"state": "stopped", "message": _tail(mid) or "Stopped"}
        elif p is None:
            st = {"state": "stopped", "message": "Not started"}
    _state[mid] = st
    return st


def stop_all():
    for p in _procs.values():
        if p.poll() is None:
            try:
                p.terminate()
            except OSError:
                pass


atexit.register(stop_all)


# ---------------------------------------------------------------- home screen numbers
def _get(port, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=0.8) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def summary():
    today = date.today()
    days = set()
    out = {"calm_minutes": 0, "focus_minutes": 0, "leaves": 0, "journal_today": 0, "journal_total": 0}

    calm = _get(8003, "/api/stats")
    if calm:
        out["calm_minutes"] = calm.get("minutes_today", 0)
        for i in range(calm.get("streak", 0)):
            days.add(today - timedelta(days=i))

    focus = _get(8002, "/api/stats")
    if focus:
        out["focus_minutes"] = (focus.get("today") or {}).get("minutes", 0)
        out["leaves"] = focus.get("points", 0)
        for i in range(focus.get("streak", 0)):
            days.add(today - timedelta(days=i))

    entries = ROOT / "voice_journal" / "entries"
    if entries.exists():
        for f in entries.glob("*.json"):
            try:
                d = date.fromisoformat(f.name[:10])
            except ValueError:
                continue
            out["journal_total"] += 1
            days.add(d)
            if d == today:
                out["journal_today"] += 1

    streak, d = 0, today
    while d in days:
        streak += 1
        d -= timedelta(days=1)
    monday = today - timedelta(days=today.weekday())
    out["streak"] = streak
    out["week"] = [(monday + timedelta(days=i)) in days for i in range(7)]
    out["today_index"] = today.weekday()
    return out


# ---------------------------------------------------------------- Food Scan pass-through
# The Food tab calls /food/... on this app, which forwards to the Food Scan API. Same address for the
# page, so it works in any browser or phone webview without CORS settings.
FOOD_PREFIX = "/food/"
FOOD_MAX_BODY = 12 * 1024 * 1024


def proxy_food(handler, method):
    port = MODULES["food"]["port"]
    path = handler.path[len(FOOD_PREFIX) - 1:]               # "/food/api/x" -> "/api/x"
    if not path.startswith(("/api/food/", "/healthz")):
        return handler._send(404, {"ok": False, "error": "NOT_FOUND", "message": "Not found"})
    body = None
    if method == "POST":
        n = int(handler.headers.get("Content-Length") or 0)
        if n > FOOD_MAX_BODY:
            return handler._send(413, {"ok": False, "error": "TOO_LARGE", "message": "Photo is too large"})
        body = handler.rfile.read(n)
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body, method=method)
    for h in ("Content-Type", "Authorization", "X-User-Id"):
        if handler.headers.get(h):
            req.add_header(h, handler.headers[h])
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            code, data, kind, extra = r.status, r.read(), r.headers.get("Content-Type", "application/json"), r.headers
    except urllib.error.HTTPError as e:                      # 4xx / 5xx from Food Scan: pass it on as is
        code, data, kind, extra = e.code, e.read(), e.headers.get("Content-Type", "application/json"), e.headers
    except OSError:
        return handler._send(503, {"ok": False, "error": "NOT_RUNNING", "message": "Food Scan isn't running"})
    handler.send_response(code)
    handler.send_header("Content-Type", kind)
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    for h in ("X-Scans-Left", "Retry-After"):
        if extra.get(h):
            handler.send_header(h, extra[h])
    handler.end_headers()
    handler.wfile.write(data)


# ---------------------------------------------------------------- page
PAGE = (HERE / "home.html").read_text(encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, kind="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith(FOOD_PREFIX):
            return proxy_food(self, "GET")
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/api/status":
            return self._send(200, {mid: dict(refresh(mid), port=m["port"], name=m["name"], needs=m["needs"])
                                    for mid, m in MODULES.items()})
        if self.path == "/api/summary":
            return self._send(200, summary())
        self._send(404, {"error": "Not found"})

    def do_POST(self):
        if self.path.startswith(FOOD_PREFIX):
            return proxy_food(self, "POST")
        if self.path.startswith("/api/restart/"):
            mid = self.path.rsplit("/", 1)[-1]
            if mid in MODULES:
                p = _procs.get(mid)
                if p is not None and p.poll() is None:
                    p.terminate()
                    try:
                        p.wait(3)
                    except subprocess.TimeoutExpired:
                        p.kill()
                start_module(mid)
                return self._send(200, {"ok": True})
        self._send(404, {"error": "Not found"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if _port_open(PORT):
        print(f"\n  BeLiving is already running. Opening http://localhost:{PORT}")
        webbrowser.open(f"http://localhost:{PORT}")
        sys.exit(0)

    print("\n  \U0001F33F  Starting BeLiving...\n")
    for mid in MODULES:
        start_module(mid)
    time.sleep(2.5)
    for mid, m in MODULES.items():
        st = refresh(mid)
        mark = {"running": "✓", "starting": "…"}.get(st["state"], "✗")
        print(f"   {mark}  {m['name']:<15} port {m['port']}  {'' if st['state'] in ('running', 'starting') else st['message'].splitlines()[-1][:80]}")
    url = f"http://localhost:{PORT}"
    print(f"\n  BeLiving app running at {url}")
    print("  Keep this window open. Press Ctrl + C to stop everything.")
    print(f"  If a module won't open, its error is in {LOGS}\\<module>.log\n")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopping all modules...")
    finally:
        stop_all()
        print("  Stopped.")
