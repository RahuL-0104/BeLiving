"""
BeLiving - Food Scan service (photo -> food labels, portion size, macros)

Run locally:   python app.py              -> opens http://localhost:8006 (test page) + /api/docs
Production:    uvicorn app:app --host 0.0.0.0 --port 8006 --workers 2
               (or: docker build -t beliving-food . && docker run -p 8006:8006 --env-file .env beliving-food)

All settings are environment variables; see .env.example. Only GEMINI_API_KEY (or OPENAI_*) is required.
"""
import os
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent

try:
    import fastapi  # noqa: F401
    import google.genai  # noqa: F401
    import uvicorn  # noqa: F401
except ImportError:  # first run from VS Code's ▷ button: install what's missing, once
    if __name__ != "__main__":
        raise
    print("\n  First run: installing packages (one time, needs internet)...\n")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", str(HERE / "requirements.txt")])

import logging  # noqa: E402

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from food_macros.api import app  # noqa: E402,F401  (food_macros loads .env next to this file)

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", 8006))


def _port_free(host, port):
    probe = "127.0.0.1" if host in ("0.0.0.0", "", "localhost") else host
    try:
        with socket.create_connection((probe, port), timeout=0.5):
            return False
    except OSError:
        return True


if __name__ == "__main__":
    import uvicorn

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    if not _port_free(HOST, PORT):
        print(f"\n  Port {PORT} is busy. Close the other Food Scan window (or set PORT=8007) and try again.\n")
        sys.exit(1)
    url = f"http://localhost:{PORT}"
    print(f"\n  \U0001F37D  BeLiving Food Scan running at {url}")
    print(f"      API docs: {url}/api/docs")
    print("      Keep this window open. Press Ctrl + C to stop.\n")
    if HOST in ("127.0.0.1", "localhost"):
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
