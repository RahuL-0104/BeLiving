"""
BeLiving - Beat the Clock (visual version)
Run:  python app.py      -> opens in your browser at http://localhost:8000
"""
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from beat_the_clock import MODEL, PROVIDER, break_down

PORT = 8000

PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Beat the Clock · BeLiving</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --page:#2c2c2c;          /* canvas around the phone */
  --bg:#f3f0eb;            /* screen cream */
  --ink:#1e1e1e;           /* titles */
  --text:#3a3a3a;
  --muted:#8c8c8c;         /* eyebrow / captions */
  --yellow:#f9d468;        /* primary accent */
  --yellow-soft:#f8ead0;   /* timer ring track */
  --teal-bg:#deeff1;       /* info box */
  --teal-line:#86c9d1;
  --white:#ffffff;
  --line:#dcd8d1;
  --grey-btn:#9a9a9a;
  --navy:#2f3a4a;          /* timer digits */
  --shadow:0 2px 6px rgba(0,0,0,.08);
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--page);font-family:Inter,system-ui,sans-serif;color:var(--text);
  min-height:100vh;display:flex;justify-content:center;align-items:flex-start;padding:24px 12px}
.phone{width:393px;max-width:100%;min-height:852px;background:var(--bg);border-radius:28px;
  padding:56px 22px 36px;position:relative;overflow:hidden}
@media (max-width:430px){body{padding:0}.phone{border-radius:0;min-height:100vh}}

.back{width:28px;height:28px;display:block;margin-bottom:22px;cursor:pointer;background:none;border:0;color:var(--ink)}
.eyebrow{font-size:15px;color:var(--muted);margin-bottom:6px}
h1{font-size:26px;font-weight:500;color:var(--ink);letter-spacing:-.01em}
.info{background:var(--teal-bg);border:1.5px solid var(--teal-line);border-radius:10px;
  padding:14px 16px;font-size:12px;line-height:1.45;color:#6f7f82;margin:26px 0 24px}
.label{font-size:15px;font-weight:600;color:var(--ink);margin:0 0 12px}

.field{width:100%;min-height:84px;resize:none;background:var(--bg);border:1px solid var(--line);
  border-radius:12px;padding:14px;font:inherit;font-size:14px;color:var(--ink);outline:none}
.field:focus{border-color:#b9b4ab}
.field::placeholder{color:#a9a59e}

.pills{display:flex;flex-wrap:wrap;gap:10px}
.pill{background:var(--white);border:0;border-radius:10px;box-shadow:var(--shadow);
  font:inherit;font-size:12px;color:var(--ink);padding:9px 14px;cursor:pointer}
.pill.on{background:var(--yellow)}
.pill.sm{font-size:11px;padding:7px 11px;color:#555}
.stuck{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}
.stuck .pill{padding:10px 0;font-size:13px;font-weight:500}
.scale{display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-top:8px}
.gap{height:22px}

.cta{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;border:0;
  background:var(--yellow);color:var(--ink);font:inherit;font-weight:600;font-size:14px;
  border-radius:10px;padding:14px;cursor:pointer;margin-top:26px}
.cta:disabled{opacity:.55;cursor:default}
.cta svg{width:16px;height:16px}
.link{display:block;width:100%;text-align:center;background:none;border:0;font:inherit;font-size:13px;
  color:var(--muted);margin-top:14px;cursor:pointer}
.err{margin-top:14px;background:#fbe9e6;border:1px solid #efc3bb;color:#9a4a3d;border-radius:10px;padding:11px 14px;font-size:12px}

/* steps (Task planner style) */
.sub{font-size:13px;color:var(--ink);margin:18px 0 6px;font-weight:500}
.row-head{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #cfcac2;
  padding-bottom:10px;margin-top:4px}
.meta{font-size:12px;color:var(--muted)}
.step{display:flex;align-items:flex-start;gap:12px;padding:13px 12px;margin-top:10px;background:var(--white);
  border-radius:10px;box-shadow:var(--shadow);cursor:pointer}
.step.star{background:#fdf3d6;outline:1.5px solid var(--yellow)}
.box{flex:0 0 18px;height:18px;border:1.5px solid #6d6d6d;border-radius:3px;margin-top:1px;display:grid;place-items:center;font-size:12px}
.step.done .box{background:var(--ink);border-color:var(--ink);color:#fff}
.step.done .txt{text-decoration:line-through;color:var(--muted)}
.txt{flex:1;font-size:14px;color:var(--ink);line-height:1.35}
.tag{display:block;font-size:10px;font-weight:600;letter-spacing:.06em;color:#b08a1e;margin-bottom:2px}
.min{font-size:11px;color:var(--muted);white-space:nowrap;margin-top:2px}

/* timer (7-Min Sprint style) */
.center{text-align:center}
.ring{position:relative;width:156px;height:156px;margin:30px auto 0}
.ring svg{transform:rotate(-90deg)}
.ring .t{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.ring .big{font-size:24px;font-weight:600;color:var(--navy)}
.ring .cap{font-size:9px;letter-spacing:.08em;color:var(--muted);margin-top:4px;text-transform:uppercase}
.ring .count{font-size:46px;font-weight:600;color:var(--navy)}
.now{font-size:15px;font-weight:600;color:var(--ink);margin:22px 8px 0;line-height:1.4}
.streak{margin-top:26px;font-size:10px;color:var(--muted)}
.dots{display:flex;justify-content:center;gap:8px;margin-top:9px}
.dot{width:14px;height:14px;border-radius:50%;background:#9a9a9a}
.dot.on{background:var(--yellow)}
.controls{display:flex;justify-content:center;align-items:center;gap:16px;margin-top:40px}
.round{border:0;border-radius:50%;display:grid;place-items:center;cursor:pointer}
.round.grey{width:38px;height:38px;background:var(--grey-btn);color:#fff}
.round.yel{width:56px;height:56px;background:var(--yellow);color:var(--ink)}
.round svg{width:20px;height:20px}
.round.yel svg{width:22px;height:22px}

/* win */
.win-emoji{font-size:64px;margin:60px 0 14px}
.hidden{display:none!important}
.spin{width:14px;height:14px;border:2px solid #0003;border-top-color:var(--ink);border-radius:50%;animation:s .7s linear infinite}
@keyframes s{to{transform:rotate(360deg)}}
.foot{position:absolute;bottom:12px;left:0;right:0;text-align:center;font-size:10px;color:#b3aea6}
</style></head><body><div class="phone">

<!-- ========== 1. INPUT ========== -->
<section id="s-input">
  <button class="back" aria-label="Back"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M11 6l-6 6 6 6"/></svg></button>
  <p class="eyebrow">AI Task Breakdown</p>
  <h1>Beat the Clock</h1>
  <div class="info">Type the task you're avoiding. We'll shrink it into tiny steps so you can start the easiest one right now.</div>

  <p class="label">What task are you putting off?</p>
  <textarea id="task" class="field" maxlength="500" placeholder="e.g. Study for my DBMS exam"></textarea>
  <div class="pills" style="margin-top:12px">
    <button class="pill sm ex">dbms exam kal hai</button>
    <button class="pill sm ex">clean my room</button>
    <button class="pill sm ex">reply to 40 emails</button>
    <button class="pill sm ex">start the gym</button>
  </div>

  <div class="gap"></div>
  <p class="label">How stuck do you feel?</p>
  <div class="stuck" id="levels"></div>
  <div class="scale"><span>A little</span><span>Totally frozen</span></div>

  <button class="cta" id="go">Break it down <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button>
  <div id="err" class="err hidden"></div>
</section>

<!-- ========== 2. STEPS ========== -->
<section id="s-steps" class="hidden">
  <button class="back" id="backToInput" aria-label="Back"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M11 6l-6 6 6 6"/></svg></button>
  <p class="eyebrow">Micro Deadlines</p>
  <h1>Your Tiny Steps</h1>
  <p class="sub" id="taskEcho"></p>
  <div class="row-head"><span class="meta"><span id="nSteps">0</span> steps · ~<span id="tMin">0</span> min</span><span class="meta" id="doneMeta">0 done</span></div>
  <div id="list"></div>
  <button class="cta" id="startBtn">Start step <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button>
  <button class="link" id="newBtn">New task</button>
</section>

<!-- ========== 3. TIMER ========== -->
<section id="s-timer" class="hidden center">
  <button class="back" id="stopBtn" aria-label="Back"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M11 6l-6 6 6 6"/></svg></button>
  <p class="eyebrow" style="text-align:left">Step <span id="tNo">1</span> of <span id="tOf">1</span></p>
  <h1 style="text-align:left">Beat the Clock</h1>
  <div class="info" style="text-align:left" id="tInfo">Just this one step. Nothing else. Hit play when you're ready.</div>

  <div class="ring">
    <svg width="156" height="156"><circle cx="78" cy="78" r="70" stroke="#f8ead0" stroke-width="8" fill="none"/>
      <circle id="arc" cx="78" cy="78" r="70" stroke="#f9d468" stroke-width="8" fill="none" stroke-linecap="round"
        stroke-dasharray="439.8" stroke-dashoffset="439.8"/></svg>
    <div class="t" id="ringText"><span class="big" id="clock">00:00</span><span class="cap" id="cap">Ready</span></div>
  </div>
  <p class="now" id="tStep"></p>

  <p class="streak">Steps done</p>
  <div class="dots" id="dots"></div>

  <div class="controls">
    <button class="round grey" id="resetBtn" aria-label="Restart"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M4 12a8 8 0 1 0 2.3-5.6M4 4v5h5"/></svg></button>
    <button class="round yel" id="playBtn" aria-label="Play"></button>
    <button class="round grey" id="doneBtn" aria-label="Done"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M5 12l5 5 9-10"/></svg></button>
  </div>
</section>

<!-- ========== 4. WIN ========== -->
<section id="s-win" class="hidden center">
  <div class="win-emoji">🎉</div>
  <h1 id="winTitle">You started.</h1>
  <div class="info" id="winSub" style="margin-top:18px">That was the hardest part.</div>
  <div class="dots" id="winDots"></div>
  <button class="cta" id="nextBtn">Next step <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button>
  <button class="link" id="backBtn">Back to my steps</button>
</section>

<p class="foot" id="foot"></p>
</div>
<script>
const $=id=>document.getElementById(id);
const screens=["input","steps","timer","win"];
function show(n){screens.forEach(s=>$("s-"+s).classList.toggle("hidden",s!==n));window.scrollTo(0,0)}
const PLAY='<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
const PAUSE='<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 5h4v14H7zM13 5h4v14h-4z"/></svg>';
const ARROW=' <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12h14M13 6l6 6-6 6"/></svg>';
let level=3, steps=[], cur=0, timer=null, left=0, total=0, phase="ready";

const lv=$("levels");
for(let i=1;i<=5;i++){const b=document.createElement("button");b.className="pill"+(i===3?" on":"");b.textContent=i;
  b.onclick=()=>{level=i;[...lv.children].forEach((c,j)=>c.classList.toggle("on",j===i-1))};lv.appendChild(b)}
document.querySelectorAll(".ex").forEach(c=>c.onclick=()=>{$("task").value=c.textContent;$("task").focus()});

async function breakDown(){
  const task=$("task").value.trim(); $("err").classList.add("hidden");
  if(task.length<3){showErr("Tell me a bit more about the task.");return}
  $("go").disabled=true;$("go").innerHTML='<span class="spin"></span> Breaking it down…';
  try{
    const r=await fetch("/api/breakdown",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({task,stuck_level:level})});
    const d=await r.json();
    if(!d.ok){showErr(d.message);return}
    steps=d.steps.map(s=>({...s,done:false}));
    $("taskEcho").textContent=task;$("nSteps").textContent=steps.length;$("tMin").textContent=d.total_minutes;
    renderSteps();show("steps");
  }catch(e){showErr("Can't reach the server. Is app.py still running?")}
  finally{$("go").disabled=false;$("go").innerHTML="Break it down"+ARROW}
}
function showErr(m){$("err").textContent=m;$("err").classList.remove("hidden")}
function esc(t){return t.replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function nextIdx(){const s=steps.findIndex(x=>x.start_here&&!x.done);return s!==-1?s:steps.findIndex(x=>!x.done)}
function doneCount(){return steps.filter(s=>s.done).length}

function renderSteps(){
  const L=$("list");L.innerHTML="";
  steps.forEach((s,i)=>{
    const d=document.createElement("div");
    d.className="step"+(s.start_here&&!s.done?" star":"")+(s.done?" done":"");
    d.innerHTML='<span class="box">'+(s.done?"✓":"")+'</span><span class="txt">'+(s.start_here&&!s.done?'<span class="tag">★ START HERE</span>':'')+esc(s.text)+'</span><span class="min">'+s.minutes+' min</span>';
    d.onclick=()=>openTimer(i);L.appendChild(d)});
  $("doneMeta").textContent=doneCount()+" done";
  const n=nextIdx();
  $("startBtn").disabled=n===-1;
  $("startBtn").innerHTML=(n===-1?"All steps done":(steps[n].start_here?"Start the ★ step":"Start step "+steps[n].id))+(n===-1?"":ARROW);
}
function renderDots(el){el.innerHTML=steps.map(s=>'<span class="dot'+(s.done?" on":"")+'"></span>').join("")}

function openTimer(i){
  clearInterval(timer);cur=i;const s=steps[i];total=s.minutes*60;left=total;phase="ready";
  $("tNo").textContent=s.id;$("tOf").textContent=steps.length;$("tStep").textContent=s.text;
  $("tInfo").textContent="Just this one step. Nothing else. Hit play when you're ready.";
  $("ringText").innerHTML='<span class="big" id="clock"></span><span class="cap" id="cap">Ready</span>';
  drawClock();$("arc").setAttribute("stroke-dashoffset","0");
  $("playBtn").innerHTML=PLAY;renderDots($("dots"));show("timer");
}
function drawClock(){const m=Math.floor(left/60),s=left%60;$("clock").textContent=String(m).padStart(2,"0")+":"+String(s).padStart(2,"0");
  $("arc").setAttribute("stroke-dashoffset",(439.8*(1-left/total)).toFixed(1))}
function countdown(){
  phase="count";let n=5;$("ringText").innerHTML='<span class="count">'+n+'</span><span class="cap">Get ready</span>';
  $("playBtn").innerHTML=PAUSE;
  timer=setInterval(()=>{n--;if(n>0){$("ringText").querySelector(".count").textContent=n}else{clearInterval(timer);run()}},1000);
}
function run(){
  phase="run";$("ringText").innerHTML='<span class="big" id="clock"></span><span class="cap" id="cap">Sprint</span>';drawClock();
  $("playBtn").innerHTML=PAUSE;
  timer=setInterval(()=>{left--;drawClock();if(left<=0){clearInterval(timer);finish()}},1000);
}
$("playBtn").onclick=()=>{
  if(phase==="ready"){countdown()}
  else if(phase==="run"){clearInterval(timer);phase="paused";$("playBtn").innerHTML=PLAY;$("cap").textContent="Paused"}
  else if(phase==="paused"){run()}
};
$("resetBtn").onclick=()=>openTimer(cur);
$("doneBtn").onclick=()=>{if(phase!=="ready"||confirmSkip())finish()};
function confirmSkip(){return true}
function finish(){
  clearInterval(timer);steps[cur].done=true;
  const remaining=steps.filter(s=>!s.done).length, d=doneCount();
  $("winTitle").textContent=remaining===0?"Task complete.":(d===1?"You started.":"Step done.");
  $("winSub").textContent=remaining===0?"Every step done. Go have some chai ☕":remaining+" step"+(remaining>1?"s":"")+" left. Momentum is on your side.";
  $("nextBtn").classList.toggle("hidden",remaining===0);
  renderDots($("winDots"));renderSteps();show("win");
}
$("go").onclick=breakDown;
$("task").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();breakDown()}});
$("startBtn").onclick=()=>{const n=nextIdx();if(n!==-1)openTimer(n)};
$("newBtn").onclick=()=>{$("task").value="";show("input")};
$("backToInput").onclick=()=>show("input");
$("stopBtn").onclick=()=>{clearInterval(timer);renderSteps();show("steps")};
$("nextBtn").onclick=()=>{const n=nextIdx();if(n!==-1)openTimer(n)};
$("backBtn").onclick=()=>show("steps");
fetch("/api/info").then(r=>r.json()).then(d=>$("foot").textContent="BeLiving · "+d.provider+" · "+d.model).catch(()=>{});
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE, "text/html")
        elif self.path == "/api/info":
            self._send(200, json.dumps({"provider": PROVIDER, "model": MODEL}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/api/breakdown":
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            result = break_down(body.get("task", ""), int(body.get("stuck_level", 3)))
        except Exception as e:
            result = {"ok": False, "error": "BAD_REQUEST", "message": str(e)}
        self._send(200, json.dumps(result))

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    import os
    key = "GEMINI_API_KEY" if PROVIDER == "gemini" else "OPENAI_API_KEY"
    if not os.getenv(key):
        print(f"\n  ⚠  No key found. Paste your key after {key}= in keys.env, save, and run again.\n")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"\n  ⏱  Beat the Clock is running at {url}")
    print("  Keep this window open. Press Ctrl + C to stop.\n")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
