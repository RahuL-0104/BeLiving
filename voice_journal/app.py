"""
BeLiving - Voice Journal (visual version)
Run:  python app.py      -> opens in your browser at http://localhost:8001

Record your voice -> see the transcript -> get your journal -> save it.
Saved journals go in the entries folder.
"""
import json
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from voice_journal import MODEL, make_journal, transcribe

PORT = 8001
ENTRIES = Path(__file__).resolve().parent / "entries"

PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voice Journal · BeLiving</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Lora:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root{
  --page:#2c2c2c;          /* canvas around the phone */
  --bg:#f3f0eb;            /* screen cream */
  --ink:#1e1e1e;
  --text:#3a3a3a;
  --muted:#8c8c8c;
  --yellow:#f9d468;
  --yellow-soft:#fdf3d6;
  --teal-bg:#deeff1;
  --teal-line:#86c9d1;
  --white:#ffffff;
  --line:#dcd8d1;
  --green:#5f9e75; --green-soft:#e3f1e7;
  --red:#c0614b;   --red-soft:#f8e4de;
  --navy:#2f3a4a;
  --shadow:0 2px 6px rgba(0,0,0,.08);
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--page);font-family:Inter,system-ui,sans-serif;color:var(--text);
  min-height:100vh;display:flex;justify-content:center;align-items:flex-start;padding:24px 12px}
.phone{width:393px;max-width:100%;min-height:852px;background:var(--bg);border-radius:28px;
  padding:48px 22px 40px;position:relative;overflow:hidden}
@media (max-width:430px){body{padding:0}.phone{border-radius:0;min-height:100vh}}

.back{width:28px;height:28px;display:block;margin-bottom:18px;cursor:pointer;background:none;border:0;color:var(--ink)}
.eyebrow{font-size:15px;color:var(--muted);margin-bottom:6px}
h1{font-size:26px;font-weight:500;color:var(--ink);letter-spacing:-.01em}
.info{background:var(--teal-bg);border:1.5px solid var(--teal-line);border-radius:10px;
  padding:13px 15px;font-size:12.5px;line-height:1.5;color:#5f7275;margin:20px 0 22px}
.label{font-size:15px;font-weight:600;color:var(--ink);margin:0 0 12px}
.hidden{display:none!important}

/* what to talk about */
.guide{display:flex;flex-direction:column;gap:9px}
.g{display:flex;gap:12px;align-items:flex-start;background:var(--white);border-radius:10px;box-shadow:var(--shadow);padding:12px 13px}
.g .ic{flex:0 0 30px;height:30px;border-radius:8px;background:var(--yellow-soft);display:grid;place-items:center;font-size:15px}
.g b{display:block;font-size:13.5px;font-weight:600;color:var(--ink);margin-bottom:2px}
.g span{font-size:12px;color:var(--muted);line-height:1.4}
.skip{font-size:11.5px;color:var(--muted);margin-top:10px;text-align:center}

/* recorder */
.rec{display:flex;flex-direction:column;align-items:center;margin-top:26px}
.mic{width:84px;height:84px;border-radius:50%;border:0;background:var(--yellow);color:var(--ink);display:grid;place-items:center;
  cursor:pointer;box-shadow:0 4px 14px rgba(249,212,104,.55);position:relative}
.mic svg{width:32px;height:32px}
.mic.on{background:var(--red);color:#fff;box-shadow:none}
.mic.on::after{content:"";position:absolute;inset:-8px;border-radius:50%;border:2px solid var(--red);animation:ring 1.4s ease-out infinite}
@keyframes ring{from{transform:scale(.95);opacity:.9}to{transform:scale(1.3);opacity:0}}
.clock{font-size:26px;font-weight:600;color:var(--navy);margin-top:14px;font-variant-numeric:tabular-nums}
.cap{font-size:10px;letter-spacing:.08em;color:var(--muted);text-transform:uppercase;margin-top:3px}
.bars{display:flex;gap:3px;height:20px;align-items:center;margin-top:10px}
.bars i{width:4px;border-radius:2px;background:var(--yellow);height:20%}
.link{display:block;width:100%;text-align:center;background:none;border:0;font:inherit;font-size:13px;
  color:var(--muted);margin-top:14px;cursor:pointer}
.link u{color:var(--ink)}

/* transcript */
.field{width:100%;min-height:190px;resize:vertical;background:var(--white);border:1px solid var(--line);
  border-radius:12px;padding:14px;font:inherit;font-size:14px;line-height:1.55;color:var(--ink);outline:none}
.field:focus{border-color:#b9b4ab}
.meta{display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);margin-top:8px}

.cta{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;border:0;
  background:var(--yellow);color:var(--ink);font:inherit;font-weight:600;font-size:14px;
  border-radius:10px;padding:14px;cursor:pointer;margin-top:22px}
.cta:disabled{opacity:.55;cursor:default}
.cta svg{width:16px;height:16px}
.err{margin-top:14px;background:#fbe9e6;border:1px solid #efc3bb;color:#9a4a3d;border-radius:10px;padding:11px 14px;font-size:12px}
.wait{display:flex;flex-direction:column;align-items:center;gap:14px;margin:70px 0 30px;color:var(--muted);font-size:13px;text-align:center}
.spin{width:14px;height:14px;border:2px solid #0003;border-top-color:var(--ink);border-radius:50%;animation:s .7s linear infinite}
.wait .spin{width:34px;height:34px;border-width:3px;border-color:var(--yellow-soft);border-top-color:var(--yellow)}
@keyframes s{to{transform:rotate(360deg)}}

/* journal: diary page + at a glance */
.paper{margin-top:18px;background:#fffdf8;border-radius:14px;box-shadow:0 2px 10px rgba(0,0,0,.07);
  padding:22px 20px 20px;position:relative}
.paper .date{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.paper h2{font-family:Lora,Georgia,serif;font-weight:600;font-size:22px;line-height:1.25;color:var(--ink);margin:6px 0 12px}
.paper .entry{font-family:Lora,Georgia,serif;font-size:15.5px;line-height:28px;color:#2b2b2b;white-space:pre-line;
  background-image:repeating-linear-gradient(transparent 0 27px,#ece5d9 27px 28px)}
.mood-tag{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--text);background:var(--bg);border-radius:999px;padding:4px 10px;margin-top:14px}
.mood-tag i{width:9px;height:9px;border-radius:50%}
.glance{margin-top:24px}
.glance h3{font-size:13px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:8px}
.gl{background:var(--white);border-radius:12px;box-shadow:var(--shadow);overflow:hidden}
.li{display:flex;gap:12px;padding:12px 14px;border-top:1px solid #f0ece5}
.li:first-child{border-top:0}
.li .e{flex:0 0 22px;font-size:16px;line-height:1.3;text-align:center}
.li .b{flex:1;min-width:0}
.li .t{font-size:11.5px;color:var(--muted);margin-bottom:2px}
.li .d{font-size:14px;color:var(--ink);line-height:1.45;overflow-wrap:anywhere}
.li .s{font-size:12.5px;color:var(--muted);margin-top:3px;line-height:1.4}
.ok{color:var(--green);font-weight:600} .no{color:var(--red);font-weight:600}
.guilt{display:inline-flex;gap:3px;vertical-align:middle;margin-left:6px}
.guilt i{width:8px;height:8px;border-radius:50%;background:#e4dfd6}
.guilt i.on{background:var(--red)}
.missing{font-size:12px;color:var(--muted);margin-top:12px;line-height:1.5}
.missing b{font-weight:600;color:var(--text)}
.from{margin-top:20px;display:flex;gap:10px;align-items:flex-start;background:var(--yellow-soft);border-radius:12px;padding:13px 14px}
.from .e{font-size:16px}
.from p{font-size:13.5px;color:var(--ink);line-height:1.5}
.from small{display:block;font-size:11px;color:#9a7615;font-weight:600;margin-bottom:2px;letter-spacing:.03em}
.support{margin-top:16px;background:var(--red-soft);border:1.5px solid var(--red);border-radius:10px;padding:13px 15px;font-size:13px;color:var(--ink);line-height:1.5}

/* saved */
.center{text-align:center}
.win-emoji{font-size:60px;margin:70px 0 14px}
.past{margin-top:30px;text-align:left}
.pe{display:flex;gap:10px;align-items:center;padding:11px 13px;margin-top:8px;background:var(--white);border-radius:10px;box-shadow:var(--shadow);cursor:pointer;width:100%;border:0;font:inherit;text-align:left}
.pe b{display:block;font-size:13px;color:var(--ink);font-weight:600}
.pe span{display:block;font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pe .tx{min-width:0;flex:1}
.pe .md{flex:0 0 12px;height:12px;border-radius:50%}
.foot{position:absolute;bottom:12px;left:0;right:0;text-align:center;font-size:10px;color:#b3aea6}
</style></head><body><div class="phone">

<!-- ========== 1. RECORD ========== -->
<section id="s-record">
  <p class="eyebrow">AI Voice Journal</p>
  <h1>How was today?</h1>
  <div class="info">Tap the mic and talk for 30–60 seconds, like a voice note to a friend. We'll write your journal for you.</div>

  <p class="label">Talk about these 4 things</p>
  <div class="guide">
    <div class="g"><span class="ic">🍽️</span><div><b>Food</b><span>What did you eat? Any cheat meal, and how guilty did you feel, 0 to 5?</span></div></div>
    <div class="g"><span class="ic">🏃</span><div><b>Fitness</b><span>Which goals did you hit today? Which did you miss, and why?</span></div></div>
    <div class="g"><span class="ic">🙂</span><div><b>Mood</b><span>How did you feel? Could you handle it? What set you off?</span></div></div>
    <div class="g"><span class="ic">🎯</span><div><b>Focus</b><span>Was it easy to start tasks? What distracted you? What helped?</span></div></div>
  </div>
  <p class="skip">Skip anything that doesn't apply today.</p>

  <div class="rec">
    <button class="mic" id="mic" aria-label="Start recording">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="9" y="2.5" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3.5"/></svg>
    </button>
    <div class="bars hidden" id="bars"></div>
    <div class="clock" id="clock">0:00</div>
    <div class="cap" id="cap">Tap to record</div>
  </div>
  <div id="err1" class="err hidden"></div>
  <button class="link" id="uploadBtn">or <u>upload a voice note</u></button>
  <input type="file" id="file" accept="audio/*" hidden>
  <button class="link" id="typeBtn">or <u>type it instead</u></button>
  <div class="past" id="pastHome"></div>
</section>

<!-- ========== 2. TRANSCRIPT ========== -->
<section id="s-text" class="hidden">
  <button class="back" id="back2" aria-label="Back"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M11 6l-6 6 6 6"/></svg></button>
  <p class="eyebrow">Step 2 of 3</p>
  <h1>Check your words</h1>
  <div id="txWait" class="wait"><span class="spin"></span>Turning your voice into text…<br>This takes a few seconds.</div>
  <div id="txReady" class="hidden">
    <div class="info">This is what we heard. Fix any wrong words, then make your journal.</div>
    <textarea id="transcript" class="field" placeholder="e.g. Breakfast was poha, lunch was dal rice. Had pizza as my cheat meal, felt a bit guilty, 2 out of 5. Did my run but skipped yoga. Mood was low after a work call…"></textarea>
    <div class="meta"><span id="words">0 words</span><span>Step 3 makes the journal</span></div>
    <button class="cta" id="make">Make my journal <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button>
    <div id="err2" class="err hidden"></div>
    <button class="link" id="again">Record again</button>
  </div>
</section>

<!-- ========== 3. JOURNAL ========== -->
<section id="s-journal" class="hidden">
  <button class="back" id="back3" aria-label="Back"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M11 6l-6 6 6 6"/></svg></button>
  <p class="eyebrow">Step 3 of 3</p>
  <h1>Your Journal</h1>
  <div id="jWait" class="wait"><span class="spin"></span>Writing your journal…</div>
  <div id="jBody"></div>
  <div id="jActions" class="hidden">
    <button class="cta" id="save">Save to my journal <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12l5 5 9-10"/></svg></button>
    <button class="link" id="new3">Start a new entry</button>
  </div>
</section>

<!-- ========== 4. SAVED ========== -->
<section id="s-saved" class="hidden center">
  <div class="win-emoji">📓</div>
  <h1>Saved.</h1>
  <div class="info">One more day on record. Small check-ins add up.</div>
  <button class="cta" id="new4">New entry <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button>
  <div class="past" id="past"></div>
</section>

<p class="foot">BeLiving · Voice Journal</p>
</div>
<script>
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const SCREENS = ["record","text","journal","saved"];
function show(n){ SCREENS.forEach(s => $("s-"+s).classList.toggle("hidden", s !== n)); window.scrollTo(0,0); }
const MAX_SECONDS = 300;
const MOOD = {1:["Awful","#c0614b"],2:["Low","#d99a6c"],3:["Okay","#a3a09a"],4:["Good","#5f9e75"],5:["Great","#e2b53e"]};
const today = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0,10); };
const pretty = iso => new Date(iso + "T12:00:00").toLocaleDateString("en-IN", {weekday:"long", day:"numeric", month:"long"});
function err(id, msg){ $(id).textContent = msg; $(id).classList.toggle("hidden", !msg); }

async function api(path, opts){
  let r;
  try { r = await fetch(path, opts); } catch { throw new Error("Can't reach the journal. Is run.bat still open?"); }
  let d = null; try { d = await r.json(); } catch {}
  if (!r.ok) throw new Error((d && d.error) || "Something went wrong. Please try again.");
  return d;
}

/* ---------- 1. record ---------- */
let rec = null, stream = null, chunks = [], t0 = 0, tick = null, actx = null, raf = null;
for (let i = 0; i < 18; i++) $("bars").appendChild(document.createElement("i"));
const fmt = s => `${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,"0")}`;

async function startRec(){
  err("err1", "");
  try { stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true, noiseSuppression:true}}); }
  catch { err("err1", "Microphone is blocked. Click the lock icon in the address bar and allow the microphone."); return; }
  chunks = []; rec = new MediaRecorder(stream);
  rec.ondataavailable = e => e.data.size && chunks.push(e.data);
  rec.onstop = () => {
    stream.getTracks().forEach(t => t.stop()); cancelAnimationFrame(raf); try { actx.close(); } catch {}
    const secs = (Date.now() - t0) / 1000; resetRec();
    if (secs < 2) { err("err1", "That was too short. Tap the mic and talk a little longer."); return; }
    handleAudio(new Blob(chunks, {type: rec.mimeType || "audio/webm"}));
  };
  rec.start(1000); t0 = Date.now();
  $("mic").classList.add("on"); $("mic").setAttribute("aria-label","Stop recording");
  $("cap").textContent = "Listening… tap to stop"; $("bars").classList.remove("hidden");
  tick = setInterval(() => { const s = (Date.now() - t0) / 1000; $("clock").textContent = fmt(s); if (s >= MAX_SECONDS) stopRec(); }, 250);
  try {
    actx = new AudioContext(); const an = actx.createAnalyser(); an.fftSize = 64;
    actx.createMediaStreamSource(stream).connect(an);
    const data = new Uint8Array(an.frequencyBinCount), bars = $("bars").children;
    const loop = () => { an.getByteFrequencyData(data); for (let i = 0; i < bars.length; i++) bars[i].style.height = Math.max(20, data[i+2] / 2.55) + "%"; raf = requestAnimationFrame(loop); };
    loop();
  } catch {}
}
function stopRec(){ clearInterval(tick); if (rec && rec.state !== "inactive") rec.stop(); }
function resetRec(){
  clearInterval(tick); $("mic").classList.remove("on"); $("mic").setAttribute("aria-label","Start recording");
  $("clock").textContent = "0:00"; $("cap").textContent = "Tap to record"; $("bars").classList.add("hidden");
}
$("mic").onclick = () => (rec && rec.state === "recording") ? stopRec() : startRec();
$("uploadBtn").onclick = () => $("file").click();
$("file").onchange = e => { const f = e.target.files[0]; e.target.value = ""; if (f) handleAudio(f); };
$("typeBtn").onclick = () => { show("text"); $("txWait").classList.add("hidden"); $("txReady").classList.remove("hidden"); $("transcript").value = ""; countWords(); $("transcript").focus(); };

/* any recording -> 16 kHz mono WAV (small, and every speech model reads it) */
async function toWav(blob){
  const ctx = new AudioContext(); const audio = await ctx.decodeAudioData(await blob.arrayBuffer()); ctx.close();
  const rate = 16000, len = Math.max(1, Math.ceil(audio.duration * rate));
  const off = new OfflineAudioContext(1, len, rate); const src = off.createBufferSource();
  src.buffer = audio; src.connect(off.destination); src.start();
  const pcm = (await off.startRendering()).getChannelData(0);
  const buf = new ArrayBuffer(44 + pcm.length * 2), v = new DataView(buf);
  const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  w(0,"RIFF"); v.setUint32(4, 36 + pcm.length*2, true); w(8,"WAVE"); w(12,"fmt "); v.setUint32(16,16,true); v.setUint16(20,1,true);
  v.setUint16(22,1,true); v.setUint32(24,rate,true); v.setUint32(28,rate*2,true); v.setUint16(32,2,true); v.setUint16(34,16,true);
  w(36,"data"); v.setUint32(40,pcm.length*2,true);
  for (let i = 0; i < pcm.length; i++){ const s = Math.max(-1, Math.min(1, pcm[i])); v.setInt16(44 + i*2, s < 0 ? s*0x8000 : s*0x7fff, true); }
  return {wav: new Blob([buf], {type:"audio/wav"}), seconds: audio.duration};
}

/* ---------- 2. transcript ---------- */
async function handleAudio(blob){
  show("text"); $("txWait").classList.remove("hidden"); $("txReady").classList.add("hidden"); err("err2", "");
  try {
    const {wav, seconds} = await toWav(blob);
    if (seconds > MAX_SECONDS + 5) throw new Error("Voice notes can be up to 5 minutes. Try a shorter one.");
    const {text} = await api("transcribe", {method:"POST", headers:{"Content-Type":"audio/wav"}, body:wav});
    $("transcript").value = text; countWords();
    $("txWait").classList.add("hidden"); $("txReady").classList.remove("hidden");
  } catch (e) {
    show("record"); err("err1", e.message.includes("decode") ? "Couldn't read that audio file. Try another one." : e.message);
  }
}
function countWords(){ const n = $("transcript").value.trim().split(/\s+/).filter(Boolean).length; $("words").textContent = n + (n === 1 ? " word" : " words"); }
$("transcript").addEventListener("input", countWords);
$("again").onclick = $("back2").onclick = () => show("record");

/* ---------- 3. journal ---------- */
let current = null;
$("make").onclick = async () => {
  const text = $("transcript").value.trim();
  if (text.split(/\s+/).length < 4) { err("err2", "Say or type a bit more about your day."); return; }
  err("err2", ""); show("journal");
  $("jWait").classList.remove("hidden"); $("jBody").innerHTML = ""; $("jActions").classList.add("hidden");
  try {
    current = await api("journal", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({text, date: today()})});
    renderJournal(current, true);
  } catch (e) { show("text"); err("err2", e.message); }
};
$("back3").onclick = () => $("jActions").classList.contains("hidden") ? show("record") : show("text");

function renderJournal(e, fresh){
  const f = e.food || {}, cm = f.cheat_meal || {}, goals = (e.fitness || {}).goals || [], m = e.mind || {}, a = e.adhd || {};
  const li = (emoji, title, main, sub = "") => `<div class="li"><span class="e">${emoji}</span><div class="b"><div class="t">${title}</div><div class="d">${main}</div>${sub ? `<div class="s">${sub}</div>` : ""}</div></div>`;
  const join = arr => arr.map(esc).join(", ");
  const md = MOOD[m.mood_1_to_5];
  let h = "";

  if (e.needs_support) h += `<div class="support"><b>You don't have to carry this alone.</b><br>Talk to someone now: Tele-MANAS is free and open 24x7. Call <b>14416</b> or 1-800-891-4416.</div>`;

  // the diary page
  h += `<div class="paper">
    <div class="date">${esc(e.date ? pretty(e.date) : "Today")}</div>
    <h2>${esc(e.title || e.summary || "Today")}</h2>
    <div class="entry">${esc(e.entry || e.transcript || "")}</div>
    ${md ? `<span class="mood-tag"><i style="background:${md[1]}"></i>Feeling ${md[0].toLowerCase()}</span>` : ""}
  </div>`;

  // at a glance: only what was talked about
  let g = "", missing = [];

  const meals = f.meals || [];
  if (meals.length) g += li("🍽️", "What I ate", meals.map(x => esc(x.items)).join(" · "));
  if (cm.had_cheat_meal) {
    const n = Number.isFinite(cm.guilt_0_to_5) ? cm.guilt_0_to_5 : null;
    const guilt = n === null ? "" : n === 0 ? `No guilt 🙌` :
      `Guilt ${n}/5 <span class="guilt">${[1,2,3,4,5].map(i => `<i class="${i <= n ? "on" : ""}"></i>`).join("")}</span>`;
    g += li("🍟", "Cheat meal", esc(cm.what || "Yes") + (guilt ? ` &nbsp;·&nbsp; ${guilt}` : ""), cm.kind_note && n >= 2 ? `“${esc(cm.kind_note)}”` : "");
  }
  if (!meals.length && !cm.had_cheat_meal) missing.push("food");

  if (goals.length) {
    const hit = goals.filter(x => x.status === "achieved").length;
    g += li("🏃", `Fitness · ${hit} of ${goals.length} done`,
      goals.map(x => x.status === "achieved" ? `<span class="ok">✓</span> ${esc(x.goal)}` : `<span class="no">✕</span> ${esc(x.goal)}${x.reason ? ` <span style="color:var(--muted)">(${esc(x.reason)})</span>` : ""}`).join("<br>"));
  } else missing.push("workouts");

  const feel = [md ? md[0] : null, ...(m.emotions || []).filter(x => !md || x.toLowerCase() !== md[0].toLowerCase())].filter(Boolean);
  const handled = {able:"I handled my emotions well", partly:"I struggled a bit, but got through it", unable:"My emotions got the better of me today"}[m.handled_emotions];
  if (feel.length || handled) g += li("🙂", "How I felt", esc(feel.join(", ")) || "", handled || "");
  if ((m.triggers || []).length) g += li("⚡", "What set me off", join(m.triggers));
  if (!feel.length && !handled && !(m.triggers || []).length) missing.push("mood");

  const focusBits = [];
  if (a.focus_1_to_5) focusBits.push(`${a.focus_1_to_5}/5 · ${a.focus_1_to_5 >= 4 ? "locked in" : a.focus_1_to_5 <= 2 ? "scattered" : "okay"}`);
  if (a.task_start) focusBits.push(a.task_start === "easy" ? "Easy to get started" : "Hard to get started");
  const focusSub = [(a.distractions || []).length ? "Distracted by " + join(a.distractions) : "", (a.what_helped || []).length ? "Helped: " + join(a.what_helped) : ""].filter(Boolean).join("<br>");
  if (focusBits.length || focusSub) g += li("🎯", "Focus", focusBits.join(" · ") || "&nbsp;", focusSub);
  else missing.push("focus");

  if (g) h += `<div class="glance"><h3>At a glance</h3><div class="gl">${g}</div>`
    + (missing.length ? `<p class="missing">Not mentioned today: <b>${missing.join(", ")}</b>. Mention them next time for a fuller picture.</p>` : "") + `</div>`;

  if (e.reflection) h += `<div class="from"><span class="e">💛</span><p><small>FROM BELIVING</small>${esc(e.reflection)}</p></div>`;

  $("jWait").classList.add("hidden"); $("jBody").innerHTML = h;
  $("jActions").classList.toggle("hidden", !fresh);
  $("save").disabled = false;
}

/* ---------- 4. save ---------- */
$("save").onclick = async () => {
  $("save").disabled = true;
  try { await api("save", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(current)}); show("saved"); loadPast(); }
  catch (e) { $("save").disabled = false; alert(e.message); }
};
$("new3").onclick = $("new4").onclick = () => { current = null; show("record"); loadPast(); };

let past = [];
async function loadPast(){
  try { past = await api("entries"); } catch { past = []; }
  const list = past.map((e, i) => {
    const md = MOOD[(e.mind || {}).mood_1_to_5];
    return `<button class="pe" data-i="${i}"><span class="md" style="background:${md ? md[1] : "#e4dfd6"}"></span><span class="tx"><b>${esc(e.date ? pretty(e.date) : "Entry")}</b><span>${esc(e.summary || e.transcript || "")}</span></span></button>`;
  }).join("");
  const title = `<p class="label" style="margin-top:6px">Your past journals <span style="font-weight:400;color:var(--muted);font-size:12px">· ${past.length}</span></p>`;
  $("past").innerHTML = past.length ? title + list : "";
  $("pastHome").innerHTML = past.length ? title + list
    : `<p class="label" style="margin-top:6px">Your past journals</p><div class="empty" style="margin-top:0">Your saved journals will show up here.</div>`;
}
const openPast = ev => { const b = ev.target.closest(".pe"); if (!b) return; current = past[+b.dataset.i]; show("journal"); $("jWait").classList.add("hidden"); renderJournal(current, false); };
$("past").onclick = openPast; $("pastHome").onclick = openPast;
loadPast();
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"), "text/html")
        elif self.path.startswith("/entries"):
            items = []
            for f in sorted(ENTRIES.glob("*.json"), reverse=True)[:30] if ENTRIES.exists() else []:
                try:
                    items.append(json.loads(f.read_text(encoding="utf-8")))
                except ValueError:
                    pass
            self._send(200, items)
        else:
            self._send(404, {"error": "Not found"})

    def do_POST(self):
        try:
            if self.path == "/transcribe":                 # step 1: voice -> text
                audio = self._body()
                if len(audio) > 20 * 1024 * 1024:
                    return self._send(413, {"error": "Recording is too long. Keep it under 5 minutes."})
                return self._send(200, {"text": transcribe(audio, "note.wav")})

            if self.path == "/journal":                    # step 2: text -> journal
                req = json.loads(self._body() or b"{}")
                return self._send(200, make_journal(req.get("text", ""), req.get("date")))

            if self.path == "/save":                       # step 3: save the journal
                ENTRIES.mkdir(exist_ok=True)
                name = datetime.now().strftime("%Y-%m-%d_%H%M%S") + ".json"
                entry = json.loads(self._body() or b"{}")
                (ENTRIES / name).write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"  💾  Saved entries/{name}")
                return self._send(200, {"saved": name})

            self._send(404, {"error": "Not found"})
        except ValueError as e:                            # a problem the user can fix
            self._send(400, {"error": str(e)})
        except Exception as e:                             # AI / network problem
            print(f"\n  ⚠⚠  {type(e).__name__}: {str(e)[:300]}\n")
            self._send(502, {"error": "The AI didn't answer. Please try again in a moment."})

    def log_message(self, *args):                          # keep the terminal quiet
        pass


if __name__ == "__main__":
    url = f"http://localhost:{PORT}"
    print(f"\n  📓  BeLiving Voice Journal  ({MODEL})")
    print(f"  Open {url}  ·  keep this window open  ·  Ctrl+C to stop\n")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
