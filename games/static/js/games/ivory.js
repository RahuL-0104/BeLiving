/* Ivory — a melody memory game on piano keys.
   The piano plays a tune, you play it back. Each round adds one note.
   Classic = 8 white keys, Pro = all 13 keys. One free retry per game. */
(function () {
  const { h, $, sfx, haptic, wait, rand } = BL;
  const NOTE_TIME = 3.2; // seconds allowed per note
  const WHITE = [["C", 261.63], ["D", 293.66], ["E", 329.63], ["F", 349.23], ["G", 392.0], ["A", 440.0], ["B", 493.88], ["C", 523.25]];
  const BLACK = [[0, "C#", 277.18], [1, "D#", 311.13], [3, "F#", 369.99], [4, "G#", 415.3], [5, "A#", 466.16]]; // [after white idx]
  const HUES = ["#FF8FAB", "#FFB4A2", "#FFC83D", "#B8E986", "#7ED9C3", "#8EC5FF", "#C9A7FF", "#FF8FAB"];
  const KEYS = "asdfghjk";
  const css = `
  .iv-stage{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;min-height:0}
  .iv-orb{width:150px;height:150px;border-radius:50%;display:grid;place-items:center;position:relative;
    background:radial-gradient(circle at 35% 30%,#fff,#FFF3CC 60%,#FFE08A);box-shadow:0 18px 40px -12px var(--yellow-glow),inset 0 -6px 16px rgba(242,169,0,.18);transition:transform .35s var(--spring),box-shadow .35s}
  .iv-orb.pulse{transform:scale(1.08);box-shadow:0 22px 50px -10px var(--c,var(--yellow-glow))}
  .iv-orb b{font-size:46px;font-weight:700;letter-spacing:-1px;line-height:1}
  .iv-orb small{display:block;font-size:12px;color:var(--muted);font-weight:600;letter-spacing:1px;text-transform:uppercase;margin-top:4px;text-align:center}
  .iv-ring{position:absolute;inset:-12px;border-radius:50%;border:2px solid var(--c,#FFC83D);opacity:0}
  .iv-ring.go{animation:ivRing .8s var(--ease)}
  @keyframes ivRing{from{transform:scale(.9);opacity:.7}to{transform:scale(1.35);opacity:0}}
  .iv-dots{display:flex;gap:6px;margin-top:22px;flex-wrap:wrap;justify-content:center;max-width:300px;min-height:12px}
  .iv-dots i{width:10px;height:10px;border-radius:50%;background:#EFE8D3;transition:background .3s,transform .3s var(--spring)}
  .iv-dots i.on{background:var(--c);transform:scale(1.25)}
  .iv-piano{position:relative;height:250px;margin:0 12px 22px;display:flex;gap:4px;padding:10px 8px 8px;border-radius:24px;
    background:linear-gradient(#2A2F45,#1E2235);box-shadow:var(--shadow-lg)}
  .iv-w{flex:1;position:relative;border-radius:4px 4px 14px 14px;background:linear-gradient(#fff 70%,#F5F0E2);
    box-shadow:inset 0 -8px 0 #E8E1CD,0 2px 0 rgba(0,0,0,.2);transition:transform .12s,box-shadow .12s,background .2s;overflow:hidden}
  .iv-w span{position:absolute;bottom:14px;left:0;right:0;text-align:center;font-size:11px;font-weight:700;color:#C4BCA6}
  .iv-w.down{transform:translateY(3px);box-shadow:inset 0 -3px 0 #E8E1CD;background:linear-gradient(#fff 10%,var(--c))}
  .iv-w.down span{color:#fff}
  .iv-b{position:absolute;top:10px;width:9%;height:58%;border-radius:3px 3px 9px 9px;background:linear-gradient(#3C425C,#141726);z-index:2;
    box-shadow:inset 0 -6px 0 #0B0D16,0 4px 8px rgba(0,0,0,.35);transition:transform .12s,box-shadow .12s,background .2s}
  .iv-b.down{transform:translateY(3px);box-shadow:inset 0 -2px 0 #0B0D16;background:linear-gradient(#3C425C,var(--c))}
  .iv-b.off{pointer-events:none}
  .iv-lock .iv-w,.iv-lock .iv-b{pointer-events:none}
  .iv-orb svg{position:absolute;inset:-8px;width:calc(100% + 16px);height:calc(100% + 16px);transform:rotate(-90deg)}
  .iv-orb svg circle{fill:none;stroke-width:6;stroke-linecap:round}
  .iv-rev{position:absolute;top:-40px;z-index:3;left:50%;transform:translateX(-50%);background:var(--ink);color:var(--yellow);font-size:11px;font-weight:800;letter-spacing:1.2px;padding:5px 10px;border-radius:99px;white-space:nowrap;opacity:0;transition:opacity .3s}
  .iv-rev.on{opacity:1;animation:pop .5s var(--spring)}
  .iv-note{position:absolute;font-size:26px;pointer-events:none;z-index:5;animation:ivNote 1.1s var(--ease) forwards}
  @keyframes ivNote{to{transform:translate(var(--dx),-170px) rotate(var(--rot)) scale(1.3);opacity:0}}`;

  BL.register({
    id: "ivory",
    name: "Ivory",
    tag: "The piano plays a tune, you play it back. It speeds up, and some rounds flip.",
    tint: "#EEF0FF",
    chips: ["Memory", "Sound"],
    icon: `<svg viewBox="0 0 48 48"><rect x="5" y="9" width="38" height="30" rx="5" fill="#1E2235"/>${[0, 1, 2, 3, 4].map((i) => `<rect x="${7.5 + i * 6.8}" y="11.5" width="6" height="25" rx="1.6" fill="${i === 2 ? "#FFC83D" : "#fff"}"/>`).join("")}${[0, 1, 3].map((i) => `<rect x="${12.2 + i * 6.8}" y="11.5" width="3.6" height="14" rx="1" fill="#1E2235"/>`).join("")}</svg>`,
    formatBest: (s) => `${s.toLocaleString("en-IN")} pts`,
    intro: {
      desc: "A musical memory battle. Every round the tune grows by a note and the tempo gets faster.",
      how: ["Listen and watch the keys light up", "Play it back before the ring runs out (3s per note)", "Every 4th round is REVERSE: play it backwards. 3 hearts. Daily is Classic"],
      options: [{ key: "keys", values: [["classic", "Classic · 8 keys"], ["pro", "Pro · 13 keys"]] }],
      science: "Sequence recall trains auditory working memory. Reverse rounds train mental manipulation, the harder half of working memory.",
      cta: "Play",
    },
    start(body, api, opts) {
      const pro = api.mode !== "daily" && opts.keys === "pro"; // daily is always Classic so scores compare
      const rng = api.rng;
      body.innerHTML = `<style>${css}</style>
        <div class="status" id="ivS" style="margin-top:8px">Listen closely…</div>
        <div class="iv-stage"><div class="iv-orb" id="ivO"><div class="iv-rev" id="ivRev">↩ REVERSE</div><svg viewBox="0 0 166 166"><circle cx="83" cy="83" r="78" stroke="#FFF3CC"/><circle id="ivArc" cx="83" cy="83" r="78" stroke="#FFC83D" stroke-dasharray="490" stroke-dashoffset="490"/></svg><div class="iv-ring" id="ivR"></div><div><b id="ivN">2</b><small>notes</small></div></div><div class="iv-dots" id="ivD"></div></div>
        <div class="iv-piano iv-lock" id="ivP"></div>`;
      const piano = $("#ivP", body), status = $("#ivS", body), orb = $("#ivO", body), ring = $("#ivR", body), dots = $("#ivD", body), arc = $("#ivArc", body);
      api.pills.innerHTML = `<span class="pill"><span class="hearts" id="ivH"><span>❤️</span><span>❤️</span><span>❤️</span></span></span><span class="pill yellow" id="ivP2">0</span>`;
      const say = (t) => { status.textContent = t; status.classList.remove("flash"); void status.offsetWidth; status.classList.add("flash"); };

      const keys = [], blacks = [];
      WHITE.forEach(([n, f], i) => { const el = h(`<button class="iv-w" aria-label="${n}"><span>${n}</span></button>`); piano.appendChild(el); keys.push({ el, freq: f, color: HUES[i], name: n }); });
      BLACK.forEach(([after, n, f]) => { const el = h(`<button class="iv-b${pro ? "" : " off"}" aria-label="${n}"></button>`); el._after = after; blacks.push(el); piano.appendChild(el); if (pro) keys.push({ el, freq: f, color: "#9B8CFF", name: n }); });
      keys.forEach((k) => k.el.style.setProperty("--c", k.color));
      const whites = [...piano.querySelectorAll(".iv-w")];
      const placeBlack = () => blacks.forEach((b) => { const w = whites[b._after]; b.style.left = w.offsetLeft + w.offsetWidth + 2 - b.offsetWidth / 2 + "px"; });
      requestAnimationFrame(placeBlack);
      window.addEventListener("resize", placeBlack);

      function light(k, dur = 300) {
        sfx.piano(k.freq, { dur: 1.2 });
        k.el.classList.add("down");
        orb.style.setProperty("--c", k.color + "aa"); ring.style.setProperty("--c", k.color);
        orb.classList.add("pulse"); ring.classList.remove("go"); void ring.offsetWidth; ring.classList.add("go");
        const r = k.el.getBoundingClientRect(), br = body.getBoundingClientRect();
        const note = h(`<div class="iv-note">${["♪", "♫", "♩", "♬"][rand(4)]}</div>`);
        note.style.left = r.left - br.left + r.width / 2 - 10 + "px"; note.style.top = r.top - br.top + 20 + "px";
        note.style.color = k.color; note.style.setProperty("--dx", (Math.random() - 0.5) * 60 + "px"); note.style.setProperty("--rot", (Math.random() - 0.5) * 50 + "deg");
        body.appendChild(note); setTimeout(() => note.remove(), 1150);
        setTimeout(() => { k.el.classList.remove("down"); orb.classList.remove("pulse"); }, dur);
      }

      const seq = [];
      let pts = 0, lives = 3, round = 0, best = 0, reverseWins = 0, accepting = false, idx = 0, want = [], resolveTurn = null, noteDeadline = 0, turnStart = 0;
      const setPts = (v) => { pts = v; $("#ivP2").textContent = v.toLocaleString("en-IN"); };
      const nextNote = () => { let n; do { n = rng.int(keys.length); } while (seq.length >= 2 && seq[seq.length - 1] === n && seq[seq.length - 2] === n); return n; };
      const drawDots = (filled) => (dots.innerHTML = want.map((n, i) => `<i class="${i < filled ? "on" : ""}" style="--c:${keys[n].color}"></i>`).join(""));

      // per-note countdown ring
      (function tick() {
        if (!api.alive()) return;
        if (accepting) {
          const left = Math.max(0, noteDeadline - Date.now()) / 1000;
          arc.style.strokeDashoffset = 490 * (1 - left / NOTE_TIME);
          arc.style.stroke = left < 1 ? "#FF6B6B" : "#FFC83D";
          if (left <= 0) { accepting = false; piano.classList.add("iv-lock"); sfx.bad(); say("Too slow ⏱"); resolveTurn && resolveTurn(false); }
        } else arc.style.strokeDashoffset = 490;
        requestAnimationFrame(tick);
      })();

      function press(k) {
        if (!accepting) return;
        haptic(6);
        const i = keys.indexOf(k);
        light(k, 180);
        if (i === want[idx]) {
          idx++; drawDots(idx); setPts(pts + 5 * want.length);
          noteDeadline = Date.now() + NOTE_TIME * 1000;
          if (idx === want.length) { accepting = false; piano.classList.add("iv-lock"); resolveTurn(true); }
        } else {
          accepting = false; piano.classList.add("iv-lock");
          k.el.style.setProperty("--c", "#FF6B6B"); setTimeout(() => k.el.style.setProperty("--c", k.color), 400);
          piano.classList.add("shake"); setTimeout(() => piano.classList.remove("shake"), 460);
          setTimeout(() => sfx.bad(), 120); haptic([30, 40, 30]);
          resolveTurn(false);
        }
      }
      keys.forEach((k) => k.el.addEventListener("pointerdown", (e) => { e.preventDefault(); press(k); }));
      const onKey = (e) => { const i = KEYS.indexOf(e.key.toLowerCase()); if (i >= 0 && keys[i]) press(keys[i]); };
      window.addEventListener("keydown", onKey);

      async function playback(reverse) {
        accepting = false; piano.classList.add("iv-lock");
        want = reverse ? seq.slice().reverse() : seq.slice();
        $("#ivRev", body).classList.toggle("on", reverse);
        say(reverse ? "Listen… then play it BACKWARDS ↩" : `Listen · ${seq.length} notes`);
        $("#ivN").textContent = seq.length;
        dots.innerHTML = seq.map(() => "<i></i>").join("");
        await wait(650);
        const gap = Math.max(260, 600 - round * 28);
        for (let i = 0; i < seq.length; i++) {
          if (!api.alive()) return;
          light(keys[seq[i]], gap * 0.6);
          dots.children[i] && dots.children[i].classList.add("on"); dots.children[i] && dots.children[i].style.setProperty("--c", keys[seq[i]].color);
          await wait(gap);
        }
        await wait(160);
        drawDots(0); idx = 0;
        say(reverse ? "Your turn · BACKWARDS ↩" : "Your turn 🎹");
        piano.classList.remove("iv-lock"); turnStart = Date.now(); noteDeadline = Date.now() + NOTE_TIME * 1000; accepting = true;
        return new Promise((r) => (resolveTurn = r));
      }

      async function loop() {
        await BL.countdown(body);
        seq.push(nextNote(), nextNote());
        while (api.alive() && lives > 0) {
          round++;
          const reverse = round >= 4 && round % 4 === 0;
          if (reverse) { BL.levelBanner(body, `ROUND ${round}`, "Reverse round ↩"); await wait(1500); }
          const ok = await playback(reverse);
          resolveTurn = null;
          if (!api.alive()) return;
          if (ok) {
            best = Math.max(best, seq.length);
            const secsPerNote = (Date.now() - turnStart) / 1000 / seq.length;
            let gain = seq.length * 15 * (reverse ? 2 : 1);
            const fast = secsPerNote < 0.7;
            if (fast) gain += 25;
            if (reverse) reverseWins++;
            setPts(pts + gain); sfx.good();
            BL.combo(body, `${reverse ? "Reverse! " : ""}+${gain}${fast ? " ⚡" : ""}`);
            say(["Nice ear!", "Smooth 🎶", "Maestro mode", "Keep the groove", "Unreal memory ✨"][Math.min(4, Math.floor(seq.length / 3))]);
            await wait(900);
            seq.push(nextNote());
          } else {
            lives--;
            $("#ivH").children[lives].classList.add("lost");
            if (lives > 0) { say(`${lives} heart${lives > 1 ? "s" : ""} left · same tune again`); await wait(1400); round--; }
            else {
              say("That’s the one that got you");
              await wait(400);
              for (let i = 0; i < want.length && api.alive(); i++) { light(keys[want[i]], 200); await wait(260); }
              await wait(500);
            }
          }
        }
        if (!api.alive()) return;
        api.finish({
          score: pts, level: best,
          title: best >= 9 ? "Maestro memory 🎼" : best >= 6 ? "Great ear!" : "Nice warm-up",
          sub: best ? `Longest melody: ${best} notes${reverseWins ? ` · ${reverseWins} reverse round${reverseWins > 1 ? "s" : ""} cracked` : ""}` : "Melodies take a few tries to click",
          big: pts.toLocaleString("en-IN"),
          stats: [["longest", best + " notes"], ["reverse wins", reverseWins], ["keys", pro ? "Pro" : "Classic"]],
          meta: { keys: pro ? "pro" : "classic", longest: best },
        });
      }
      loop();
      return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("resize", placeBlack); };
    },
  });
})();
