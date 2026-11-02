"""
BeLiving - Focus Lock (visual version)
Run:  python app.py      -> opens in your browser at http://localhost:8002

Enter a time in minutes or hours, lock in, stay in the app, earn leaves.
"""
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pomodoro

PORT = 8002

PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Focus Lock · BeLiving</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Playfair+Display:wght@500&display=swap" rel="stylesheet">
<style>
:root{
  --page:#d9d6d0; --cream:#f3efe8; --card:#fff; --line:#e6e1d8; --ink:#1f2633; --muted:#8b919c;
  --navy:#2b3a52; --dark:#111821; --dark-2:#19222e; --dark-line:#263243; --dark-text:#e9e5de; --dark-muted:#6f7988;
  --orange:#d4784a;
  --serif:"Playfair Display",Georgia,serif; --sans:"DM Sans",system-ui,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--page);font-family:var(--sans);color:var(--ink);min-height:100vh;
  display:flex;justify-content:center;align-items:flex-start;padding:24px 12px}
.phone{width:393px;max-width:100%;height:852px;max-height:calc(100vh - 48px);min-height:640px;background:var(--cream);
  border-radius:34px;position:relative;overflow:hidden;transition:background .3s}
.phone.dark{background:var(--dark)}
@media (max-width:430px){body{padding:0}.phone{border-radius:0;height:100vh;max-height:none}}
:fullscreen body{padding:0;background:var(--dark)} :fullscreen .phone{border-radius:0;height:100vh;max-height:none;width:100%}
section{position:absolute;inset:0;display:flex;flex-direction:column;padding:56px 28px 40px}
.hidden{display:none!important}
button{font:inherit;cursor:pointer;border:0;background:none;color:inherit}
input{font:inherit}

/* top bar */
.top{display:flex;justify-content:space-between;align-items:center}
.title{font-family:var(--serif);font-size:26px;font-weight:500}
.leaves{font-size:13px;color:var(--muted)}
.leaves b{color:var(--ink);font-weight:600}

/* time picker */
.mid{flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center}
.ask{font-size:14px;color:var(--muted)}
.timebox{display:flex;align-items:baseline;justify-content:center;margin-top:14px}
.timebox input{width:200px;border:0;background:transparent;text-align:center;outline:none;
  font-family:var(--serif);font-size:96px;font-weight:500;color:var(--ink);line-height:1;-moz-appearance:textfield}
.timebox input::-webkit-outer-spin-button,.timebox input::-webkit-inner-spin-button{-webkit-appearance:none;margin:0}
.underline{width:160px;height:2px;background:var(--line);margin-top:6px;border-radius:2px}
.unit{display:flex;background:#e9e4da;border-radius:99px;padding:4px;margin-top:22px}
.unit button{padding:8px 22px;border-radius:99px;font-size:14px;color:var(--muted)}
.unit button.on{background:var(--card);color:var(--ink);box-shadow:0 1px 3px #0000001a}
.quick{display:flex;gap:8px;margin-top:26px}
.quick button{font-size:13px;color:var(--muted);border:1px solid var(--line);border-radius:99px;padding:7px 14px}
.quick button:hover{color:var(--ink);border-color:#cfc8bc}
.brk{display:flex;align-items:center;gap:12px;margin-top:26px}
.brk span{font-size:13px;color:var(--muted)}
.seg{display:flex;background:#e9e4da;border-radius:99px;padding:3px}
.seg button{padding:6px 14px;border-radius:99px;font-size:13px;color:var(--muted)}
.seg button.on{background:var(--card);color:var(--ink);box-shadow:0 1px 3px #0000001a}
.note{font-size:12px;color:var(--muted);text-align:center;margin-top:14px;min-height:16px}
.note.err{color:#b4533f}

.start{width:100%;background:var(--navy);color:#fff;border-radius:18px;padding:18px;font-size:16px;font-weight:600}
.start:disabled{opacity:.6}
.fine{font-size:12px;color:var(--muted);text-align:center;margin-top:14px}

/* lock */
.dark .ring{position:relative;width:270px;height:270px}
.ring svg{transform:rotate(-90deg);display:block}
.ring .c{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.clock{font-family:var(--serif);font-size:60px;color:var(--dark-text);font-weight:500;font-variant-numeric:tabular-nums}
.clock.long{font-size:46px}
.sub{font-size:11px;letter-spacing:.18em;color:var(--dark-muted);margin-top:6px}
.lockfoot{display:flex;justify-content:center;gap:56px}
.lb{display:flex;flex-direction:column;align-items:center;gap:12px}
.stop .cup{font-size:20px}
.stop{width:58px;height:58px;border-radius:50%;background:var(--dark-2);border:1px solid var(--dark-line);color:#8d96a3;
  display:grid;place-items:center;position:relative}
.stop svg{width:18px;height:18px}
.stop .hold{position:absolute;inset:-4px;width:66px;height:66px}
.holdtxt{font-size:12px;color:var(--dark-muted)}

/* result screens */
.res{text-align:center}
.res .e{font-size:54px}
.res h2{font-family:var(--serif);font-weight:500;font-size:30px;margin-top:14px}
.dark .res h2{color:var(--dark-text)}
.res p{font-size:14px;color:var(--muted);margin-top:8px;line-height:1.5}
.dark .res p{color:var(--dark-muted)}
.res .big{font-family:var(--serif);font-size:72px;margin-top:4px}
.btn{width:100%;border-radius:18px;padding:18px;font-size:16px;font-weight:600}
.btn.navy{background:var(--navy);color:#fff}
.btn.orange{background:var(--orange);color:#fff}

/* overlay */
.ov{position:absolute;inset:0;background:#0b1017ee;display:flex;align-items:center;justify-content:center;padding:28px;z-index:5}
.sheet{background:var(--dark-2);border:1px solid var(--dark-line);border-radius:22px;padding:26px;text-align:center;color:var(--dark-text);width:100%}
.sheet h3{font-family:var(--serif);font-weight:500;font-size:22px}
.sheet p{font-size:13px;color:#9aa3af;margin-top:8px;line-height:1.5}
.sheet .btn{margin-top:18px;padding:15px}
</style></head><body><div class="phone" id="phone">

<!-- HOME -->
<section id="s-home">
  <div class="top">
    <span class="title">Focus Lock</span>
    <span class="leaves">🍃 <b id="pts">0</b></span>
  </div>
  <div class="mid">
    <p class="ask">How long do you want to focus?</p>
    <div class="timebox"><input id="amount" type="number" inputmode="decimal" value="25" min="1" step="any" aria-label="Time"></div>
    <div class="underline"></div>
    <div class="unit" id="unit">
      <button data-u="min" class="on">minutes</button>
      <button data-u="hr">hours</button>
    </div>
    <div class="quick" id="quick">
      <button data-m="25">25m</button><button data-m="50">50m</button>
      <button data-m="60">1h</button><button data-m="120">2h</button>
    </div>
    <div class="brk"><span>Breaks</span>
      <div class="seg" id="brk"><button data-b="0" class="on">None</button><button data-b="1">1</button><button data-b="2">2</button><button data-b="3">3</button></div>
    </div>
    <p class="note" id="note"></p>
  </div>
  <button class="start" id="go">Start lock</button>
  <p class="fine">Leave the app for 15 seconds and the lock breaks.</p>
</section>

<!-- LOCK -->
<section id="s-lock" class="hidden" style="align-items:center">
  <div class="mid">
    <div class="ring">
      <svg width="270" height="270">
        <circle cx="135" cy="135" r="122" stroke="#1d2632" stroke-width="6" fill="none"/>
        <circle id="arc" cx="135" cy="135" r="122" stroke="#d4784a" stroke-width="6" fill="none"
          stroke-linecap="round" stroke-dasharray="766.5" stroke-dashoffset="0"/>
      </svg>
      <div class="c"><span class="clock" id="clock">25:00</span><span class="sub">🔒 LOCKED</span></div>
    </div>
  </div>
  <div class="lockfoot">
    <div class="lb">
    <button class="stop" id="stop" aria-label="Hold to end">
      <svg class="hold" viewBox="0 0 66 66"><circle id="holdArc" cx="33" cy="33" r="31" stroke="#c0644f" stroke-width="2.5" fill="none"
        stroke-dasharray="194.8" stroke-dashoffset="194.8" transform="rotate(-90 33 33)"/></svg>
      <svg viewBox="0 0 24 24" fill="currentColor"><rect x="7" y="7" width="10" height="10" rx="2"/></svg>
    </button>
    <span class="holdtxt">Hold to end</span>
    </div>
    <div class="lb" id="breakWrap">
      <button class="stop" id="breakBtn" aria-label="Take a break"><span class="cup">☕</span></button>
      <span class="holdtxt" id="breakTxt">Break</span>
    </div>
  </div>
</section>

<!-- BREAK -->
<section id="s-break" class="hidden">
  <div class="mid res">
    <div class="e">☕</div>
    <h2 id="brTitle">Break</h2>
    <div class="big" id="brClock">05:00</div>
    <p id="brText">Lock paused. You can use your phone, just be back before the timer ends.</p>
  </div>
  <button class="btn navy" id="brBack">Back to focus 🔒</button>
</section>

<!-- DONE -->
<section id="s-done" class="hidden">
  <div class="mid res">
    <div class="e">🍃</div>
    <div class="big">+<span id="dEarn">0</span></div>
    <p id="dText"></p>
  </div>
  <button class="btn navy" id="dBtn">Done</button>
</section>

<!-- BROKEN -->
<section id="s-broken" class="hidden">
  <div class="mid res">
    <div class="e">🥀</div>
    <h2>Lock broken</h2>
    <p id="bText"></p>
  </div>
  <button class="btn orange" id="bBtn">Try again</button>
</section>

<div class="ov hidden" id="ov"><div class="sheet" id="sheet"></div></div>
</div>

<script>
const $=id=>document.getElementById(id);
const DARK=new Set(["lock","broken"]), RING=766.5, HOLD=194.8;
let breaks=0, breaksLeft=0, breaksUsed=0, pausedLeft=0, breakEnd=0, bTick=null;
let S=null, unit="min", sess=null, endAt=0, total=0, tick=null, slips=0, leftAt=null, titleT=null, screen="home";

function show(n){screen=n;["home","lock","break","done","broken"].forEach(s=>$("s-"+s).classList.toggle("hidden",s!==n));
  $("phone").classList.toggle("dark",DARK.has(n))}
async function api(p,b){const r=await fetch(p,b?{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b)}:{});return r.json()}
const pts=m=>Math.floor(m*(m>=60?1.5:m>=45?1.25:1)+.5);
function fmt(s){s=Math.max(0,Math.ceil(s));const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60,p=n=>String(n).padStart(2,"0");
  return h?`${h}:${p(m)}:${p(x)}`:`${p(m)}:${p(x)}`}
function human(m){const h=Math.floor(m/60),r=m%60;return h?(r?`${h} h ${r} min`:`${h} h`):`${m} min`}

// ---------- home
async function home(){
  S=await api("/api/stats");
  if(S.active){const r=await api("/api/give_up",{session_id:S.active.id,reason:"left_app"});S=await api("/api/stats");if(r.ok){broken(r);return}}
  $("pts").textContent=S.points;show("home");update();
}
function minutes(){const v=parseFloat($("amount").value);if(!(v>0))return 0;return Math.round(unit==="hr"?v*60:v)}
function update(){
  const m=minutes(),n=$("note");n.classList.remove("err");
  if(!m){n.textContent="";return}
  if(m<S.rules.min_minutes||m>S.rules.max_minutes){n.classList.add("err");n.textContent=`Pick between ${S.rules.min_minutes} min and ${S.rules.max_minutes/60} hours`;return}
  n.textContent=`${human(m)} · ${breaks?`${breaks} × ${S.rules.break_len} min break${breaks>1?"s":""} · `:""}+${pts(m)+10} 🍃 if you stay`;
}
$("amount").addEventListener("input",update);
$("amount").addEventListener("keydown",e=>{if(e.key==="Enter")$("go").click()});
$("unit").onclick=e=>{const u=e.target.dataset.u;if(!u||u===unit)return;
  const m=minutes();unit=u;
  document.querySelectorAll("#unit button").forEach(b=>b.classList.toggle("on",b.dataset.u===u));
  if(m)$("amount").value=u==="hr"?+(m/60).toFixed(2):m;
  update()};
$("brk").onclick=e=>{const b=e.target.dataset.b;if(b===undefined)return;breaks=+b;
  document.querySelectorAll("#brk button").forEach(x=>x.classList.toggle("on",x.dataset.b===b));update()};
$("quick").onclick=e=>{const m=+e.target.dataset.m;if(!m)return;
  const u=m>=60&&m%60===0?"hr":"min";unit=u;
  document.querySelectorAll("#unit button").forEach(b=>b.classList.toggle("on",b.dataset.u===u));
  $("amount").value=u==="hr"?m/60:m;update()};

$("go").onclick=async()=>{
  const m=minutes();
  if(!m||m<S.rules.min_minutes||m>S.rules.max_minutes){update();$("amount").focus();return}
  fs(true);$("go").disabled=true;
  const r=await api("/api/start",{task:"Focus",minutes:m,rounds:1,breaks});
  $("go").disabled=false;
  if(!r.ok){$("note").classList.add("err");$("note").textContent=r.message;fs(false);return}
  lock(r.session);
};

// ---------- lock
function lock(s){
  sess=s;slips=0;leftAt=null;total=s.minutes*60;endAt=Date.now()+s.seconds_left*1000;
  breaksLeft=s.breaks;breaksUsed=0;breakUI();
  $("clock").classList.toggle("long",total>=3600);show("lock");
  clearInterval(tick);tick=setInterval(draw,250);draw();
}
function draw(){
  const left=Math.max(0,(endAt-Date.now())/1000);
  $("clock").textContent=fmt(left);
  $("arc").setAttribute("stroke-dashoffset",(RING*(1-left/total)).toFixed(1));
  if(left<=0){clearInterval(tick);finish()}
}
function breakUI(){$("breakWrap").classList.toggle("hidden",!sess.breaks);
  $("breakBtn").disabled=breaksLeft<=0;$("breakBtn").style.opacity=breaksLeft>0?1:.35;
  $("breakTxt").textContent=breaksLeft>0?`Break · ${breaksLeft} left`:"No breaks left"}
$("breakBtn").onclick=()=>{
  if(breaksLeft<=0||screen!=="lock")return;
  breaksLeft--;breaksUsed++;pausedLeft=Math.max(0,(endAt-Date.now())/1000);clearInterval(tick);
  breakEnd=Date.now()+sess.break_len*60*1000;fs(false);
  $("brTitle").textContent="Break";$("brText").textContent="Lock paused. You can use your phone, just be back before the timer ends.";
  show("break");clearInterval(bTick);bTick=setInterval(bdraw,250);bdraw();
};
function bdraw(){
  const left=(breakEnd-Date.now())/1000;
  if(left>0){$("brClock").textContent=fmt(left);return}
  const over=-left,g=sess.grace_seconds-over;
  if(g<=0){clearInterval(bTick);end("break_overrun");return}
  if($("brTitle").textContent==="Break"){chime();buzz([200,100,200])}
  $("brTitle").textContent="Break's over";$("brClock").textContent=Math.ceil(g)+"s";
  $("brText").textContent="Tap below to lock back in, or the lock breaks.";
}
$("brBack").onclick=()=>{clearInterval(bTick);fs(true);endAt=Date.now()+pausedLeft*1000;show("lock");breakUI();
  clearInterval(tick);tick=setInterval(draw,250);draw()};

let hs=null,hr=null;
function holdTick(){const p=Math.min(1,(Date.now()-hs)/2000);$("holdArc").setAttribute("stroke-dashoffset",(HOLD*(1-p)).toFixed(1));
  if(p>=1){holdOff();end("quit");return}hr=requestAnimationFrame(holdTick)}
function holdOff(){hs=null;cancelAnimationFrame(hr);$("holdArc").setAttribute("stroke-dashoffset",HOLD)}
["mousedown","touchstart"].forEach(e=>$("stop").addEventListener(e,ev=>{ev.preventDefault();hs=Date.now();holdTick()}));
["mouseup","mouseleave","touchend","touchcancel"].forEach(e=>$("stop").addEventListener(e,holdOff));

document.addEventListener("visibilitychange",()=>{
  if(screen==="break"&&!document.hidden){bdraw();return}
  if(screen!=="lock")return;
  if(document.hidden){leftAt=Date.now();
    titleT=setInterval(()=>{const l=sess.grace_seconds-Math.floor((Date.now()-leftAt)/1000);document.title=l>0?`⚠ Come back · ${l}s`:"🥀 Lock broken"},500);
  }else if(leftAt){
    clearInterval(titleT);document.title="Focus Lock · BeLiving";
    const away=(Date.now()-leftAt)/1000;leftAt=null;
    if(away>sess.grace_seconds){end("left_app");return}
    if(++slips>sess.max_slips){end("too_many_slips");return}
    sheet(`<h3>Stay with it</h3><p>You left for ${Math.round(away)}s. ${slips===sess.max_slips?"Next time you leave, the lock breaks.":`${sess.max_slips-slips} more and the lock breaks.`}</p>
      <button class="btn orange" onclick="closeSheet();fs(true)">Back to focus</button>`);
  }
});
document.addEventListener("fullscreenchange",()=>{
  if(screen==="lock"&&!document.fullscreenElement&&!document.hidden)
    sheet(`<h3>Stay in the lock</h3><p>Full screen keeps everything else out of sight.</p>
      <button class="btn orange" onclick="closeSheet();fs(true)">Back to full screen</button>`);
});
window.addEventListener("beforeunload",e=>{if(screen==="lock"){e.preventDefault();e.returnValue=""}});
function fs(on){try{if(on&&!document.fullscreenElement)document.documentElement.requestFullscreen?.().catch(()=>{});
  if(!on&&document.fullscreenElement)document.exitFullscreen()}catch(e){}}
function sheet(h){$("sheet").innerHTML=h;$("ov").classList.remove("hidden")}
function closeSheet(){$("ov").classList.add("hidden")}

async function end(reason){
  clearInterval(tick);clearInterval(bTick);clearInterval(titleT);document.title="Focus Lock · BeLiving";closeSheet();screen="ending";
  const r=await api("/api/give_up",{session_id:sess.id,reason});fs(false);buzz([300,100,300]);
  broken(r.ok?r:{message:"The lock broke.",focused_minutes:0});
}
function broken(r){
  const why={quit:"You ended it early.",too_many_slips:"You left the app too many times.",break_overrun:"You didn't come back after your break.",too_many_breaks:"You took more breaks than you picked."}[r.reason]||"You left the app for too long.";
  $("bText").textContent=why+(r.focused_minutes?` You still focused ${human(r.focused_minutes)}.`:"");
  show("broken");
}
$("bBtn").onclick=home;

async function finish(){
  chime();buzz([200,100,200]);
  let r=await api("/api/finish",{session_id:sess.id,slips,task_done:false,breaks_used:breaksUsed});
  if(!r.ok&&r.error==="TOO_EARLY"){await new Promise(z=>setTimeout(z,(r.seconds_left+1)*1000));r=await api("/api/finish",{session_id:sess.id,slips,task_done:false,breaks_used:breaksUsed})}
  fs(false);
  if(r.broken){broken(r);return}
  if(!r.ok){broken({reason:"left_app",focused_minutes:0});return}
  $("dEarn").textContent=r.earned;
  $("dText").textContent=`${human(sess.minutes)} of focus. You now have ${r.total_points} leaves`+(r.level_up?` and reached ${r.level.emoji} ${r.level.name}.`:".");
  show("done");
}
$("dBtn").onclick=home;

function chime(){try{const a=new (window.AudioContext||window.webkitAudioContext)();[523,659,784].forEach((f,i)=>{
  const o=a.createOscillator(),g=a.createGain();o.frequency.value=f;o.connect(g);g.connect(a.destination);
  const t=a.currentTime+i*.18;g.gain.setValueAtTime(.0001,t);g.gain.exponentialRampToValueAtTime(.2,t+.02);g.gain.exponentialRampToValueAtTime(.0001,t+.5);
  o.start(t);o.stop(t+.55)})}catch(e){}}
function buzz(p){try{navigator.vibrate&&navigator.vibrate(p)}catch(e){}}

home();
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, kind="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"), "text/html")
        elif self.path == "/api/stats":
            self._send(200, pomodoro.stats())
        else:
            self._send(404, {"error": "Not found"})

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            if self.path == "/api/start":
                return self._send(200, pomodoro.start(body.get("task", ""), body.get("minutes", 25), body.get("rounds", 1),
                                                            breaks=body.get("breaks", 0)))
            if self.path == "/api/finish":
                return self._send(200, pomodoro.finish_round(body.get("session_id", ""), body.get("slips", 0),
                                                             bool(body.get("task_done")),
                                                             breaks_used=body.get("breaks_used", 0)))
            if self.path == "/api/next":
                return self._send(200, pomodoro.next_round(body.get("session_id", "")))
            if self.path == "/api/give_up":
                return self._send(200, pomodoro.give_up(body.get("session_id", ""), body.get("reason", "quit")))
            self._send(404, {"error": "Not found"})
        except Exception as e:
            print(f"\n  ⚠⚠  {type(e).__name__}: {str(e)[:300]}\n")
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
    print(f"\n  🔒  BeLiving Focus Lock running at {url}")
    print("  Keep this window open. Press Ctrl + C to stop.\n")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
