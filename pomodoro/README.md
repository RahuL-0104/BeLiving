# Focus Lock (Pomodoro) · BeLiving

Pick a time, lock in, and stay in the app. Every round you finish earns leaves 🍃,
which grow your level and unlock badges.

## Run it
1. Double-click **setup.bat** (first time only)
2. Double-click **run.bat**. Focus Lock opens in your browser at http://localhost:8002
3. Type a time, switch between **minutes** and **hours** (5 min to 8 hours), and tap **Start lock**

No API key needed, and nothing to install besides Python. Progress is saved in the `data` folder.

## How the lock works
- Once the lock is on: **no switching apps, no notifications**. Calls and emergency SOS still work.
- Before starting, pick **breaks: None / 1 / 2 / 3** (5 min each). During a break the timer pauses
  and the phone is unlocked. When the break ends you have 15 s to lock back in, or the lock breaks.
- Leave the app during the lock and a **15 second** countdown starts. Come back in time = 1 slip
  (2 allowed). A 3rd slip, or staying away longer = **lock broken**, no leaves.
- Hold ■ for 2 s to end early (no leaves).

## Rewards
| What | Leaves |
|---|---|
| Focus time | 1 per minute (×1.25 for 45–59 min, ×1.5 for 60+ min) → 25 min = 25, 50 min = 63, 1 h = 90, 2 h = 180 |
| Clean lock (never left the app) | +10 |
| Skipped your breaks (picked breaks, used none) | +5 |
| Task done (ticked off at the end, once per session) | +15 |
| Full set (every round of a 2+ round session) | +20 |
| Daily streak (first finished round of the day) | +5 per streak day, max +35 |

Levels: 🌰 Seed (0) → 🌱 Sprout (150) → 🌿 Sapling (400) → 🌳 Tree (900) → 🌲 Forest (2000)

Badges: 🔒 First Lock · ✨ Untouchable (3 clean in a row) · 🌊 Deep Diver (50+ min) · 🍅 Full Set (4 rounds) ·
🔥 On Fire (3-day streak) · ⚡ Unstoppable (7-day streak) · ⏳ 10 Hour Club · 🗡️ Task Slayer (10 tasks)

## For the senior / app team
All the rules and rewards live in `pomodoro.py`. The app only shows the timer and reports
what happened. The server checks the time really passed, so a round can't be finished early.

```python
import pomodoro

s = pomodoro.start("DBMS notes", minutes=50, rounds=2, user="user_123")
# -> {"ok": true, "session": {"id", "task", "minutes", "break_minutes", "rounds", "round",
#     "seconds_left", "grace_seconds": 15, "max_slips": 2, "points_if_finished": 63}}

r = pomodoro.finish_round(s["session"]["id"], slips=1, task_done=True, user="user_123")
# -> {"ok": true, "earned": 83, "breakdown": [{"label", "points"}], "total_points",
#     "level": {...}, "level_up": bool, "streak", "new_badges": [...],
#     "session_done": false, "next": {"round": 2, "rounds": 2, "break_minutes": 10}}
#    or {"ok": false, "error": "TOO_EARLY", "seconds_left": 120}

pomodoro.next_round(session_id, user="user_123")          # after the break
pomodoro.give_up(session_id, "left_app", user="user_123")  # reasons: left_app | too_many_slips | quit
pomodoro.stats(user="user_123")                            # home screen: leaves, level, streak, badges, history
```

HTTP endpoints in `app.py` (same shapes): `GET /api/stats`, `POST /api/start`, `/api/finish`, `/api/next`, `/api/give_up`.

### Real lock spec for the mobile app
The browser version can only *detect* leaving. The app must actually block. Target behaviour:
**no app switching, no notifications, calls + emergency allowed, user-picked breaks.**

**Android (full lock)**
1. **Block app switching:** call `Activity.startLockTask()` when the lock starts (screen pinning).
   Home, Recents and the notification shade are blocked. Android asks the user to confirm pinning.
2. **Block notifications:** ask once for *Do Not Disturb access*
   (`ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS`), then during the lock set
   `NotificationManager.setInterruptionFilter(INTERRUPTION_FILTER_PRIORITY)` with a policy that
   allows **calls** (contacts + repeat callers) and **alarms** only. Save the user's old setting and restore it after.
3. **Emergency:** incoming calls still ring while pinned, and the power-button SOS always works. Nothing extra needed.
4. **Breaks:** on ☕ call `stopLockTask()` and restore DND, start the 5-min break timer and send a
   notification 1 min before it ends. On "Back to focus" call `startLockTask()` and DND again.
5. **If the user force-unpins** (holding Back + Recents), treat it like leaving: 15 s grace, then the lock breaks.
6. **Battery:** ask to be excluded from battery optimisation (needed on Xiaomi, Vivo, Oppo, Realme, Samsung),
   or the phone may kill the timer.

**iOS (partial lock: Apple doesn't allow a full one)**
- Apps can't block app switching or turn on Do Not Disturb.
- Best option: Apple's Screen Time API (`FamilyControls` + `ManagedSettings`). During the lock,
  shield every app except Phone so other apps show a "Locked by BeLiving" screen. Lift the shield during breaks.
  This needs Apple's **Family Controls entitlement** (apply early, approval takes time).
- For notifications, guide the user to set up a "BeLiving Focus" mode once in iOS Settings.
- Without the entitlement: detect leaving (`sceneDidEnterBackground`), send "Come back in 15s", break the lock if they don't.

**Server side (already done in `pomodoro.py`):** `start(..., breaks=2)`, `finish_round(..., breaks_used=1)`.
Rewards are only paid once the full focus time has passed, so the app can't be tricked into finishing early.

`data/` holds personal progress. Keep it out of GitHub (already in `.gitignore`).
