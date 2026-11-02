"""
BeLiving · Mind Gym (brain games module)
=========================================

Run:   python app.py          (opens the browser by itself)
Tests: python -m unittest discover tests

Zero dependencies: Python standard library only (http.server + sqlite3).
All gameplay runs in the browser (static/). This server only:
  1. serves the static files
  2. stores scores, streaks and the leaderboard

If the server is down, the frontend silently falls back to localStorage,
so the games never break.

Two modes per game:
  daily     same puzzle for everyone today (seeded by date) -> counts for the leaderboard
  practice  random every time, saved to your history only

API (send header  x-user-id: <id>, defaults to "demo"):
  GET  /health
  GET  /api/scores                      -> {best, plays_today, minutes_today, streak_days, recent, name}
  POST /api/score  {game, score, mode?, level?, duration_s?, meta?}
                                        -> {ok, best, is_best, plays_today, rank?, players?}
  POST /api/name   {name}               -> {ok, name}
  GET  /api/leaderboard?game=ivory&period=today|week|all
                                        -> {game, period, top:[{rank,name,score,me}], me:{rank,score}|null, players}
"""

import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
DB_PATH = os.environ.get("BRAIN_GAMES_DB", os.path.join(HERE, "data", "brain_games.db"))
PORT = int(os.environ.get("PORT", "8090"))
HOST = os.environ.get("HOST", "127.0.0.1")  # set HOST=0.0.0.0 to open it to your phone on the same Wi-Fi

GAMES = {"mandala", "pattern_recall", "ivory", "power_memory", "speed_match"}
MODES = {"daily", "practice", "calm"}
# Sanity caps per single run. Scores above these are rejected (basic anti-cheat).
MAX_SCORE = {"mandala": 20_000, "pattern_recall": 50_000, "ivory": 50_000, "power_memory": 50_000, "speed_match": 50_000}

_lock = threading.Lock()


def db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS plays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            game TEXT NOT NULL,
            score INTEGER NOT NULL,
            level INTEGER,
            duration_s INTEGER,
            meta TEXT,
            played_on TEXT NOT NULL,
            created_at TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'practice'
        )"""
    )
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(plays)")}
    if "mode" not in cols:  # upgrade a database from the first version
        conn.execute("ALTER TABLE plays ADD COLUMN mode TEXT NOT NULL DEFAULT 'practice'")
    conn.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, name TEXT NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_game ON plays(user_id, game)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_board ON plays(game, mode, played_on)")
    return conn


@contextmanager
def conn_ctx():
    conn = db()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _name_of(conn, user_id):
    r = conn.execute("SELECT name FROM users WHERE user_id=?", (user_id,)).fetchone()
    return r["name"] if r else None


def summary(user_id):
    today = date.today().isoformat()
    with _lock, conn_ctx() as conn:
        best = {
            r["game"]: r["best"]
            for r in conn.execute(
                "SELECT game, MAX(score) AS best FROM plays WHERE user_id=? AND mode!='calm' GROUP BY game", (user_id,)
            )
        }
        t = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(duration_s),0) AS secs FROM plays WHERE user_id=? AND played_on=?",
            (user_id, today),
        ).fetchone()
        days = {r["played_on"] for r in conn.execute("SELECT DISTINCT played_on FROM plays WHERE user_id=?", (user_id,))}
        daily_done = [
            r["game"]
            for r in conn.execute(
                "SELECT DISTINCT game FROM plays WHERE user_id=? AND mode='daily' AND played_on=?", (user_id, today)
            )
        ]
        recent = [
            dict(r)
            for r in conn.execute(
                "SELECT game, score, mode, level, played_on FROM plays WHERE user_id=? ORDER BY id DESC LIMIT 10",
                (user_id,),
            )
        ]
        name = _name_of(conn, user_id)
    streak, d = 0, date.today()
    if d.isoformat() not in days:
        d -= timedelta(days=1)
    while d.isoformat() in days:
        streak += 1
        d -= timedelta(days=1)
    return {
        "best": best,
        "plays_today": t["n"],
        "minutes_today": round(t["secs"] / 60),
        "streak_days": streak,
        "daily_done": daily_done,
        "recent": recent,
        "name": name,
    }


def _since(period):
    if period == "today":
        return date.today().isoformat()
    if period == "week":
        return (date.today() - timedelta(days=6)).isoformat()
    if period == "all":
        return "0000-00-00"
    raise ValueError("period must be today, week or all")


def leaderboard(game, period="today", user_id=None, limit=20):
    if game not in GAMES:
        raise ValueError(f"unknown game '{game}'")
    since = _since(period)
    with _lock, conn_ctx() as conn:
        rows = conn.execute(
            """SELECT p.user_id, MAX(p.score) AS score, MIN(p.created_at) AS first_at,
                      COALESCE(u.name, 'Player ' || substr(p.user_id, 1, 4)) AS name
               FROM plays p LEFT JOIN users u ON u.user_id = p.user_id
               WHERE p.game=? AND p.mode='daily' AND p.played_on>=?
               GROUP BY p.user_id
               ORDER BY score DESC, first_at ASC""",
            (game, since),
        ).fetchall()
    board, me = [], None
    for i, r in enumerate(rows):
        entry = {"rank": i + 1, "name": r["name"], "score": r["score"], "me": r["user_id"] == user_id}
        if entry["me"]:
            me = {"rank": i + 1, "score": r["score"]}
        if i < limit:
            board.append(entry)
    return {"game": game, "period": period, "top": board, "me": me, "players": len(rows)}


def set_name(user_id, body):
    name = re.sub(r"\s+", " ", str(body.get("name", ""))).strip()
    if not (2 <= len(name) <= 20):
        raise ValueError("name must be 2-20 characters")
    if re.search(r"[<>\"'`]", name):
        raise ValueError("name has characters that aren't allowed")
    with _lock, conn_ctx() as conn:
        conn.execute(
            "INSERT INTO users(user_id, name) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET name=excluded.name",
            (user_id, name),
        )
    return {"ok": True, "name": name}


def save_score(user_id, body):
    game = body.get("game")
    if game not in GAMES:
        raise ValueError(f"unknown game '{game}'")
    mode = body.get("mode") or "practice"
    if mode not in MODES:
        raise ValueError("mode must be daily, practice or calm")
    try:
        score = int(body.get("score", 0))
        level = int(body["level"]) if body.get("level") is not None else None
        duration = int(body.get("duration_s") or 0)
    except (TypeError, ValueError):
        raise ValueError("score, level and duration_s must be numbers")
    if not (0 <= score <= MAX_SCORE[game]):
        raise ValueError("score out of range")
    if not (0 <= duration <= 6 * 3600):
        raise ValueError("duration_s out of range")
    meta = body.get("meta")
    meta_s = json.dumps(meta)[:2000] if meta is not None else None
    today = date.today().isoformat()
    with _lock, conn_ctx() as conn:
        prev = conn.execute(
            "SELECT MAX(score) AS b FROM plays WHERE user_id=? AND game=? AND mode!='calm'", (user_id, game)
        ).fetchone()["b"]
        conn.execute(
            "INSERT INTO plays(user_id, game, score, level, duration_s, meta, played_on, created_at, mode) VALUES (?,?,?,?,?,?,?,?,?)",
            (user_id, game, score, level, duration, meta_s, today, datetime.now().isoformat(), mode),
        )
        n = conn.execute("SELECT COUNT(*) AS n FROM plays WHERE user_id=? AND played_on=?", (user_id, today)).fetchone()["n"]
    is_best = mode != "calm" and (prev is None or score > prev)
    out = {"ok": True, "best": max(score, prev or 0), "is_best": is_best, "plays_today": n}
    if mode == "daily":
        lb = leaderboard(game, "today", user_id)
        out["rank"] = lb["me"]["rank"] if lb["me"] else None
        out["players"] = lb["players"]
    return out


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=STATIC, **kw)

    def log_message(self, fmt, *args):
        if os.environ.get("BRAIN_GAMES_QUIET"):
            return
        super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", os.environ.get("CORS_ORIGIN", "*"))
        self.send_header("Access-Control-Allow-Headers", "content-type, x-user-id")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        if self.path.split("?")[0].endswith((".js", ".css", ".html", "/")):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _user(self):
        u = (self.headers.get("x-user-id") or "demo").strip()[:64]
        return u or "demo"

    def _json(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/health":
            return self._json(200, {"ok": True, "games": sorted(GAMES)})
        if u.path == "/api/scores":
            return self._json(200, summary(self._user()))
        if u.path == "/api/leaderboard":
            q = parse_qs(u.query)
            try:
                return self._json(
                    200, leaderboard(q.get("game", [""])[0], q.get("period", ["today"])[0], self._user())
                )
            except ValueError as e:
                return self._json(422, {"error": str(e)})
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        routes = {"/api/score": save_score, "/api/name": set_name}
        if path not in routes:
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 10_000:
                raise ValueError("body too large")
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("body must be a JSON object")
            return self._json(200, routes[path](self._user(), body))
        except (ValueError, json.JSONDecodeError) as e:
            return self._json(422, {"error": str(e)})


def make_server(port=PORT, host=HOST):
    return ThreadingHTTPServer((host, port), Handler)


def make_server_any_port(start=PORT, host=HOST):
    """Windows sometimes reserves ports (WinError 10013). Try the next few."""
    last = None
    for p in [start] + list(range(8765, 8785)) + [0]:
        try:
            return make_server(p, host)
        except OSError as e:
            last = e
    raise last


if __name__ == "__main__":
    srv = make_server_any_port()
    port = srv.server_address[1]
    url = f"http://localhost:{port}"
    print(f"\n  BeLiving Mind Gym running ->  {url}\n  (Ctrl+C to stop)\n")
    if not os.environ.get("NO_BROWSER"):
        import webbrowser

        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
