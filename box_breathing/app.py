"""
BeLiving - Box Breathing (visual version)
Run:  python app.py      -> opens in your browser at http://localhost:8003

A calm voice settles you in, a silent 3-2-1 countdown, then "Inhale, Hold, Exhale, Hold"
around the box over soft ocean waves.
"""
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import box_breathing

PORT = 8003

PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Box Breathing · BeLiving</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
<style>
/* Layout: BeLiving app screen system (Beat the Clock / 7-Min Sprint / Body Double): cream page, white cards, BeLiving yellow with navy text, light-teal info box. One phone-width column. Single light look by design, matching the app. */
:root{
  --bg:#F3F0EB; --surface:#FFFFFF; --sunk:#F7F4EE; --ink:#2F3A4A; --text:#3A3A3A; --muted:#8C8C8C; --line:#E4DFD6;
  --yellow:#F9D468; --yellow-soft:#FDF3D6; --yellow-deep:#E9B93A;
  --teal-bg:#DEEFF1; --teal-line:#86C9D1; --teal-text:#5F7275;
  --in:#F9D468; --hold:#F9D468; --out:#F9D468; --on-accent:#2F3A4A;
  --font:"Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
  color-scheme:light;
}
*{box-sizing:border-box}
html,body{background:var(--bg)}
body{color:var(--text);font:15px/1.5 var(--font);margin:0;-webkit-font-smoothing:antialiased}
.screen{max-width:440px;margin:0 auto;padding-block:20px 48px;padding-left:max(18px,env(safe-area-inset-left,0px));padding-right:max(18px,env(safe-area-inset-right,0px));display:flex;flex-direction:column;gap:16px}
button,input{font:inherit;color:inherit}
button{cursor:pointer}
:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.mono{font-variant-numeric:tabular-nums}

.head{display:flex;flex-direction:column;gap:2px}
.eyebrow{font-size:15px;color:var(--muted)}
h1{margin:0;font-size:26px;font-weight:500;color:var(--ink);letter-spacing:-.01em}
.info{background:var(--teal-bg);border:1.5px solid var(--teal-line);border-radius:10px;padding:12px 14px;font-size:13px;line-height:1.5;color:var(--teal-text)}

.card{background:var(--surface);border-radius:16px;padding:16px;box-shadow:0 2px 6px rgba(0,0,0,.06)}
.stage-card{display:flex;flex-direction:column;gap:12px}
.stage-head{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.stage-head h2{margin:0;font-size:18px;font-weight:600;color:var(--ink)}
.stage-head .mono{font-size:13px;color:var(--muted)}
.stage{position:relative;width:100%;aspect-ratio:1;max-width:100%}
.stage canvas{display:block;width:100%;height:100%}
.done{position:absolute;inset:17%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;text-align:center;padding:16px;border-radius:16px;background:var(--surface);box-shadow:0 10px 30px rgba(0,0,0,.12)}
.done[hidden]{display:none}
.done h3{margin:0;font-size:18px;font-weight:600;color:var(--ink)}
.done .big{font-size:44px;font-weight:700;line-height:1;color:var(--ink);background:var(--yellow);border-radius:999px;padding:6px 20px}
.done p{margin:0;color:var(--muted);font-size:13.5px}
.progress{height:6px;border-radius:999px;background:var(--sunk);overflow:hidden}
.progress span{display:block;height:100%;width:0;background:var(--yellow);border-radius:inherit}
.stage-foot{display:flex;justify-content:space-between;gap:10px;font-size:13px;color:var(--muted)}

.actions{display:flex;gap:10px}
.btn-main{flex:1;height:54px;border:0;border-radius:999px;background:var(--yellow);color:var(--ink);font-size:16px;font-weight:600;box-shadow:0 2px 6px rgba(0,0,0,.08)}
.btn-main:active{transform:scale(.985)}
.btn-main:disabled{opacity:.6}
.btn-alt{height:54px;padding:0 22px;border:0;border-radius:999px;background:#E9E6E0;color:var(--ink);font-weight:600}

.field{display:flex;flex-direction:column;gap:8px}
.label{font-size:14px;font-weight:500;color:var(--ink)}
.pills{display:flex;flex-wrap:wrap;gap:8px}
.pills button{border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:8px 16px;font-size:14px;font-weight:500;color:var(--text);font-variant-numeric:tabular-nums}
.pills button[aria-pressed="true"]{background:var(--yellow);border-color:var(--yellow);color:var(--ink);font-weight:600}
.pills button:disabled{cursor:not-allowed;opacity:.5}
.settings{display:flex;flex-direction:column;gap:16px}
.vol{display:flex;align-items:center;gap:12px}
.vol .vname{width:3.6em;font-size:14px;color:var(--text)}
.vol input{flex:1;min-width:0;accent-color:var(--yellow-deep)}
.vol .mono{font-size:13px;color:var(--muted);width:3ch;text-align:right}
.toggle-row{display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:14px}
.switch{width:46px;height:28px;border-radius:999px;border:0;background:#DCD8D1;position:relative;flex:none;transition:background .2s}
.switch::after{content:"";position:absolute;top:3px;left:3px;width:22px;height:22px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.2);transition:transform .2s}
.switch[aria-pressed="true"]{background:var(--yellow-deep)}
.switch[aria-pressed="true"]::after{transform:translateX(18px)}

.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.stat{background:var(--surface);border-radius:14px;padding:12px;display:flex;flex-direction:column;gap:2px;box-shadow:0 2px 6px rgba(0,0,0,.06);min-width:0}
.stat .v{font-size:24px;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums;line-height:1.15}
.stat .k{font-size:12px;color:var(--muted)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media (prefers-reduced-motion:reduce){.switch,.switch::after{transition:none}}
</style>

</head><body>
<main class="screen">
  <div class="head">
    <span class="eyebrow">Mindfulness</span>
    <h1>Box Breathing</h1>
  </div>
  <div class="info">Breathe in, hold, breathe out, hold. Follow the dot around the box and let the voice guide you. Headphones sound best.</div>

  <section class="card stage-card">
    <div class="stage-head">
      <h2 id="phase-title">Ready when you are</h2>
      <span class="mono" id="clock">0:00 / 2:56</span>
    </div>
    <div class="stage">
      <canvas id="cv" aria-hidden="true"></canvas>
      <div class="done" id="done" hidden>
        <h3>Session complete</h3>
        <div class="big mono" id="done-boxes">11</div>
        <p id="done-meta">boxes in 2:56</p>
        <p>Notice your shoulders and jaw. Softer?</p>
      </div>
    </div>
    <div class="progress" aria-hidden="true"><span id="bar"></span></div>
    <div class="stage-foot"><span id="box-count">11 boxes this session</span><span class="mono" id="bpm">3.75 breaths/min</span></div>
  </section>

  <div class="actions">
    <button class="btn-main" id="go" type="button">Begin</button>
    <button class="btn-alt" id="end" type="button" hidden>End</button>
  </div>
  <div class="sr" aria-live="polite" id="live"></div>

  <section class="card settings">
    <div class="field">
      <span class="label" id="pace-l">Seconds per side</span>
      <div class="pills" id="pace" role="group" aria-labelledby="pace-l">
        <button type="button" data-v="3" aria-pressed="false">3s</button>
        <button type="button" data-v="4" aria-pressed="true">4s</button>
        <button type="button" data-v="5" aria-pressed="false">5s</button>
        <button type="button" data-v="6" aria-pressed="false">6s</button>
      </div>
    </div>
    <div class="field">
      <span class="label" id="len-l">Session length</span>
      <div class="pills" id="len" role="group" aria-labelledby="len-l">
        <button type="button" data-v="1" aria-pressed="false">1 min</button>
        <button type="button" data-v="3" aria-pressed="true">3 min</button>
        <button type="button" data-v="5" aria-pressed="false">5 min</button>
        <button type="button" data-v="0" aria-pressed="false">Open</button>
      </div>
    </div>
    <div class="field">
      <span class="label">Sound</span>
      <label class="vol"><span class="vname">Voice</span>
        <input type="range" id="vol-voice" min="0" max="100" value="85" aria-label="Voice volume">
        <span class="mono" id="vol-voice-v">85</span>
      </label>
      <label class="vol"><span class="vname">Ocean</span>
        <input type="range" id="vol-ocean" min="0" max="100" value="35" aria-label="Ocean volume">
        <span class="mono" id="vol-ocean-v">35</span>
      </label>
    </div>
    <div class="toggle-row"><span>Vibrate on each side</span><button type="button" class="switch" id="opt-haptics" aria-pressed="true" aria-label="Vibrate on each side"></button></div>
  </section>

  <div class="stats">
    <div class="stat"><span class="v" id="st-min">0</span><span class="k">Minutes today</span></div>
    <div class="stat"><span class="v" id="st-ses">0</span><span class="k">Sessions</span></div>
    <div class="stat"><span class="v" id="st-streak">0</span><span class="k">Day streak</span></div>
  </div>
</main>
<script>
(() => {
  const $ = id => document.getElementById(id);
  const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp01 = t => Math.max(0, Math.min(1, t));
  const ease = t => 0.5 - 0.5 * Math.cos(Math.PI * clamp01(t));

  const PH = [
    { label: 'Breathe in',  side: 'INHALE', tok: 'in' },
    { label: 'Hold',        side: 'HOLD',   tok: 'hold' },
    { label: 'Breathe out', side: 'EXHALE', tok: 'out' },
    { label: 'Hold',        side: 'HOLD',   tok: 'hold' }
  ];
  let COUNT_STEP = 1.5; // seconds per number in the 3-2-1 countdown (from the server plan)
  const cfg = { pace: 4, minutes: 3, haptics: true, voice: 0.85, ocean: 0.35 };
  const CLIP_NAMES = ['inhale', 'exhale', 'hold', 'intro', 'outro'];
  let PLAN = null;
  const api = async (path, body) => { const r = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}); return r.json(); };

  /* ---------- theme tokens for canvas ---------- */
  const tok = {};
  const hexRgb = h => { h = (h || '#000').trim().replace('#', ''); if (h.length === 3) h = h.split('').map(c => c + c).join(''); const n = parseInt(h, 16) || 0; return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
  function readTokens() { const cs = getComputedStyle(document.documentElement); ['bg','surface','sunk','ink','muted','line','in','hold','out','on-accent'].forEach(k => tok[k] = hexRgb(cs.getPropertyValue('--' + k))); }
  readTokens();
  try { matchMedia('(prefers-color-scheme: dark)').addEventListener('change', readTokens); } catch (e) {}
  try { new MutationObserver(readTokens).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] }); } catch (e) {}
  const rgba = (c, a) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
  const mix = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];

  /* ---------- audio: voice clips + ocean, all on the audio clock ---------- */
  const A = {
    ctx: null, buf: null, sess: null,
    ensure() {
      if (this.ctx) return this.ctx;
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      let c; try { c = new AC({ latencyHint: 'interactive' }); } catch (e) { try { c = new AC(); } catch (e2) { return null; } }
      this.ctx = c;
      const comp = c.createDynamicsCompressor();
      comp.threshold.value = -12; comp.knee.value = 10; comp.ratio.value = 2.5; comp.attack.value = 0.005; comp.release.value = 0.25;
      comp.connect(c.destination); this.out = comp;
      try { const b = c.createBuffer(1, 1, c.sampleRate), s = c.createBufferSource(); s.buffer = b; s.connect(c.destination); s.start(); } catch (e) {}
      return c;
    },
    async load() {
      if (this.buf) return this.buf;
      const c = this.ctx, out = {};
      await Promise.all(CLIP_NAMES.map(async k => {
        const ab = await (await fetch('/audio/' + k + '.wav')).arrayBuffer();
        out[k] = await new Promise((res, rej) => { const p = c.decodeAudioData(ab, res, rej); if (p && p.catch) p.catch(rej); });
      }));
      this.buf = out; this.ocean = this.makeNoise(); return out;
    },
    makeNoise() {
      const c = this.ctx, len = c.sampleRate * 8, nb = c.createBuffer(2, len, c.sampleRate);
      for (let ch = 0; ch < 2; ch++) {
        const d = nb.getChannelData(ch); let last = 0;
        for (let i = 0; i < len; i++) { const w = Math.random() * 2 - 1; last = (last + 0.02 * w) / 1.02; d[i] = last * 3.2; }
        const f = Math.floor(c.sampleRate * 0.25);
        for (let i = 0; i < f; i++) { const k = i / f; d[i] = d[i] * k + d[len - f + i] * (1 - k); }
      }
      return nb;
    },
    gainOf(name) { return name === 'voice' ? cfg.voice ** 1.5 : (cfg.ocean ** 1.5) * 0.9; },
    setLevel(name) { const s = this.sess; if (s && this.ctx) s[name].gain.setTargetAtTime(this.gainOf(name), this.ctx.currentTime, 0.03); },
    begin(t0) {
      const c = this.ctx, s = { bus: c.createGain(), voice: c.createGain(), ocean: c.createGain(), srcs: [], waveUntil: t0 };
      s.bus.connect(this.out); s.voice.connect(s.bus); s.ocean.connect(s.bus);
      s.voice.gain.value = this.gainOf('voice');
      s.ocean.gain.value = this.gainOf('ocean');
      s.bus.gain.setValueAtTime(0, t0); s.bus.gain.linearRampToValueAtTime(1, t0 + 2.5);
      // ocean: brown-noise body + a little foam, both swelling with each wave
      const body = c.createBufferSource(); body.buffer = this.ocean; body.loop = true;
      s.lp = c.createBiquadFilter(); s.lp.type = 'lowpass'; s.lp.frequency.value = 400; s.lp.Q.value = 0.2;
      s.swell = c.createGain(); s.swell.gain.value = 0.3;
      body.connect(s.lp); s.lp.connect(s.swell); s.swell.connect(s.ocean);
      const foam = c.createBufferSource(); foam.buffer = this.ocean; foam.loop = true; foam.playbackRate.value = 2.7;
      const hp = c.createBiquadFilter(); hp.type = 'bandpass'; hp.frequency.value = 2600; hp.Q.value = 0.5;
      s.foam = c.createGain(); s.foam.gain.value = 0;
      foam.connect(hp); hp.connect(s.foam); s.foam.connect(s.ocean);
      body.start(t0); foam.start(t0, 1.3); s.srcs.push(body, foam);
      this.sess = s; return s;
    },
    waves(horizon) {
      const s = this.sess;
      while (s.waveUntil < horizon) {
        const t = s.waveUntil, d = 7 + Math.random() * 4, peak = 0.7 + Math.random() * 0.3, n = 96;
        const sw = new Float32Array(n), lf = new Float32Array(n), fm = new Float32Array(n);
        for (let i = 0; i < n; i++) {
          const x = i / (n - 1);
          const rise = x < 0.42 ? ease(x / 0.42) : 1 - ease((x - 0.42) / 0.58);
          sw[i] = 0.3 + (peak - 0.3) * rise;
          lf[i] = 320 + 900 * rise * peak;
          fm[i] = 0.16 * Math.pow(Math.max(0, rise - 0.55) / 0.45, 1.5) * peak;
        }
        s.waveUntil = t + d + 0.03; // small gap so consecutive curves never touch
        try {
          s.swell.gain.setValueCurveAtTime(sw, t, d);
          s.lp.frequency.setValueCurveAtTime(lf, t, d);
          s.foam.gain.setValueCurveAtTime(fm, t, d);
        } catch (e) {}
      }
    },
    play(name, t, fade) {
      const c = this.ctx, b = this.buf && this.buf[name]; if (!b || !this.sess) return 0;
      const src = c.createBufferSource(); src.buffer = b;
      const g = c.createGain();
      if (fade) { g.gain.setValueAtTime(1, t); g.gain.setValueAtTime(1, t + 0.45); g.gain.linearRampToValueAtTime(0.75, t + b.duration); }
      src.connect(g); g.connect(this.sess.voice); src.start(t);
      return b.duration;
    },
    phase(i, t, P) {
      const p = i % 4;
      // words start 60 ms early: the ear hears a word's beat slightly after its first sound
      const at = Math.max(this.ctx.currentTime, t - 0.06);
      this.play(p === 0 ? 'inhale' : p === 2 ? 'exhale' : 'hold', at, false);
    },
    stop(delay) {
      const s = this.sess, c = this.ctx; if (!s || !c) return;
      this.sess = null;
      const at = c.currentTime + (delay || 0);
      try { s.bus.gain.cancelScheduledValues(c.currentTime); s.bus.gain.setValueAtTime(s.bus.gain.value, c.currentTime); s.bus.gain.setValueAtTime(s.bus.gain.value, at); s.bus.gain.linearRampToValueAtTime(0, at + (delay ? 2.5 : 0.25)); } catch (e) {}
      setTimeout(() => { s.srcs.forEach(x => { try { x.stop(); } catch (e) {} }); try { s.bus.disconnect(); } catch (e) {} }, ((delay || 0) + 3) * 1000);
    }
  };

  /* ---------- clock: the time you are hearing right now ---------- */
  const Clock = {
    mode: 'perf', last: 0, pausedAt: 0, pausedTotal: 0,
    now() {
      if (this.mode === 'ctx') {
        const c = A.ctx;
        if (c.state !== 'running') return this.last;
        let v;
        if (c.getOutputTimestamp) {
          try {
            const ts = c.getOutputTimestamp();
            if (ts && ts.performanceTime > 0 && ts.contextTime > 0) {
              const x = ts.contextTime + (performance.now() - ts.performanceTime) / 1000;
              if (Math.abs(x - c.currentTime) < 0.5) v = x;
            }
          } catch (e) {}
        }
        if (v === undefined) v = c.currentTime - (c.outputLatency || c.baseLatency || 0);
        this.last = Math.max(this.last, v);
        return this.last;
      }
      const p = this.pausedAt ? this.pausedAt : performance.now();
      return (p - this.pausedTotal) / 1000;
    }
  };

  /* ---------- session ---------- */
  const S = { status: 'idle', start: 0, P: 4, total: Infinity, next: 0, lastI: -2, elapsed: 0 };

  function scheduler() {
    if (Clock.mode !== 'ctx' || !A.sess || (S.status !== 'run' && S.status !== 'paused')) return;
    const horizon = A.ctx.currentTime + 2.0;
    while (S.next < S.total) {
      const t = S.start + S.next * S.P;
      if (t > horizon) break;
      const i = S.next++;
      try { A.phase(i, t, S.P); } catch (e) {}
    }
    try { A.waves(horizon + 10); } catch (e) {}
    if (S.next >= S.total && !S.outro) { A.play('outro', S.start + S.total * S.P + 0.3, false); S.outro = true; }
  }
  setInterval(scheduler, 50);

  let wake = null;
  async function wakeOn() { try { if (navigator.wakeLock) wake = await navigator.wakeLock.request('screen'); } catch (e) { wake = null; } }
  function wakeOff() { try { wake && wake.release(); } catch (e) {} wake = null; }
  const buzz = ms => { if (cfg.haptics) try { navigator.vibrate && navigator.vibrate(ms); } catch (e) {} };
  function lockControls(on) { document.querySelectorAll('#pace button, #len button').forEach(b => b.disabled = on); }

  async function begin() {
    const c0 = A.ensure();
    if (c0) { try { if (c0.state !== 'running') c0.resume(); } catch (e) {} }
    try { PLAN = await api(`/api/plan?pace=${cfg.pace}&minutes=${cfg.minutes}`); } catch (e) { PLAN = null; }
    S.P = cfg.pace;
    if (PLAN && PLAN.ok) {
      S.total = PLAN.boxes ? PLAN.boxes * 4 : Infinity;
      COUNT_STEP = PLAN.intro.countdown_step;
    } else S.total = cfg.minutes ? Math.max(1, Math.round(cfg.minutes * 60 / (4 * S.P))) * 4 : Infinity;
    S.next = 0; S.lastI = -2; S.elapsed = 0; S.outro = false;
    const c = A.ensure();
    if (c) { try { if (c.state !== 'running') c.resume(); } catch (e) {} }
    if (c && !A.buf) {
      S.status = 'loading'; $('go').textContent = 'Loading\u2026'; $('go').disabled = true;
      try { await (A.loading || A.load()); } catch (e) { A.buf = null; }
      $('go').disabled = false;
    }
    if (c && A.buf) {
      Clock.mode = 'ctx'; Clock.last = 0;
      const t0 = c.currentTime + 0.05;
      A.begin(t0);
      // slow intro, then "three, two, one" on the countdown ticks, then the first corner
      // calm spoken line, a short rest, then a silent on-screen countdown
      const introLen = A.play('intro', t0 + 0.3, false);
      S.start = t0 + 0.3 + introLen + 0.8 + 3 * COUNT_STEP;
      scheduler();
    } else {
      Clock.mode = 'perf'; Clock.pausedAt = 0; Clock.pausedTotal = 0;
      S.start = Clock.now() + 3 * COUNT_STEP;
      say('Sound could not start on this device. The visual guide still works.');
    }
    S.status = 'run';
    $('done').hidden = true; $('end').hidden = false; $('go').textContent = 'Pause';
    lockControls(true); wakeOn();
  }
  function pause() {
    S.status = 'paused'; $('go').textContent = 'Resume';
    if (Clock.mode === 'ctx') { try { A.ctx.suspend(); } catch (e) {} } else Clock.pausedAt = performance.now();
    say('Paused');
  }
  function resume() {
    S.status = 'run'; $('go').textContent = 'Pause';
    if (Clock.mode === 'ctx') { try { A.ctx.resume(); } catch (e) {} }
    else { Clock.pausedTotal += performance.now() - Clock.pausedAt; Clock.pausedAt = 0; }
  }
  function end(complete) {
    if (S.status === 'paused' && Clock.mode === 'ctx') { try { A.ctx.resume(); } catch (e) {} }
    const secs = S.elapsed;
    if (secs > 20) addStats(secs, complete);
    A.stop(complete ? 3.5 : 0);
    S.status = complete ? 'done' : 'idle'; S.lastI = -2;
    lockControls(false); wakeOff(); highlight(-1);
    $('end').hidden = true;
    $('go').textContent = complete ? 'Breathe again' : 'Begin';
    if (complete) {
      const boxes = Math.round(S.total / 4);
      $('done-boxes').textContent = boxes;
      $('done-meta').textContent = `box${boxes === 1 ? '' : 'es'} in ${fmt(secs)}`;
      $('done').hidden = false;
      buzz([60, 80, 60]);
      say('Session complete');
    }
    refreshMeta();
  }
  $('go').addEventListener('click', () => {
    if (S.status === 'loading') return;
    if (S.status === 'run') pause();
    else if (S.status === 'paused') resume();
    else begin();
  });
  $('end').addEventListener('click', () => end(false));
  document.addEventListener('keydown', e => {
    const tag = (e.target.tagName || '').toLowerCase();
    if (e.code === 'Space' && tag !== 'button' && tag !== 'input') { e.preventDefault(); $('go').click(); }
    if (e.key === 'Escape' && (S.status === 'run' || S.status === 'paused')) end(false);
  });

  /* ---------- settings ---------- */
  function seg(id, key) {
    $(id).addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b || b.disabled) return;
      cfg[key] = +b.dataset.v;
      $(id).querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
      refreshMeta();
    });
  }
  seg('pace', 'pace'); seg('len', 'minutes');
  $('opt-haptics').addEventListener('click', () => { cfg.haptics = !cfg.haptics; $('opt-haptics').setAttribute('aria-pressed', String(cfg.haptics)); });
  ['voice', 'ocean'].forEach(k => {
    $('vol-' + k).addEventListener('input', e => { cfg[k] = +e.target.value / 100; $('vol-' + k + '-v').textContent = e.target.value; A.setLevel(k); });
  });

  const fmt = s => { s = Math.max(0, Math.round(s)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
  function refreshMeta() {
    const cl = 4 * cfg.pace;
    const bpm = (60 / cl).toFixed(2).replace(/\.?0+$/, '');
    const boxes = cfg.minutes ? Math.max(1, Math.round(cfg.minutes * 60 / cl)) : 0;
    setText('bpm', `${bpm} breaths/min`);
    if (S.status === 'idle' || S.status === 'done') {
      setText('box-count', boxes ? `${boxes} boxes this session` : 'Open session, end any time');
      setText('clock', `0:00 / ${boxes ? fmt(boxes * cl) : '\u221e'}`);
      setText('phase-title', S.status === 'done' ? 'Nicely done' : 'Ready when you are');
      $('bar').style.width = S.status === 'done' ? '100%' : '0%';
    }
    document.querySelectorAll('#legend .v').forEach(v => v.textContent = cfg.pace + 's');
  }

  /* ---------- stats (this browser only) ---------- */
  const KEY = 'beliving-breathe-v1';
  const today = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };
  async function addStats(secs, completed) {
    try { const r = await api('/api/session', { seconds: secs, boxes: Math.floor(secs / (4 * S.P)), pace: S.P, completed: !!completed }); if (r && r.stats) showStats(r.stats); } catch (e) {}
  }
  async function showStats(st) {
    try { if (!st) st = await api('/api/stats'); } catch (e) { return; }
    $('st-min').textContent = st.minutes_today ?? 0;
    $('st-ses').textContent = st.sessions ?? 0;
    $('st-streak').textContent = st.streak ?? 0;
  }

  /* ---------- small UI helpers ---------- */
  const cache = {};
  function setText(id, v) { if (cache[id] !== v) { cache[id] = v; $(id).textContent = v; } }
  function say(t) { $('live').textContent = t; }
  function highlight(i) { document.querySelectorAll('#legend .leg').forEach(el => el.dataset.on = String(+el.dataset.i === i)); }

  /* ---------- canvas ---------- */
  const cv = $('cv'), g = cv.getContext('2d');
  let W = 0;
  function resize() {
    const r = cv.getBoundingClientRect(), dpr = Math.min(2, window.devicePixelRatio || 1);
    W = r.width; cv.width = Math.round(W * dpr); cv.height = Math.round(W * dpr);
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  try { new ResizeObserver(resize).observe(cv); } catch (e) { addEventListener('resize', resize); }
  resize();

  let cur = tok.in.slice();
  const ripples = [], bubbles = [];
  function rr(x, y, w, h, r) {
    g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
  }

  function draw(v, dt) {
    const s = W; if (!s) return;
    g.clearRect(0, 0, s, s);
    const target = v.p >= 0 ? tok[PH[v.p].tok] : tok.in;
    cur = mix(cur, target, 1 - Math.exp(-dt * 7));

    const pad = Math.max(54, s * 0.15), L = s - 2 * pad;
    const x0 = pad, y0 = pad, x1 = x0 + L, y1 = y0 + L, r = Math.min(22, L * 0.09);
    const o = Math.max(12, s * 0.034), cx = s / 2, cy = s / 2;
    const time = v.now / 1000;

    const halo = g.createRadialGradient(cx, cy, L * 0.25, cx, cy, s * 0.62);
    halo.addColorStop(0, rgba(cur, 0.10 + 0.12 * v.b)); halo.addColorStop(1, rgba(cur, 0));
    g.fillStyle = halo; g.fillRect(0, 0, s, s);

    rr(x0, y0, L, L, r); g.fillStyle = rgba(tok.sunk, 1); g.fill();

    let wave = null;
    if (v.b > 0.002) {
      const level = y1 - L * v.b;
      const amp = RM ? 0 : L * (v.moving ? 0.02 : 0.011);
      g.save(); rr(x0, y0, L, L, r); g.clip();
      g.beginPath(); g.moveTo(x0, y1 + 2);
      for (let x = x0; x <= x1 + 4; x += 4) g.lineTo(x, level - amp * 0.6 + amp * Math.sin((x - x0) / L * Math.PI * 2.4 + time * 1.5 + 1.3));
      g.lineTo(x1 + 4, y1 + 2); g.closePath(); g.fillStyle = rgba(cur, 0.30); g.fill();

      wave = new Path2D(); wave.moveTo(x0 - 2, y1 + 2);
      for (let x = x0 - 2; x <= x1 + 4; x += 4) wave.lineTo(x, level + amp * Math.sin((x - x0) / L * Math.PI * 2 - time * 2.0) + amp * 0.35 * Math.sin((x - x0) / L * Math.PI * 6.2 + time * 1.2));
      wave.lineTo(x1 + 4, y1 + 2); wave.closePath();
      const wg = g.createLinearGradient(0, level - amp, 0, y1);
      wg.addColorStop(0, rgba(cur, 0.95)); wg.addColorStop(1, rgba(mix(cur, [233, 185, 58], 0.55), 1));
      g.fillStyle = wg; g.fill(wave);

      if (!RM && v.active && v.b > 0.12 && Math.random() < (v.moving ? 0.22 : 0.07)) bubbles.push({ x: 0.1 + Math.random() * 0.8, y: 0, r: 1.5 + Math.random() * 3, sp: 0.12 + Math.random() * 0.2, ph: Math.random() * 6 });
      g.save(); g.clip(wave);
      g.strokeStyle = 'rgba(255,255,255,0.75)'; g.lineWidth = 1.3;
      for (let i = bubbles.length - 1; i >= 0; i--) {
        const bb = bubbles[i]; bb.y += bb.sp * dt;
        if (bb.y > v.b - 0.02) { bubbles.splice(i, 1); continue; }
        const bx = x0 + L * bb.x + Math.sin(time * 3 + bb.ph) * 3, by = y1 - L * bb.y;
        g.beginPath(); g.arc(bx, by, bb.r, 0, Math.PI * 2); g.stroke();
      }
      g.restore();
      g.restore();
    } else bubbles.length = 0;

    const fsC = Math.round(L * 0.36), fsL = Math.max(13, Math.round(L * 0.07));
    const text = (cNum, cLab) => {
      g.textAlign = 'center'; g.textBaseline = 'middle';
      g.font = `600 ${fsC}px Inter, system-ui, sans-serif`;
      g.fillStyle = cNum; g.fillText(v.count, cx, cy - fsL * 0.55);
      g.font = `500 ${fsL}px Inter, system-ui, sans-serif`;
      g.fillStyle = cLab; g.fillText(v.label, cx, v.count ? cy + fsC * 0.46 : cy);
    };
    text(rgba(tok.ink, 1), rgba(tok.muted, 1));
    if (wave) { g.save(); rr(x0, y0, L, L, r); g.clip(); g.clip(wave); text(rgba(tok['on-accent'], 1), rgba(tok['on-accent'], 0.9)); g.restore(); }

    for (let i = ripples.length - 1; i >= 0; i--) {
      const rp = ripples[i], a = (v.now - rp.t0) / 1400;
      if (a > 1) { ripples.splice(i, 1); continue; }
      const grow = o + ease(a) * Math.min(26, pad - o - 6);
      rr(x0 - grow, y0 - grow, L + grow * 2, L + grow * 2, r + grow);
      g.strokeStyle = rgba(rp.c, 0.35 * (1 - a)); g.lineWidth = 2; g.stroke();
    }

    const tx0 = x0 - o, ty0 = y0 - o, tx1 = x1 + o, ty1 = y1 + o;
    const C = [[tx0, ty1], [tx0, ty0], [tx1, ty0], [tx1, ty1], [tx0, ty1]];
    g.lineCap = 'round'; g.lineJoin = 'round'; g.lineWidth = Math.max(5, s * 0.013);
    g.strokeStyle = rgba(tok.line, 1);
    g.beginPath(); g.moveTo(tx0, ty1); g.lineTo(tx0, ty0); g.lineTo(tx1, ty0); g.lineTo(tx1, ty1); g.closePath(); g.stroke();
    let ox = tx0, oy = ty1;
    if (v.p >= 0) {
      for (let k2 = 0; k2 <= v.p; k2++) {
        const f = k2 < v.p ? 1 : v.t, [ax, ay] = C[k2], [bx, by] = C[k2 + 1];
        const ex = ax + (bx - ax) * f, ey = ay + (by - ay) * f;
        g.strokeStyle = rgba(tok[PH[k2].tok], 1);
        g.beginPath(); g.moveTo(ax, ay); g.lineTo(ex, ey); g.stroke();
        if (k2 === v.p) { ox = ex; oy = ey; }
      }
    }

    const fs = Math.max(10, Math.round(s * 0.025)), lo = Math.max(15, s * 0.042);
    g.font = `600 ${fs}px Inter, system-ui, sans-serif`;
    if ('letterSpacing' in g) g.letterSpacing = '1.5px';
    g.textAlign = 'center'; g.textBaseline = 'middle';
    [[tx0 - lo, cy, -Math.PI / 2], [cx, ty0 - lo, 0], [tx1 + lo, cy, Math.PI / 2], [cx, ty1 + lo, 0]].forEach(([lx, ly, rot], i) => {
      g.save(); g.translate(lx, ly); g.rotate(rot);
      g.fillStyle = i === v.p ? rgba(tok.ink, 1) : rgba(tok.muted, 0.7);
      g.fillText(`${PH[i].side} \u00b7 ${v.pace}s`, 0, 0);
      g.restore();
    });
    if ('letterSpacing' in g) g.letterSpacing = '0px';

    const orr = Math.max(8, s * 0.024) * (1 + 0.14 * v.pulse);
    const og = g.createRadialGradient(ox, oy, 0, ox, oy, orr * 3.4);
    og.addColorStop(0, rgba(cur, 0.4)); og.addColorStop(1, rgba(cur, 0));
    g.fillStyle = og; g.beginPath(); g.arc(ox, oy, orr * 3.4, 0, Math.PI * 2); g.fill();
    g.fillStyle = rgba(tok.surface, 1); g.beginPath(); g.arc(ox, oy, orr, 0, Math.PI * 2); g.fill();
    g.strokeStyle = rgba(cur, 1); g.lineWidth = 3; g.stroke();
    g.fillStyle = rgba(tok.ink, 1); g.beginPath(); g.arc(ox, oy, orr * 0.38, 0, Math.PI * 2); g.fill();
  }

  /* ---------- frame loop ---------- */
  let lastT = performance.now();
  function frame(now) {
    const dt = Math.min(0.05, (now - lastT) / 1000); lastT = now;
    const v = { now, b: 0, p: -1, t: 0, count: String(cfg.pace), label: 'Ready', moving: false, active: false, pulse: 0.5 + 0.5 * Math.sin(now / 420), pace: cfg.pace };

    if (S.status === 'run' || S.status === 'paused') {
      v.pace = S.P;
      const e = Clock.now() - S.start;
      if (e < 0) {
        v.b = 0;
        if (-e > 3 * COUNT_STEP) { v.count = ''; v.label = 'Relax your shoulders'; setText('phase-title', 'Relax your shoulders'); }
        else { v.count = String(Math.ceil(-e / COUNT_STEP)); v.label = 'Starting in'; setText('phase-title', 'Starting in\u2026'); }
        setText('clock', `0:00 / ${S.total < Infinity ? fmt(S.total * S.P) : '\u221e'}`);
      } else if (e >= S.total * S.P) {
        S.elapsed = S.total * S.P; end(true);
      } else {
        S.elapsed = e;
        const i = Math.floor(e / S.P), p = i % 4, t = (e - i * S.P) / S.P;
        v.p = p; v.t = t;
        v.b = p === 0 ? ease(t) : p === 1 ? 1 : p === 2 ? 1 - ease(t) : 0;
        v.moving = p === 0 || p === 2; v.active = S.status === 'run';
        v.pulse = v.b;
        v.count = String(Math.min(S.P, Math.floor(t * S.P) + 1));
        v.label = S.status === 'paused' ? 'Paused' : PH[p].label;
        if (i !== S.lastI) {
          S.lastI = i;
          if (!RM) ripples.push({ t0: now, c: tok[PH[p].tok] });
          buzz(p === 0 ? 40 : 18);
          highlight(p); say(PH[p].label);
          $('bar').style.background = `var(--${PH[p].tok})`;
        }
        setText('phase-title', S.status === 'paused' ? 'Paused' : PH[p].label);
        const box = Math.floor(i / 4) + 1;
        setText('box-count', S.total < Infinity ? `Box ${box} of ${S.total / 4}` : `Box ${box}`);
        setText('clock', `${fmt(e)} / ${S.total < Infinity ? fmt(S.total * S.P) : '\u221e'}`);
        $('bar').style.width = S.total < Infinity ? (100 * e / (S.total * S.P)).toFixed(2) + '%' : '0%';
      }
    } else {
      v.b = S.status === 'done' ? 0 : 0.55 + 0.035 * Math.sin(now / 1300);
      v.label = S.status === 'done' ? 'Done' : 'Ready';
      $('phase-title').style.color = '';
      $('bar').style.background = '';
    }
    draw(v, dt);
    requestAnimationFrame(frame);
  }

  refreshMeta(); showStats(); highlight(-1);
  // decode the voice before the first tap so Begin starts straight away
  try { if (A.ensure()) { A.loading = A.load(); A.loading.catch(() => {}); } } catch (e) {}
  requestAnimationFrame(frame);
})();
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, kind="application/json"):
        data = body if isinstance(body, bytes) else (
            body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8"))
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store" if kind != "audio/wav" else "max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if url.path == "/api/plan":
            q = parse_qs(url.query)
            return self._send(200, box_breathing.plan(q.get("pace", [box_breathing.DEFAULT_PACE])[0],
                                                      q.get("minutes", [box_breathing.DEFAULT_LENGTH])[0]))
        if url.path == "/api/stats":
            return self._send(200, box_breathing.stats())
        if url.path.startswith("/audio/"):
            name = url.path.rsplit("/", 1)[-1]
            f = box_breathing.AUDIO_DIR / name
            if name.endswith(".wav") and "/" not in name and "\\" not in name and f.is_file():
                return self._send(200, f.read_bytes(), "audio/wav")
        self._send(404, {"error": "Not found"})

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            if self.path == "/api/session":
                return self._send(200, box_breathing.record(body.get("seconds", 0), body.get("boxes", 0),
                                                            body.get("pace", box_breathing.DEFAULT_PACE),
                                                            bool(body.get("completed"))))
            self._send(404, {"error": "Not found"})
        except Exception as e:
            print(f"\n  \u26a0  {type(e).__name__}: {str(e)[:300]}\n")
            self._send(500, {"ok": False, "error": "SERVER_ERROR", "message": "Something went wrong. Try again."})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    url = f"http://localhost:{PORT}"
    print(f"\n  \U0001F32C  BeLiving Box Breathing running at {url}")
    print("  Keep this window open. Press Ctrl + C to stop.\n")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except OSError:
        print(f"  Port {PORT} is busy. Close the other Box Breathing window and try again.")
    except KeyboardInterrupt:
        print("\n  Stopped.")
