/* BeLiving · Mind Gym — shared core
   - game registry + hub + routing (#ivory opens a game directly)
   - sound (Web Audio, no files), haptics, confetti, toast, countdown
   - score storage: server API, falls back to localStorage automatically
*/
(function () {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
  const games = [];
  const BL = (window.BL = { games, $, h });

  /* ---------------- icons (inline SVG strokes) ---------------- */
  BL.ico = {
    back: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>',
    arrow: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>',
    sound: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5L6 9H3v6h3l5 4V5z"/><path d="M15.5 8.5a5 5 0 010 7"/><path d="M18.5 5.5a9 9 0 010 13"/></svg>',
    mute: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5L6 9H3v6h3l5 4V5z"/><path d="M22 9l-6 6M16 9l6 6"/></svg>',
    trophy: '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 01-10 0V4z"/><path d="M7 6H4a3 3 0 003 4M17 6h3a3 3 0 01-3 4"/></svg>',
    restart: '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 109-9 9.7 9.7 0 00-6.7 2.8L3 8"/><path d="M3 3v5h5"/></svg>',
  };

  /* ---------------- storage ---------------- */
  const LS = {
    get(k, d) { try { const v = localStorage.getItem("bl_mg_" + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("bl_mg_" + k, JSON.stringify(v)); } catch (e) {} },
  };
  BL.LS = LS;
  // each device gets its own id unless the app passes ?user=<id>
  let USER = new URLSearchParams(location.search).get("user") || LS.get("uid", null);
  if (!USER) { USER = "u_" + Math.random().toString(36).slice(2, 10); LS.set("uid", USER); }
  BL.user = USER;
  const API = location.protocol.startsWith("http") ? "" : null; // file:// → local only
  const isoLocal = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const today = () => isoLocal(new Date());
  BL.today = today;

  /* ---------------- seeded randomness ----------------
     Daily mode: everyone gets the same puzzle today → fair leaderboard.
     Practice: fresh random every run. */
  function hash(str) { let h = 1779033703 ^ str.length; for (let i = 0; i < str.length; i++) { h = Math.imul(h ^ str.charCodeAt(i), 3432918353); h = (h << 13) | (h >>> 19); } return (h >>> 0); }
  BL.rng = function (seed) {
    let a = typeof seed === "number" ? seed >>> 0 : hash(String(seed));
    const f = () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    f.int = (n) => Math.floor(f() * n);
    f.pick = (arr) => arr[Math.floor(f() * arr.length)];
    f.shuffle = (arr) => { arr = arr.slice(); for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(f() * (i + 1)); [arr[i], arr[j]] = [arr[j], arr[i]]; } return arr; };
    return f;
  };
  BL.seedFor = (gameId, mode) => (mode === "daily" ? `${gameId}|${today()}` : `${gameId}|${Date.now()}|${Math.random()}`);

  function localSummary() {
    const plays = LS.get("plays", []);
    const best = {};
    plays.forEach((p) => { if (p.mode !== "calm" && (best[p.game] == null || p.score > best[p.game])) best[p.game] = p.score; });
    const t = plays.filter((p) => p.played_on === today());
    const days = new Set(plays.map((p) => p.played_on));
    let streak = 0, d = new Date();
    if (!days.has(today())) d.setDate(d.getDate() - 1);
    while (days.has(d.toISOString().slice(0, 10))) { streak++; d.setDate(d.getDate() - 1); }
    const daily_done = [...new Set(t.filter((p) => p.mode === "daily").map((p) => p.game))];
    return { best, plays_today: t.length, minutes_today: Math.round(t.reduce((a, p) => a + (p.duration_s || 0), 0) / 60), streak_days: streak, daily_done, name: LS.get("name", null) };
  }
  BL.store = {
    summary: localSummary(),
    async refresh() {
      if (API !== null) {
        try {
          const r = await fetch(API + "/api/scores", { headers: { "x-user-id": USER } });
          if (r.ok) { this.summary = await r.json(); return this.summary; }
        } catch (e) {}
      }
      this.summary = localSummary();
      return this.summary;
    },
    async save(entry) {
      const prevBest = this.summary.best[entry.game];
      // always keep a local copy (offline-safe)
      const plays = LS.get("plays", []);
      plays.push({ ...entry, played_on: today() });
      LS.set("plays", plays.slice(-400));
      let res = null;
      if (API !== null) {
        try {
          const r = await fetch(API + "/api/score", { method: "POST", headers: { "content-type": "application/json", "x-user-id": USER }, body: JSON.stringify(entry) });
          if (r.ok) res = await r.json();
        } catch (e) {}
      }
      await this.refresh();
      const isBest = entry.mode === "calm" ? false : res ? res.is_best : prevBest == null || entry.score > prevBest;
      return { isBest, best: this.summary.best[entry.game], rank: res && res.rank, players: res && res.players };
    },
    async leaderboard(game, period) {
      if (API === null) return null;
      try { const r = await fetch(`${API}/api/leaderboard?game=${game}&period=${period}`, { headers: { "x-user-id": USER } }); if (r.ok) return await r.json(); } catch (e) {}
      return null;
    },
    async setName(name) {
      LS.set("name", name);
      if (API === null) return { ok: true, name };
      try {
        const r = await fetch(API + "/api/name", { method: "POST", headers: { "content-type": "application/json", "x-user-id": USER }, body: JSON.stringify({ name }) });
        const j = await r.json(); if (!r.ok) return { ok: false, error: j.error }; return j;
      } catch (e) { return { ok: true, name }; }
    },
  };

  /* ---------------- sound ---------------- */
  let ctx = null, master = null, muted = LS.get("muted", false);
  function ac() {
    if (!ctx) {
      const C = window.AudioContext || window.webkitAudioContext;
      if (!C) return null;
      ctx = new C();
      master = ctx.createGain(); master.gain.value = 0.55;
      const comp = ctx.createDynamicsCompressor();
      master.connect(comp); comp.connect(ctx.destination);
    }
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }
  function tone(freq, { type = "sine", dur = 0.18, vol = 0.25, attack = 0.008, delay = 0, slide = 0 } = {}) {
    if (muted) return;
    const c = ac(); if (!c) return;
    const t = c.currentTime + delay;
    const o = c.createOscillator(), g = c.createGain();
    o.type = type; o.frequency.setValueAtTime(freq, t);
    if (slide) o.frequency.exponentialRampToValueAtTime(freq * slide, t + dur);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(master); o.start(t); o.stop(t + dur + 0.05);
  }
  /* soft piano-ish voice: a few harmonics with a fast decay */
  function piano(freq, { dur = 1.1, vol = 0.32, delay = 0 } = {}) {
    if (muted) return;
    const c = ac(); if (!c) return;
    const t = c.currentTime + delay;
    const out = c.createGain();
    const lp = c.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.setValueAtTime(freq * 6, t); lp.frequency.exponentialRampToValueAtTime(freq * 1.5, t + dur);
    out.gain.setValueAtTime(0.0001, t);
    out.gain.exponentialRampToValueAtTime(vol, t + 0.006);
    out.gain.exponentialRampToValueAtTime(vol * 0.35, t + 0.25);
    out.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    [[1, 1, "triangle"], [2, 0.35, "sine"], [3, 0.12, "sine"], [4.01, 0.06, "sine"]].forEach(([m, a, ty]) => {
      const o = c.createOscillator(), g = c.createGain();
      o.type = ty; o.frequency.value = freq * m; o.detune.value = (Math.random() - 0.5) * 4;
      g.gain.value = a; o.connect(g); g.connect(lp); o.start(t); o.stop(t + dur + 0.05);
    });
    lp.connect(out); out.connect(master);
  }
  BL.sfx = {
    tone, piano,
    tap() { tone(660, { type: "sine", dur: 0.07, vol: 0.12 }); },
    soft() { tone(520, { type: "sine", dur: 0.12, vol: 0.1, slide: 1.2 }); },
    good() { tone(784, { type: "triangle", dur: 0.12, vol: 0.18 }); tone(1175, { type: "triangle", dur: 0.18, vol: 0.16, delay: 0.07 }); },
    bad() { tone(196, { type: "sine", dur: 0.28, vol: 0.28, slide: 0.6 }); },
    tick() { tone(1400, { type: "sine", dur: 0.03, vol: 0.06 }); },
    win() { [523, 659, 784, 1047].forEach((f, i) => tone(f, { type: "triangle", dur: 0.28, vol: 0.16, delay: i * 0.09 })); },
    whoosh() { tone(300, { type: "sine", dur: 0.25, vol: 0.06, slide: 2.4 }); },
    get muted() { return muted; },
    toggle() { muted = !muted; LS.set("muted", muted); return muted; },
    unlock() { ac(); },
  };
  BL.haptic = (p = 10) => { try { if (navigator.vibrate) navigator.vibrate(p); } catch (e) {} };

  /* ---------------- helpers ---------------- */
  BL.wait = (ms) => new Promise((r) => setTimeout(r, ms));
  BL.shuffle = (a) => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = (Math.random() * (i + 1)) | 0; [a[i], a[j]] = [a[j], a[i]]; } return a; };
  BL.rand = (n) => (Math.random() * n) | 0;

  function toast(msg) {
    const t = $(".toast");
    t.textContent = msg; t.classList.add("show");
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 1800);
  }
  BL.toast = toast;

  BL.floatPts = (parent, x, y, text, bad) => {
    const el = h(`<div class="float-pts${bad ? " bad" : ""}">${text}</div>`);
    el.style.left = x + "px"; el.style.top = y + "px";
    parent.appendChild(el); setTimeout(() => el.remove(), 950);
  };

  /* confetti */
  BL.confetti = function (count = 120) {
    const cv = $("#confetti"), app = $("#app");
    const W = (cv.width = app.clientWidth * devicePixelRatio), H = (cv.height = app.clientHeight * devicePixelRatio);
    const g = cv.getContext("2d");
    const cols = ["#FFC83D", "#F2A900", "#1FB5A3", "#FF6B6B", "#9B8CFF", "#FFE08A"];
    const ps = Array.from({ length: count }, () => ({
      x: W / 2 + (Math.random() - 0.5) * W * 0.3, y: H * 0.55, vx: (Math.random() - 0.5) * 16 * devicePixelRatio,
      vy: -(Math.random() * 18 + 10) * devicePixelRatio, r: (Math.random() * 6 + 4) * devicePixelRatio,
      c: cols[BL.rand(cols.length)], rot: Math.random() * 6, vr: (Math.random() - 0.5) * 0.4, shape: BL.rand(2),
    }));
    let f = 0;
    (function loop() {
      g.clearRect(0, 0, W, H);
      ps.forEach((p) => {
        p.vy += 0.55 * devicePixelRatio; p.vx *= 0.99; p.x += p.vx; p.y += p.vy; p.rot += p.vr;
        g.save(); g.translate(p.x, p.y); g.rotate(p.rot); g.fillStyle = p.c;
        g.globalAlpha = Math.max(0, 1 - f / 140);
        if (p.shape) g.fillRect(-p.r / 2, -p.r / 4, p.r, p.r / 2); else { g.beginPath(); g.arc(0, 0, p.r / 2.4, 0, 7); g.fill(); }
        g.restore();
      });
      if (++f < 150) requestAnimationFrame(loop); else g.clearRect(0, 0, W, H);
    })();
  };

  BL.countdown = async function (parent) {
    const ov = h('<div class="countdown"></div>');
    parent.appendChild(ov);
    for (const n of [3, 2, 1]) {
      ov.innerHTML = `<b>${n}</b>`;
      BL.sfx.tone(n === 1 ? 880 : 660, { dur: 0.12, vol: 0.14 });
      await BL.wait(800);
    }
    ov.style.transition = "opacity .25s"; ov.style.opacity = "0";
    BL.sfx.tone(1175, { type: "triangle", dur: 0.2, vol: 0.16 });
    await BL.wait(220); ov.remove();
  };

  /* ---------------- registry ---------------- */
  BL.register = (g) => games.push(g);

  /* ---------------- shared countdown timer (used by timed games) ----------------
     const t = BL.timer(api, 60, { onEnd, onTick }); t.add(-3) to penalise, t.left() */
  BL.timer = function (api, seconds, { onEnd, onTick, el } = {}) {
    let end = Date.now() + seconds * 1000, stopped = false, last = Math.ceil(seconds), paused = 0;
    const bar = el || null;
    const t = {
      left: () => (paused ? paused : Math.max(0, end - Date.now())) / 1000,
      add(sec) { end += sec * 1000; if (bar) { bar.classList.remove("bump-plus", "bump-minus"); void bar.offsetWidth; bar.classList.add(sec > 0 ? "bump-plus" : "bump-minus"); } },
      pause() { if (!paused) paused = end - Date.now(); },
      resume() { if (paused) { end = Date.now() + paused; paused = 0; } },
      stop() { stopped = true; },
    };
    (function tick() {
      if (stopped || !api.alive()) return;
      const left = t.left();
      if (bar) {
        const fill = bar.querySelector("i"); if (fill) fill.style.transform = `scaleX(${Math.min(1, left / seconds)})`;
        bar.classList.toggle("low", left < 10);
        const num = bar.querySelector("b"); if (num) num.textContent = Math.ceil(left);
      }
      const sec = Math.ceil(left);
      if (sec < last && sec <= 5 && sec > 0) BL.sfx.tick();
      last = sec;
      onTick && onTick(left);
      if (left <= 0) { stopped = true; onEnd && onEnd(); return; }
      requestAnimationFrame(tick);
    })();
    return t;
  };
  BL.combo = (parent, text) => { const el = h(`<div class="combo">${text}</div>`); parent.appendChild(el); setTimeout(() => el.remove(), 950); };
  BL.levelBanner = (parent, small, big) => { const el = h(`<div class="level-banner"><div><small>${small}</small><b>${big}</b></div></div>`); parent.appendChild(el); BL.sfx.whoosh(); setTimeout(() => el.remove(), 1750); };
  BL.timerBarHTML = (id = "tBar") => `<div class="t-bar" id="${id}"><div class="t-track"><i></i></div><b>60</b></div>`;

  /* ---------------- hub ---------------- */
  function greeting() {
    const hr = new Date().getHours();
    return hr < 5 ? "Late night, sharp mind" : hr < 12 ? "Good morning" : hr < 17 ? "Good afternoon" : "Good evening";
  }
  function renderHub() {
    const s = BL.store.summary;
    const done = new Set(s.daily_done || []);
    const nDone = games.filter((g) => done.has(g.id)).length;
    const hub = $("#hub");
    hub.innerHTML = `
      <div class="hub-head" style="display:flex;align-items:flex-start;gap:10px">
        <div style="flex:1">
          <div class="hello">${greeting()}${s.name ? ", " + esc(s.name) : ""} ✨</div>
          <h1 class="hub-title">Your <em>Mind Gym</em></h1>
        </div>
        <button class="icon-btn" id="lbBtn" aria-label="Leaderboard">${BL.ico.trophy}</button>
        <button class="icon-btn" id="muteBtn" aria-label="Sound">${BL.sfx.muted ? BL.ico.mute : BL.ico.sound}</button>
      </div>
      <div class="scroll">
        <div class="stats-row">
          <div class="stat hot"><b>${s.streak_days || 0}🔥</b><span>day streak</span></div>
          <div class="stat"><b>${s.plays_today || 0}</b><span>played today</span></div>
          <div class="stat"><b>${s.minutes_today || 0}<small style="font-size:13px;font-weight:600"> min</small></b><span>trained today</span></div>
        </div>
        <div class="daily">
          <div style="flex:1">
            <div class="daily-k">DAILY CHALLENGE · ${new Date().toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</div>
            <div class="daily-t">${nDone === games.length ? "All done today. Legend 👑" : nDone ? `${nDone} of ${games.length} done, keep going` : "Same puzzles for everyone today"}</div>
            <div class="daily-dots">${games.map((g) => `<i class="${done.has(g.id) ? "on" : ""}"></i>`).join("")}</div>
          </div>
          <div class="daily-ring" style="--p:${(nDone / games.length) * 100}"><span>${nDone}/${games.length}</span></div>
        </div>
        <div class="section-label">Games · about 1 min each</div>
        <div class="game-list"></div>
        <div class="tip"><span style="font-size:18px">💡</span><span>Your first Daily Challenge run each day counts for the leaderboard. Replays are practice.</span></div>
      </div>`;
    const list = $(".game-list", hub);
    games.forEach((g, i) => {
      const best = s.best[g.id];
      const bestTxt = best != null && g.formatBest ? g.formatBest(best) : null;
      const card = h(`
        <button class="game-card" style="animation-delay:${80 + i * 70}ms;--tint:${g.tint}">
          <div class="game-icon">${g.icon}</div>
          <div class="game-meta">
            <div class="game-name">${g.name}</div>
            <div class="game-tag">${g.tag}</div>
            <div class="chips">${done.has(g.id) ? '<span class="chip done">✓ Daily</span>' : '<span class="chip daily-chip">Daily open</span>'}${(g.chips || []).map((c) => `<span class="chip">${c}</span>`).join("")}${bestTxt ? `<span class="chip best">★ ${bestTxt}</span>` : ""}</div>
          </div>
          <div class="go">${BL.ico.arrow}</div>
        </button>`);
      card.onclick = () => { BL.sfx.unlock(); BL.sfx.tap(); BL.haptic(8); location.hash = g.id; };
      list.appendChild(card);
    });
    $("#muteBtn").onclick = (e) => { const m = BL.sfx.toggle(); e.currentTarget.innerHTML = m ? BL.ico.mute : BL.ico.sound; if (!m) BL.sfx.tap(); };
    $("#lbBtn").onclick = () => { BL.sfx.tap(); location.hash = "leaderboard"; };
  }
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  BL.esc = esc;

  /* ---------------- game screen ---------------- */
  let current = null; // {game, cleanups:[]}
  function slideIn(scr) {
    $("#hub").classList.add("off-left");
    document.querySelectorAll(".screen.side").forEach((x) => x !== scr && x.classList.add("off-right"));
    scr.classList.remove("off-right");
  }
  function openGame(g) {
    closeGame(true);
    const scr = $("#game");
    scr.style.setProperty("--tint", g.tint);
    scr.innerHTML = `
      <div class="g-head">
        <button class="icon-btn" id="gBack" aria-label="Back">${BL.ico.back}</button>
        <div class="g-title">${g.name}</div>
        <div id="gPills" style="display:flex;gap:6px;align-items:center"></div>
      </div>
      <div class="g-body" id="gBody"></div>`;
    $("#gBack").onclick = () => { BL.sfx.tap(); location.hash = ""; };
    current = { game: g, cleanups: [] };
    showIntro(g);
    slideIn(scr);
  }
  function runCleanups() {
    if (!current) return;
    current.cleanups.forEach((f) => { try { f(); } catch (e) { console.error(e); } });
    current.cleanups = [];
  }
  function goHub() {
    document.querySelectorAll(".screen.side").forEach((x) => x.classList.add("off-right"));
    $("#hub").classList.remove("off-left");
    BL.store.refresh().then(renderHub);
  }
  function closeGame(silent) {
    runCleanups();
    current = null;
    if (!silent) goHub();
  }

  const DEFAULT_MODES = [["daily", "Daily challenge"], ["practice", "Practice"]];
  function showIntro(g) {
    runCleanups();
    $("#gPills").innerHTML = "";
    const body = $("#gBody");
    const it = g.intro;
    const opts = {};
    const done = (BL.store.summary.daily_done || []).includes(g.id);
    body.innerHTML = "";
    const card = h(`
      <div class="intro">
        <div class="big-icon">${g.icon}</div>
        <h2>${g.name}</h2>
        <p>${it.desc}</p>
        <ul class="how">${it.how.map((x, i) => `<li><i>${i + 1}</i><span>${x}</span></li>`).join("")}</ul>
        <div class="opts"></div>
        <div class="mode-note" id="modeNote"></div>
        <button class="btn" id="startBtn">${it.cta || "Let’s go"}</button>
        ${it.science ? `<div class="science">🧠 ${it.science}</div>` : ""}
      </div>`);
    const modes = g.modes || DEFAULT_MODES;
    const allOpts = [{ key: "mode", values: modes }, ...(it.options || [])];
    const note = () => {
      const m = opts.mode;
      $("#modeNote", card).innerHTML = m === "daily"
        ? done ? "✓ Today’s daily is done. This run will be <b>practice</b>." : "🏆 Same puzzle for everyone today. <b>Counts for the leaderboard.</b>"
        : m === "calm" ? "🌿 No timer, no score. Just colour." : "🎲 New random puzzle every time.";
    };
    allOpts.forEach((o) => {
      const saved = LS.get(`opt_${g.id}_${o.key}`, o.values[0][0]);
      opts[o.key] = o.values.some(([v]) => String(v) === String(saved)) ? saved : o.values[0][0];
      if (o.key === "mode" && !done) opts.mode = modes[0][0]; // daily first while it's open
      const seg = h(`<div class="seg">${o.values.map(([v, l]) => `<button data-v="${v}" class="${String(v) === String(opts[o.key]) ? "on" : ""}">${l}</button>`).join("")}</div>`);
      seg.querySelectorAll("button").forEach((b) => (b.onclick = () => {
        BL.sfx.tap(); seg.querySelectorAll("button").forEach((x) => x.classList.remove("on")); b.classList.add("on");
        const raw = b.dataset.v; opts[o.key] = isNaN(raw) ? raw : +raw; LS.set(`opt_${g.id}_${o.key}`, opts[o.key]); note();
      }));
      $(".opts", card).appendChild(seg);
    });
    note();
    body.appendChild(card);
    $("#startBtn", card).onclick = () => { BL.sfx.unlock(); BL.sfx.good(); BL.haptic(12); start(g, opts); };
  }

  function start(g, opts) {
    const body = $("#gBody");
    body.innerHTML = "";
    $("#gPills").innerHTML = "";
    const t0 = Date.now();
    const doneDaily = (BL.store.summary.daily_done || []).includes(g.id);
    const mode = opts.mode === "daily" && doneDaily ? "practice" : opts.mode || "practice";
    const seedMode = opts.mode === "daily" ? "daily" : mode; // replays of daily still get today's puzzle
    const api = {
      body, opts, mode,
      rng: BL.rng(BL.seedFor(g.id, seedMode)),
      pills: $("#gPills"),
      onCleanup: (f) => current && current.cleanups.push(f),
      later(fn, ms) { const id = setTimeout(fn, ms); api.onCleanup(() => clearTimeout(id)); return id; },
      every(fn, ms) { const id = setInterval(fn, ms); api.onCleanup(() => clearInterval(id)); return id; },
      alive: () => current && current.game === g && api._alive,
      _alive: true,
      async finish(r) {
        if (!api._alive) return;
        api._alive = false;
        const duration_s = Math.round((Date.now() - t0) / 1000);
        let saved = { isBest: false, best: null };
        if (!r.noSave) saved = await BL.store.save({ game: g.id, mode, score: Math.max(0, Math.round(r.score)), level: r.level ?? null, duration_s, meta: r.meta || null });
        showResult(g, r, saved, opts, mode);
      },
    };
    api.onCleanup(() => (api._alive = false));
    current.cleanups.push(g.start(body, api, opts) || (() => {}));
  }

  function showResult(g, r, saved, opts, mode) {
    if (!current) return;
    const s = BL.store.summary;
    const rankLine = saved.rank
      ? `<div class="rank-line">🏅 You’re <b>#${saved.rank}</b> of ${saved.players} today</div>`
      : mode === "daily" ? `<div class="rank-line">🏆 Daily challenge score saved</div>` : mode === "practice" ? `<div class="rank-line muted">Practice run · doesn’t count for the leaderboard</div>` : "";
    const askName = mode === "daily" && !s.name;
    const wrap = h(`
      <div class="sheet-wrap"><div class="sheet">
        <div class="grab"></div>
        <div class="medal">${r.emoji || (saved.isBest ? "🏆" : "⭐")}</div>
        ${saved.isBest && !r.noSave && r.score > 0 ? '<div class="new-best">NEW PERSONAL BEST</div>' : ""}
        <h3>${r.title || "Nice work!"}</h3>
        <div class="sub">${r.sub || ""}</div>
        ${r.big != null ? `<div class="score-big">${r.big}</div>` : ""}
        ${rankLine}
        ${r.stats ? `<div class="kv">${r.stats.map(([k, v]) => `<div><b>${v}</b><span>${k}</span></div>`).join("")}</div>` : '<div style="height:14px"></div>'}
        ${askName ? `<div class="name-row"><input id="nmIn" maxlength="20" placeholder="Your name for the leaderboard" autocomplete="off"><button class="btn" id="nmSave" style="width:auto;padding:12px 16px">Save</button></div>` : ""}
        <div class="btn-row">
          <button class="btn ghost" id="rHome">Games</button>
          <button class="btn" id="rAgain">${BL.ico.restart}&nbsp;${r.againLabel || "Play again"}</button>
        </div>
        ${r.extraBtn ? `<button class="btn dark" id="rExtra" style="margin-top:10px">${r.extraBtn.label}</button>` : mode !== "calm" ? `<button class="btn dark" id="rLb" style="margin-top:10px">${BL.ico.trophy}&nbsp;Leaderboard</button>` : ""}
      </div></div>`);
    $("#game").appendChild(wrap);
    requestAnimationFrame(() => requestAnimationFrame(() => wrap.classList.add("show")));
    if (saved.isBest && r.score > 0 && !r.noSave) { BL.sfx.win(); setTimeout(() => BL.confetti(), 250); }
    else if (r.celebrate) { BL.sfx.win(); setTimeout(() => BL.confetti(80), 250); }
    const close = (fn) => { wrap.classList.remove("show"); setTimeout(() => { wrap.remove(); fn(); }, 380); };
    $("#rHome", wrap).onclick = () => { BL.sfx.tap(); close(() => (location.hash = "")); };
    $("#rAgain", wrap).onclick = () => { BL.sfx.good(); close(() => start(g, { ...opts, mode: opts.mode })); };
    if (r.extraBtn) $("#rExtra", wrap).onclick = () => { BL.sfx.tap(); r.extraBtn.onClick(); };
    if ($("#rLb", wrap)) $("#rLb", wrap).onclick = () => { BL.sfx.tap(); BL.lbGame = g.id; location.hash = "leaderboard"; };
    if (askName) {
      $("#nmSave", wrap).onclick = async () => {
        const v = $("#nmIn", wrap).value.trim();
        const res = await BL.store.setName(v);
        if (res.ok) { BL.store.summary.name = res.name; $(".name-row", wrap).outerHTML = `<div class="rank-line">👋 Saved as <b>${esc(res.name)}</b></div>`; BL.sfx.good(); }
        else BL.toast(res.error || "Try another name");
      };
    }
    current.cleanups.push(() => wrap.remove());
  }

  /* ---------------- leaderboard screen ---------------- */
  let lbState = { game: null, period: "today" };
  async function openLeaderboard() {
    closeGame(true);
    const scr = $("#lb");
    lbState.game = BL.lbGame || lbState.game || games[0].id;
    BL.lbGame = null;
    scr.innerHTML = `
      <div class="g-head">
        <button class="icon-btn" id="lbBack" aria-label="Back">${BL.ico.back}</button>
        <div class="g-title">Leaderboard</div>
        <button class="icon-btn" id="lbName" aria-label="Edit name" style="width:auto;padding:0 12px;font-size:13px;font-weight:600">✎ ${esc(BL.store.summary.name || "Set name")}</button>
      </div>
      <div class="lb-tabs" id="lbTabs">${games.map((g) => `<button data-g="${g.id}" style="--tint:${g.tint}"><span>${g.icon}</span>${g.name}</button>`).join("")}</div>
      <div style="padding:0 20px"><div class="seg" id="lbPer" style="width:100%;display:grid;grid-template-columns:repeat(3,1fr)"><button data-p="today">Today</button><button data-p="week">This week</button><button data-p="all">All time</button></div></div>
      <div class="scroll" id="lbList"></div>`;
    $("#lbBack").onclick = () => { BL.sfx.tap(); location.hash = ""; };
    $("#lbName").onclick = () => {
      BL.sfx.tap();
      if ($("#lbNameRow")) return $("#lbNameRow").remove();
      const row = h(`<div class="name-row" id="lbNameRow" style="margin:0 20px 12px"><input maxlength="20" placeholder="Your leaderboard name" value="${esc(BL.store.summary.name || "")}"><button class="btn" style="width:auto;padding:12px 16px">Save</button></div>`);
      $("#lbList").before(row); $("input", row).focus();
      $("button", row).onclick = async () => {
        const res = await BL.store.setName($("input", row).value.trim());
        if (res.ok) { BL.store.summary.name = res.name; $("#lbName").textContent = "✎ " + res.name; row.remove(); BL.sfx.good(); loadBoard(); } else BL.toast(res.error);
      };
    };
    scr.querySelectorAll("#lbTabs button").forEach((b) => (b.onclick = () => { BL.sfx.tap(); lbState.game = b.dataset.g; loadBoard(); }));
    scr.querySelectorAll("#lbPer button").forEach((b) => (b.onclick = () => { BL.sfx.tap(); lbState.period = b.dataset.p; loadBoard(); }));
    slideIn(scr);
    loadBoard();
  }
  async function loadBoard() {
    const scr = $("#lb");
    scr.querySelectorAll("#lbTabs button").forEach((b) => b.classList.toggle("on", b.dataset.g === lbState.game));
    scr.querySelectorAll("#lbPer button").forEach((b) => b.classList.toggle("on", b.dataset.p === lbState.period));
    const on = scr.querySelector("#lbTabs button.on"), tabs = $("#lbTabs"); if (on) tabs.scrollTo({ left: on.offsetLeft - tabs.clientWidth / 2 + on.offsetWidth / 2, behavior: "smooth" });
    const list = $("#lbList");
    list.innerHTML = `<div class="lb-empty">Loading…</div>`;
    const g = games.find((x) => x.id === lbState.game);
    const data = await BL.store.leaderboard(lbState.game, lbState.period);
    if (!data) { list.innerHTML = `<div class="lb-empty">🔌 The leaderboard needs the Mind Gym server.<br>Run <b>app.py</b> and open it from there.</div>`; return; }
    if (!data.top.length) { list.innerHTML = `<div class="lb-empty">No daily scores yet for ${g.name}.<br><b>Be the first one up here 🚀</b></div>`; return; }
    const medal = (r) => (r === 1 ? "🥇" : r === 2 ? "🥈" : r === 3 ? "🥉" : r);
    const fmt = g.formatBest || ((x) => x);
    list.innerHTML = `
      <div class="lb-count">${data.players} player${data.players > 1 ? "s" : ""} · daily challenge</div>
      ${data.top.map((e, i) => `<div class="lb-row${e.me ? " me" : ""}${e.rank <= 3 ? " top" : ""}" style="animation-delay:${i * 40}ms"><span class="lb-rank">${medal(e.rank)}</span><span class="lb-name">${esc(e.name)}${e.me ? " <small>(you)</small>" : ""}</span><span class="lb-score">${fmt(e.score)}</span></div>`).join("")}
      ${data.me && data.me.rank > data.top.length ? `<div class="lb-row me" style="margin-top:10px"><span class="lb-rank">${data.me.rank}</span><span class="lb-name">You</span><span class="lb-score">${fmt(data.me.score)}</span></div>` : ""}
      ${!data.me ? `<div class="lb-empty" style="padding:18px 0 0">Play today’s Daily Challenge to get on the board.</div>` : ""}`;
  }

  /* ---------------- routing ---------------- */
  function route() {
    const id = location.hash.replace("#", "");
    if (id === "leaderboard") return openLeaderboard();
    const g = games.find((x) => x.id === id);
    if (g) openGame(g);
    else closeGame();
  }

  BL.boot = async function () {
    renderHub();
    window.addEventListener("hashchange", route);
    document.addEventListener("visibilitychange", () => { if (document.hidden && ctx) ctx.suspend(); else if (ctx) ctx.resume(); });
    await BL.store.refresh();
    if (location.hash) route(); else renderHub();
  };
})();
