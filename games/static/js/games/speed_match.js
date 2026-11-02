/* Snap Match — speed + attention. Does this card match the one before it?
   45 seconds. Tap Yes/No, swipe the card, or use ← → keys.
   Streaks raise your multiplier (up to x5). */
(function () {
  const { h, $, sfx, haptic, wait, rand } = BL;
  const DURATION = 60;
  const COLS = ["#FFC83D", "#FF8FAB", "#7ED9C3", "#9B8CFF", "#FF6B6B", "#8EC5FF"];
  const SHAPES = {
    circle: ["#FFC83D", '<circle cx="50" cy="50" r="34"/>'],
    triangle: ["#FF8FAB", '<path d="M50 14L88 82H12Z" stroke-linejoin="round"/>'],
    square: ["#7ED9C3", '<rect x="18" y="18" width="64" height="64" rx="10"/>'],
    star: ["#9B8CFF", '<path d="M50 12l11 24 26 3-19 18 5 26-23-13-23 13 5-26-19-18 26-3z" stroke-linejoin="round"/>'],
    heart: ["#FF6B6B", '<path d="M50 84S14 62 14 38a18 18 0 0136-6 18 18 0 0136 6c0 24-36 46-36 46z"/>'],
    drop: ["#8EC5FF", '<path d="M50 12C50 12 20 46 20 62a30 30 0 0060 0C80 46 50 12 50 12z"/>'],
  };
  const NAMES = Object.keys(SHAPES);
  const svgOf = (n, col, rot = 0) => `<svg viewBox="0 0 100 100" width="150" height="150" style="transform:rotate(${rot}deg)"><g fill="${col || SHAPES[n][0]}" stroke="#1E2235" stroke-width="3">${SHAPES[n][1]}</g></svg>`;

  const css = `
  .sm-top{padding:4px 20px 0}
  .sm-time{height:8px;border-radius:9px;background:#F1ECDD;overflow:hidden}
  .sm-time i{display:block;height:100%;width:100%;border-radius:9px;background:linear-gradient(90deg,#FFC83D,#F2A900);transform-origin:left;transition:background .4s}
  .sm-stage{flex:1;display:grid;place-items:center;position:relative;min-height:0}
  .sm-stack{position:relative;width:250px;height:300px}
  .sm-card{position:absolute;inset:0;border-radius:32px;background:#fff;border:1px solid var(--line);box-shadow:var(--shadow);display:grid;place-items:center;
    transition:transform .45s var(--ease),opacity .45s var(--ease);touch-action:none;will-change:transform}
  .sm-card.ghost1{transform:translateY(18px) scale(.95);background:#FFF6DA;border-color:#F6E7B8;box-shadow:var(--shadow-sm)}
  .sm-card.ghost2{transform:translateY(34px) scale(.9);background:#FFEDB8;border-color:#F5DF9C;box-shadow:none}
  .sm-card.enter{animation:smEnter .45s var(--spring)}
  @keyframes smEnter{from{transform:translateY(18px) scale(.95)}}
  .sm-card svg{filter:drop-shadow(0 10px 14px rgba(0,0,0,.1));transition:transform .4s var(--spring)}
  .sm-card.enter svg{animation:smPop .5s var(--spring)}
  @keyframes smPop{from{transform:scale(.5) rotate(-12deg)}}
  .sm-stamp{position:absolute;top:18px;padding:6px 14px;border-radius:12px;font-weight:800;font-size:18px;letter-spacing:1px;opacity:0;border:3px solid}
  .sm-stamp.yes{right:18px;color:var(--teal);border-color:var(--teal);transform:rotate(12deg)}
  .sm-stamp.no{left:18px;color:var(--coral);border-color:var(--coral);transform:rotate(-12deg)}
  .sm-q{text-align:center;font-weight:600;color:var(--ink-2);font-size:15px;margin-top:46px;min-height:22px}
  .sm-btns{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:6px 20px 24px}
  .sm-b{height:68px;border-radius:22px;font-size:18px;font-weight:700;display:flex;align-items:center;justify-content:center;gap:8px;
    transition:transform .15s var(--spring),box-shadow .2s,opacity .3s}
  .sm-b:active{transform:scale(.94)}
  .sm-b.no{background:#FFF0F0;color:#D94848;box-shadow:inset 0 -4px 0 #FFD6D6}
  .sm-b.yes{background:#E6F8F5;color:#118C7D;box-shadow:inset 0 -4px 0 #C4EEE7}
  .sm-b[disabled]{opacity:.4}
  .sm-mult{transition:transform .35s var(--spring)}
  .sm-mult.bump{transform:scale(1.25)}
  .sm-flash{position:absolute;inset:0;border-radius:32px;pointer-events:none;opacity:0}
  .sm-flash.ok{animation:smF .5s;box-shadow:0 0 0 4px var(--teal) inset}
  .sm-flash.bad{animation:smF .5s;box-shadow:0 0 0 4px var(--coral) inset}
  @keyframes smF{30%{opacity:1}}
  .sm-lvl{display:flex;justify-content:center;gap:6px;padding:12px 0 0}
  .sm-lvl span{font-size:11.5px;font-weight:700;padding:5px 10px;border-radius:99px;background:#F4F0E4;color:var(--muted);transition:all .35s var(--spring)}
  .sm-lvl span.on{background:var(--ink);color:var(--yellow);transform:scale(1.06)}
  .sm-q b{color:var(--ink)}
  .sm-back{position:absolute;right:-6px;top:-10px;z-index:9;background:var(--yellow);color:#3A2A00;font-weight:800;font-size:12px;padding:5px 10px;border-radius:99px;box-shadow:var(--shadow-sm);opacity:0;transition:opacity .3s}
  .sm-back.on{opacity:1;animation:pop .5s var(--spring)}`;

  BL.register({
    id: "speed_match",
    name: "Snap Match",
    tag: "Same shape as before? Three levels in 60 seconds: colour tricks, then 2-back.",
    tint: "#FFE9EE",
    chips: ["Speed", "60 sec"],
    icon: `<svg viewBox="0 0 48 48"><rect x="16" y="9" width="24" height="31" rx="6" fill="#fff" stroke="#1E2235" stroke-width="1.5" transform="rotate(12 28 24)"/><rect x="8" y="8" width="24" height="31" rx="6" fill="#fff" stroke="#1E2235" stroke-width="1.5" transform="rotate(-8 20 24)"/><path d="M20 17l3.2 6.6 7.2.9-5.3 5 1.4 7.1L20 33l-6.5 3.6 1.4-7.1-5.3-5 7.2-.9z" fill="#FFC83D" stroke="#1E2235" stroke-width="1.3" stroke-linejoin="round" transform="rotate(-8 20 24)"/></svg>`,
    formatBest: (s) => `${s.toLocaleString("en-IN")} pts`,
    intro: {
      desc: "A 60-second speed test that changes the rules on you. Stay sharp when the cards start lying.",
      how: ["Level 1 (0–20s): same SHAPE as the previous card?", "Level 2 (20–40s): colours and angles change. Only the shape counts", "Level 3 (40–60s): 2-back. Same shape as 2 cards ago? Points ×2, then ×3"],
      science: "The n-back task is a classic working-memory workout. Colour tricks train you to ignore distractions.",
      cta: "Start sprint",
    },
    start(body, api) {
      const rng = api.rng;
      body.innerHTML = `<style>${css}</style>
        ${BL.timerBarHTML("smT")}
        <div class="sm-lvl" id="smL"><span class="on">1 · Match</span><span>2 · Tricks</span><span>3 · 2-back</span></div>
        <div class="sm-stage"><div>
          <div class="sm-stack" id="smStack"><div class="sm-back" id="smBack">2-BACK</div><div class="sm-card ghost2"></div><div class="sm-card ghost1"></div></div>
          <div class="sm-q" id="smQ"></div>
        </div></div>
        <div class="sm-btns"><button class="sm-b no" id="smNo" disabled>✕ No</button><button class="sm-b yes" id="smYes" disabled>✓ Yes</button></div>`;
      const stack = $("#smStack", body), q = $("#smQ", body), bNo = $("#smNo", body), bYes = $("#smYes", body);
      api.pills.innerHTML = `<span class="pill sm-mult" id="smM">x1</span><span class="pill yellow" id="smP">0</span>`;
      const multEl = $("#smM"), ptsEl = $("#smP");

      const hist = []; // shapes shown so far
      let timer = null, card = null, live = false, pts = 0, mult = 1, streak = 0, right = 0, total = 0, shownAt = 0, rts = [], level = 1, t0 = 0, perLevel = { 1: [0, 0], 2: [0, 0], 3: [0, 0] };
      const back = () => (level === 3 ? 2 : 1);
      const question = () => (level === 3 ? "Same shape as <b>2 cards ago</b>?" : level === 2 ? "Same <b>shape</b> as the last card? (ignore colour)" : "Same shape as the previous card?");

      function newCard(n, label) {
        const col = level >= 2 ? rng.pick(COLS) : null;
        const rot = level >= 2 ? rng.pick([0, 0, 90, 180, 270, 45]) : 0;
        const el = h(`<div class="sm-card enter">${svgOf(n, col, rot)}<div class="sm-stamp yes">YES</div><div class="sm-stamp no">NO</div><div class="sm-flash"></div></div>`);
        if (card && card.parentNode === stack) stack.insertBefore(el, card); else stack.appendChild(el);
        el.addEventListener("animationend", () => el.classList.remove("enter"), { once: true });
        bindDrag(el);
        q.innerHTML = label;
        return el;
      }
      function pick() {
        const k = back();
        const target = hist[hist.length - k];
        if (target && rng() < 0.45) return target;
        // in 2-back, sometimes show the 1-back shape as a lure
        if (level === 3 && rng() < 0.3) return hist[hist.length - 1];
        return rng.pick(NAMES);
      }
      function fly(el, dir) {
        el.style.transition = "transform .45s var(--ease), opacity .45s";
        el.style.transform = `translateX(${dir * 420}px) rotate(${dir * 24}deg)`;
        el.style.opacity = "0";
        setTimeout(() => el.remove(), 460);
      }
      function show() {
        const n = pick();
        hist.push(n);
        card = newCard(n, question());
        shownAt = Date.now();
      }

      function answer(yes) {
        if (!live || !card) return;
        const cur = hist[hist.length - 1], cmp = hist[hist.length - 1 - back()];
        const isSame = cur === cmp;
        const correct = yes === isSame;
        total++; rts.push(Date.now() - shownAt); perLevel[level][1]++;
        const fl = card.querySelector(".sm-flash"); fl.className = "sm-flash " + (correct ? "ok" : "bad");
        const r = stack.getBoundingClientRect(), br = body.getBoundingClientRect();
        if (correct) {
          right++; streak++; perLevel[level][0]++;
          const gain = 10 * mult * level;
          pts += gain; ptsEl.textContent = pts.toLocaleString("en-IN");
          BL.floatPts(body, r.left - br.left + r.width / 2 - 14, r.top - br.top - 6, "+" + gain);
          if (streak % 3 === 0 && mult < 5) { mult++; multEl.textContent = "x" + mult; multEl.classList.add("bump"); setTimeout(() => multEl.classList.remove("bump"), 350); sfx.win(); }
          else sfx.tone(700 + mult * 90, { type: "triangle", dur: 0.12, vol: 0.15 });
          haptic(8);
        } else {
          streak = 0; mult = 1; multEl.textContent = "x1";
          BL.floatPts(body, r.left - br.left + r.width / 2 - 14, r.top - br.top - 6, isSame ? "it matched" : "different", true);
          sfx.bad(); haptic([25, 30, 25]);
        }
        const old = card;
        card.querySelector(yes ? ".sm-stamp.yes" : ".sm-stamp.no").style.opacity = 1;
        setTimeout(() => fly(old, yes ? 1 : -1), 90);
        show();
      }
      bNo.onclick = () => answer(false);
      bYes.onclick = () => answer(true);
      const onKey = (e) => { if (e.key === "ArrowLeft") answer(false); if (e.key === "ArrowRight") answer(true); };
      window.addEventListener("keydown", onKey);

      function bindDrag(el) {
        let sx = 0, dx = 0, drag = false;
        el.addEventListener("pointerdown", (e) => { if (!live) return; drag = true; sx = e.clientX; dx = 0; el.style.transition = "none"; el.setPointerCapture(e.pointerId); });
        el.addEventListener("pointermove", (e) => {
          if (!drag) return; dx = e.clientX - sx;
          el.style.transform = `translateX(${dx}px) rotate(${dx / 14}deg)`;
          el.querySelector(".sm-stamp.yes").style.opacity = Math.max(0, dx / 90);
          el.querySelector(".sm-stamp.no").style.opacity = Math.max(0, -dx / 90);
        });
        const end = () => {
          if (!drag) return; drag = false;
          if (Math.abs(dx) > 80 && el === card) answer(dx > 0);
          else { el.style.transition = ""; el.style.transform = ""; el.querySelectorAll(".sm-stamp").forEach((s) => (s.style.opacity = 0)); }
        };
        el.addEventListener("pointerup", end); el.addEventListener("pointercancel", end);
      }

      async function setLevel(l) {
        level = l;
        [...$("#smL", body).children].forEach((s, i) => s.classList.toggle("on", i === l - 1));
        live = false; timer && timer.pause();
        BL.levelBanner(body, `LEVEL ${l} · POINTS ×${l}`, l === 2 ? "Colour tricks 🎨" : "2-back 🧠");
        $("#smBack", body).classList.toggle("on", l === 3);
        await wait(1400);
        if (!api.alive()) return;
        // re-seed history with fresh cards for the new rule
        hist.length = 0;
        if (card) { fly(card, -1); card = null; }
        const first = rng.pick(NAMES); hist.push(first);
        card = newCard(first, l === 3 ? "Remember this one…" : "Remember this card 👀");
        await wait(900);
        if (l === 3) {
          if (!api.alive()) return;
          const second = rng.pick(NAMES.filter((x) => x !== first)); fly(card, -1); hist.push(second);
          card = newCard(second, "…and this one");
          await wait(900);
        }
        if (!api.alive()) return;
        fly(card, -1); show(); live = true; timer && timer.resume();
      }

      async function run() {
        await BL.countdown(body);
        if (!api.alive()) return;
        const first = rng.pick(NAMES); hist.push(first);
        card = newCard(first, "Remember this card 👀");
        await wait(1300);
        if (!api.alive()) return;
        fly(card, -1); show();
        live = true; bNo.disabled = bYes.disabled = false; t0 = Date.now();
        timer = BL.timer(api, DURATION, {
          el: $("#smT", body),
          onEnd: end,
          onTick: (left) => {
            const el = DURATION - left;
            if (level === 1 && el >= 20) setLevel(2);
            else if (level === 2 && el >= 40) setLevel(3);
          },
        });
      }
      function end() {
        live = false; bNo.disabled = bYes.disabled = true;
        q.textContent = "Time!";
        const acc = total ? Math.round((right / total) * 100) : 0;
        const avg = rts.length ? Math.round(rts.reduce((a, b) => a + b, 0) / rts.length) : 0;
        const l3 = perLevel[3][1] ? Math.round((perLevel[3][0] / perLevel[3][1]) * 100) + "%" : "–";
        setTimeout(() => api.finish({
          score: pts, level: right,
          title: acc >= 90 && total >= 40 ? "Lightning focus ⚡" : acc >= 80 ? "Sharp and quick" : "Good sprint",
          sub: `${right} of ${total} correct · 2-back accuracy ${l3}`,
          big: pts.toLocaleString("en-IN"),
          stats: [["accuracy", acc + "%"], ["avg reaction", (avg / 1000).toFixed(2) + "s"], ["2-back", l3]],
          meta: { accuracy: acc, avg_ms: avg, answers: total },
        }), 600);
      }
      run();
      return () => window.removeEventListener("keydown", onKey);
    },
  });
})();
