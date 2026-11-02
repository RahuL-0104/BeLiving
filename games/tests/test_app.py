import json, os, sys, tempfile, threading, unittest, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["BRAIN_GAMES_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["BRAIN_GAMES_QUIET"] = "1"
import app  # noqa: E402


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = app.make_server(port=0, host="127.0.0.1")
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def req(self, path, body=None, user="u1"):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(self.base + path, data=data, headers={"content-type": "application/json", "x-user-id": user})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def test_health(self):
        s, b = self.req("/health")
        self.assertEqual(s, 200)
        self.assertEqual(len(b["games"]), 5)

    def test_index_served(self):
        with urllib.request.urlopen(self.base + "/") as r:
            self.assertIn(b"Mind Gym", r.read())
        for f in ["mandala", "pattern_recall", "ivory", "power_memory", "speed_match"]:
            with urllib.request.urlopen(f"{self.base}/js/games/{f}.js") as r:
                self.assertEqual(r.status, 200)

    def test_save_and_best(self):
        s, b = self.req("/api/score", {"game": "ivory", "score": 6, "level": 6, "duration_s": 90}, user="best")
        self.assertEqual(s, 200); self.assertTrue(b["is_best"]); self.assertEqual(b["best"], 6)
        s, b = self.req("/api/score", {"game": "ivory", "score": 4, "duration_s": 60}, user="best")
        self.assertFalse(b["is_best"]); self.assertEqual(b["best"], 6)
        s, b = self.req("/api/scores", user="best")
        self.assertEqual(b["best"]["ivory"], 6)
        self.assertEqual(b["plays_today"], 2)
        self.assertEqual(b["minutes_today"], 2)
        self.assertEqual(b["streak_days"], 1)

    def test_users_isolated(self):
        self.req("/api/score", {"game": "speed_match", "score": 500}, user="a")
        s, b = self.req("/api/scores", user="b")
        self.assertNotIn("speed_match", b["best"])

    def test_validation(self):
        for bad in [{"game": "chess", "score": 1}, {"game": "ivory", "score": 1, "mode": "cheat"}, {"game": "mandala", "score": 999999}, {"game": "ivory", "score": -1}, {"game": "ivory", "score": "x"}, {"game": "ivory", "score": 1, "duration_s": 999999}]:
            s, b = self.req("/api/score", bad)
            self.assertEqual(s, 422, bad)
        s, _ = self.req("/api/score", ["not", "a", "dict"])
        self.assertEqual(s, 422)


    def test_daily_leaderboard_and_rank(self):
        self.req("/api/name", {"name": "Asha"}, user="lb1")
        self.req("/api/name", {"name": "Ravi"}, user="lb2")
        s, b = self.req("/api/score", {"game": "pattern_recall", "score": 300, "mode": "daily"}, user="lb1")
        self.assertEqual(b["rank"], 1)
        s, b = self.req("/api/score", {"game": "pattern_recall", "score": 500, "mode": "daily"}, user="lb2")
        self.assertEqual((b["rank"], b["players"]), (1, 2))
        # practice runs never reach the board
        self.req("/api/score", {"game": "pattern_recall", "score": 9999, "mode": "practice"}, user="lb3")
        s, b = self.req("/api/leaderboard?game=pattern_recall&period=today", user="lb1")
        self.assertEqual([e["name"] for e in b["top"]], ["Ravi", "Asha"])
        self.assertEqual(b["me"], {"rank": 2, "score": 300})
        self.assertTrue(b["top"][1]["me"])
        for period in ("week", "all"):
            s, b = self.req(f"/api/leaderboard?game=pattern_recall&period={period}")
            self.assertEqual(s, 200)

    def test_leaderboard_validation(self):
        s, _ = self.req("/api/leaderboard?game=chess")
        self.assertEqual(s, 422)
        s, _ = self.req("/api/leaderboard?game=ivory&period=year")
        self.assertEqual(s, 422)
        for bad in ["A", "x" * 30, "<script>"]:
            s, _ = self.req("/api/name", {"name": bad})
            self.assertEqual(s, 422, bad)

    def test_calm_not_best_and_daily_done(self):
        s, b = self.req("/api/score", {"game": "mandala", "score": 100, "mode": "calm"}, user="calm")
        self.assertFalse(b["is_best"])
        self.req("/api/score", {"game": "mandala", "score": 400, "mode": "daily"}, user="calm")
        s, b = self.req("/api/scores", user="calm")
        self.assertEqual(b["best"]["mandala"], 400)
        self.assertEqual(b["daily_done"], ["mandala"])

    def test_old_database_upgrades(self):
        import sqlite3
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        c = sqlite3.connect(path)
        c.execute("CREATE TABLE plays (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, game TEXT NOT NULL, score INTEGER NOT NULL, level INTEGER, duration_s INTEGER, meta TEXT, played_on TEXT NOT NULL, created_at TEXT NOT NULL)")
        c.execute("INSERT INTO plays(user_id,game,score,played_on,created_at) VALUES('old','ivory',7,'2026-10-01','x')")
        c.commit(); c.close()
        old = app.DB_PATH
        app.DB_PATH = path
        try:
            self.assertEqual(app.summary("old")["best"]["ivory"], 7)
            app.save_score("old", {"game": "ivory", "score": 9, "mode": "daily"})
        finally:
            app.DB_PATH = old


if __name__ == "__main__":
    unittest.main()
