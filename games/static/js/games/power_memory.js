/* Power Memory — digit span. Numbers flash one at a time; type them back.
   Forward = remember. Backward = remember AND flip (harder, trains working memory).
   Get it right → one more digit. Two misses in a row at the same length → game over. */
(function () {
  const { h, $, sfx, haptic, wait, rand } = BL;
  const css = `
  .pm-stage{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:0;padding:0 20px}
  .pm-disp{width:190px;height:190px;border-radius:50%;display:grid;place-items:center;position:relative;background:#fff;
    box-shadow:var(--shadow),inset 0 0 0 10px var(--yellow-soft)}
  .pm-disp svg{position:absolute;inset:0;transform:rotate(-90deg)}
  .pm-disp circle{fill:none;stroke-width:10;stroke-linecap:round}
  .pm-dig{font-size:92px;font-weight:700;letter-spacing:-2px;line-height:1;font-variant-numeric:tabular-nums}
  .pm-dig.in{animation:pmIn .55s var(--spring)}
  .pm-dig.out{animation:pmOut .25s var(--ease) forwards}
  @keyframes pmIn{from{transform:scale(.4) translateY(20px);opacity:0;filter:blur(6px)}}
  @keyframes pmOut{to{transform:scale(1.25);opacity:0;filter:blur(4px)}}
  .pm-slots{display:flex;gap:7px;justify-content:center;flex-wrap:wrap;margin:26px 0 6px;min-height:54px}
  .pm-slot{width:40px;height:52px;border-radius:14px;background:#fff;border:1.5px solid var(--line);display:grid;place-items:center;
    font-size:26px;font-weight:700;transition:all .3s var(--spring);box-shadow:var(--shadow-sm)}
  .pm-slot.cur{border-color:var(--yellow);box-shadow:0 0 0 4px var(--yellow-soft)}
  .pm-slot.fill{animation:pmPop .35s var(--spring)}
  .pm-slot.ok{background:var(--teal);color:#fff;border-color:transparent;transform:translateY(-4px)}
  .pm-slot.bad{background:var(--coral-soft);color:#C23B3B;border-color:#FFB3B3}
  @keyframes pmPop{from{transform:scale(.6)}}
  .pm-ans{font-size:13px;color:var(--muted);min-height:18px;text-align:center}
  .pm-ans b{color:var(--ink);letter-spacing:3px}
  .pm-pad{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:8px 22px 22px;transition:opacity .35s,transform .45s var(--ease)}
  .pm-pad.hide{opacity:.25;pointer-events:none;transform:translateY(10px)}
  .pm-k{height:58px;border-radius:18px;background:#fff;border:1px solid var(--line);font-size:24px;font-weight:600;box-shadow:0 4px 0 #EFE8D3;
    transition:transform .12s,box-shadow .12s,background .2s}
  .pm-k:active{transform:translateY(3px);box-shadow:0 1px 0 #EFE8D3;background:var(--yellow-soft)}
  .pm-k.alt{background:#F6F2E6;font-size:18px}
  .pm-dir{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:99px;font-weight:800;font-size:13px;letter-spacing:1px;margin-bottom:16px;transition:all .35s var(--spring)}
  .pm-dir.fwd{background:var(--teal-soft);color:#0E7D70}
  .pm-dir.bwd{background:var(--ink);color:var(--yellow)}
  .pm-dir.pop{animation:pop .5s var(--spring)}`;

  BL.register({
    id: "power_memory",
    name: "Power Memory",
    tag: "Numbers flash fast. Type them back, forwards or reversed, before time’s up.",
    tint: "#E4F7F3",
    chips: ["Working memory", "Adaptive"],
    icon: `<svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="18" fill="#fff" stroke="#1E2235" stroke-width="1.6"/><path d="M24 6a18 18 0 0117.2 12.6" fill="none" stroke="#1FB5A3" stroke-width="4" stroke-linecap="round"/><text x="24" y="31" text-anchor="middle" font-family="Outfit,system-ui" font-weight="700" font-size="19" fill="#1E2235">7</text></svg>`,
    formatBest: (s) => `${s.toLocaleString("en-IN")} pts`,
    intro: {
      desc: "Digit span, turned into a sprint. Strings get longer, flashes get faster, and some rounds must be typed backwards.",
      how: ["Watch the digits flash one at a time", "Type them back before the ring runs out. Fast answers score a bonus", "3 hearts. Daily Challenge is always Mixed mode"],
      options: [{ key: "dir", values: [["mixed", "Mixed"], ["forward", "Forward"], ["backward", "Backward"]] }],
      science: "Typical adult span is about 7 forward and 5 backward (Miller, 1956). Backward rounds score 1.5×.",
      cta: "Start",
    },
    start(body, api, opts) {
      const rng = api.rng;
      const dir = api.mode === "daily" ? "mixed" : opts.dir || "mixed";
      body.innerHTML = `<style>${css}</style>
        <div class="status" id="pmS" style="margin-top:8px">Focus on the circle</div>
        <div class="pm-stage">
          <div class="pm-dir fwd" id="pmDir">→ FORWARD</div>
          <div class="pm-disp"><svg viewBox="0 0 190 190"><circle cx="95" cy="95" r="85" stroke="#FFF3CC"/><circle id="pmArc" cx="95" cy="95" r="85" stroke="#FFC83D" stroke-dasharray="534" stroke-dashoffset="534" style="transition:stroke .3s"/></svg><div class="pm-dig" id="pmD">·</div></div>
          <div class="pm-slots" id="pmSl"></div>
          <div class="pm-ans" id="pmA"></div>
        </div>
        <div class="pm-pad hide" id="pmPad">${[1, 2, 3, 4, 5, 6, 7, 8, 9].map((d) => `<button class="pm-k" data-d="${d}">${d}</button>`).join("")}<button class="pm-k alt" data-d="del">⌫</button><button class="pm-k" data-d="0">0</button><button class="pm-k alt" data-d="clr">Clear</button></div>`;
      const disp = $("#pmD", body), arc = $("#pmArc", body), slots = $("#pmSl", body), ans = $("#pmA", body), pad = $("#pmPad", body), status = $("#pmS", body), dirEl = $("#pmDir", body);
      api.pills.innerHTML = `<span class="pill"><span class="hearts" id="pmH"><span>❤️</span><span>❤️</span><span>❤️</span></span></span><span class="pill yellow" id="pmP">0</span>`;
      const say = (t) => { status.textContent = t; status.classList.remove("flash"); void status.offsetWidth; status.classList.add("flash"); };

      let span = 3, best = 0, bestBack = 0, lives = 3, pts = 0, input = [], accepting = false, resolve = null, rounds = 0, deadline = 0, inputTime = 0, arcMode = "show";
      const setPts = (v) => { pts = v; $("#pmP").textContent = v.toLocaleString("en-IN"); };
      const makeSeq = (n) => { const s = []; while (s.length < n) { const d = rng.int(10); if (d !== s[s.length - 1]) s.push(d); } return s; };

      function drawSlots(state) {
        slots.innerHTML = "";
        for (let i = 0; i < span; i++) {
          const s = h(`<div class="pm-slot${i === input.length && accepting ? " cur" : ""}${state ? " " + state : ""}">${input[i] ?? ""}</div>`);
          if (span > 7) { s.style.width = "34px"; s.style.height = "46px"; s.style.fontSize = "22px"; }
          if (state === "ok") s.style.transitionDelay = i * 40 + "ms";
          slots.appendChild(s);
        }
      }
      function key(d) {
        if (!accepting) return;
        haptic(6);
        if (d === "del") { input.pop(); sfx.soft(); }
        else if (d === "clr") { input = []; sfx.soft(); }
        else if (input.length < span) { input.push(+d); sfx.tone(440 + input.length * 55, { type: "triangle", dur: 0.08, vol: 0.1 }); }
        drawSlots();
        if (d !== "del" && d !== "clr" && slots.children[input.length - 1]) slots.children[input.length - 1].classList.add("fill");
        if (input.length === span) { accepting = false; pad.classList.add("hide"); setTimeout(() => resolve("done"), 200); }
      }
      pad.querySelectorAll(".pm-k").forEach((b) => b.addEventListener("pointerdown", (e) => { e.preventDefault(); key(b.dataset.d); }));
      const onKey = (e) => { if (/^[0-9]$/.test(e.key)) key(e.key); else if (e.key === "Backspace") key("del"); };
      window.addEventListener("keydown", onKey);

      // answer countdown on the ring
      (function tick() {
        if (!api.alive()) return;
        if (accepting) {
          const left = Math.max(0, deadline - Date.now()) / 1000;
          arc.style.strokeDashoffset = 534 * (1 - left / inputTime);
          arc.style.stroke = left < 2 ? "#FF6B6B" : "#FFC83D";
          if (left <= 0) { accepting = false; pad.classList.add("hide"); resolve("timeout"); }
        }
        requestAnimationFrame(tick);
      })();

      async function show(seq, back) {
        accepting = false; pad.classList.add("hide"); input = []; drawSlots(); ans.innerHTML = "";
        dirEl.className = "pm-dir pop " + (back ? "bwd" : "fwd"); dirEl.textContent = back ? "↩ BACKWARD · 1.5×" : "→ FORWARD";
        arc.style.stroke = "#1FB5A3"; arc.style.transition = "stroke-dashoffset .4s var(--ease)"; arc.style.strokeDashoffset = 534;
        say(`${span} digits`);
        disp.textContent = "·";
        await wait(750);
        const on = Math.max(420, 760 - (span - 3) * 55);
        for (let i = 0; i < seq.length; i++) {
          if (!api.alive()) return;
          disp.className = "pm-dig"; void disp.offsetWidth;
          disp.textContent = seq[i]; disp.classList.add("in");
          arc.style.strokeDashoffset = 534 * (1 - (i + 1) / seq.length);
          sfx.tone(620, { dur: 0.09, vol: 0.08 });
          await wait(on);
          disp.classList.add("out");
          await wait(200);
        }
        disp.className = "pm-dig in"; disp.textContent = "?";
        say(back ? "Type it BACKWARDS ↩" : "Type it in order");
        arc.style.transition = "stroke .3s";
        inputTime = 2.5 + span * 0.9; deadline = Date.now() + inputTime * 1000;
        accepting = true; pad.classList.remove("hide"); drawSlots();
        return new Promise((r) => (resolve = r));
      }

      async function loop() {
        await BL.countdown(body);
        while (api.alive() && lives > 0) {
          rounds++;
          const back = dir === "backward" || (dir === "mixed" && span >= 4 && rng() < 0.45);
          const seq = makeSeq(span);
          const how = await show(seq, back);
          if (!api.alive()) return;
          const leftSec = Math.max(0, deadline - Date.now()) / 1000;
          const want = back ? seq.slice().reverse() : seq;
          const ok = how === "done" && want.every((d, i) => d === input[i]);
          if (ok) {
            best = Math.max(best, span); if (back) bestBack = Math.max(bestBack, span);
            const gain = Math.round(span * 10 * (back ? 1.5 : 1) + leftSec * 5);
            setPts(pts + gain);
            drawSlots("ok"); arc.style.stroke = "#1FB5A3"; sfx.good(); disp.textContent = "✓";
            BL.combo(body, `+${gain}${leftSec > inputTime * 0.5 ? " ⚡ fast" : ""}`);
            say(span >= 8 ? "Elite span 🧠" : span >= 6 ? "Strong memory!" : "Correct!");
            await wait(1000);
            span++;
            if (span === 7) { BL.levelBanner(body, "SPAN 7", "Above the average adult 🧠"); await wait(1500); }
          } else {
            lives--;
            $("#pmH").children[lives].classList.add("lost");
            drawSlots("bad"); slots.classList.add("shake"); setTimeout(() => slots.classList.remove("shake"), 460);
            arc.style.stroke = "#FF6B6B"; sfx.bad(); haptic([30, 40, 30]); disp.textContent = how === "timeout" ? "⏱" : "✕";
            ans.innerHTML = `It was <b>${want.join("")}</b>`;
            say(how === "timeout" ? "Out of time" : lives ? `${lives} heart${lives > 1 ? "s" : ""} left` : "Out of hearts");
            await wait(1800);
          }
        }
        if (!api.alive()) return;
        api.finish({
          score: pts, level: best,
          title: best > 7 ? "Above average 🧠" : best === 7 ? "Right on average" : "Solid start",
          sub: `Longest span ${best || 0}${bestBack ? ` · ${bestBack} backwards` : ""}`,
          big: pts.toLocaleString("en-IN"),
          stats: [["span", best || 0], ["backward", bestBack || "–"], ["avg adult", "7 / 5"]],
          meta: { dir, best, bestBack },
        });
      }
      loop();
      return () => window.removeEventListener("keydown", onKey);
    },
  });
})();
