/* Pattern Recall — 60 seconds. Yellow tiles flash, tap them back from memory.
   Perfect round: level up, +2s, combo grows. Wrong tile: −3s, level drops.
   Level 5+: purple decoy tiles flash too. Only tap the yellow ones.
   Level 8+: the flash gets shorter. */
(function () {
  const { h, $, sfx, haptic, wait } = BL;
  const DURATION = 60;
  const css = `
  .pr-wrap{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:0 18px 26px;position:relative}
  .pr-grid{display:grid;gap:10px;width:100%;max-width:360px;perspective:900px;transition:transform .45s var(--ease),opacity .35s}
  .pr-grid.out{transform:scale(.85);opacity:0}
  .pr-tile{position:relative;aspect-ratio:1;transform-style:preserve-3d;transition:transform .5s var(--spring);cursor:pointer;animation:prIn .45s var(--spring) backwards}
  @keyframes prIn{from{transform:scale(.3);opacity:0}}
  .pr-tile .f,.pr-tile .b{position:absolute;inset:0;border-radius:16px;backface-visibility:hidden;-webkit-backface-visibility:hidden}
  .pr-tile .f{background:#fff;border:1px solid var(--line);box-shadow:0 4px 0 #EFE8D3,var(--shadow-sm)}
  .pr-tile .b{transform:rotateY(180deg);background:linear-gradient(145deg,#FFD866,#FFB800);box-shadow:0 0 0 3px #fff inset,0 8px 22px -6px var(--yellow-glow)}
  .pr-tile.flip{transform:rotateY(180deg)}
  .pr-tile.decoy .b{background:linear-gradient(145deg,#B7A8FF,#7C68F0);box-shadow:0 0 0 3px #fff inset,0 8px 22px -6px rgba(124,104,240,.5)}
  .pr-tile.ok .b{background:linear-gradient(145deg,#4AD6C3,#17A592);box-shadow:0 0 0 3px #fff inset,0 8px 22px -6px rgba(31,181,163,.5)}
  .pr-tile.bad .b{background:linear-gradient(145deg,#FF8E8E,#F25555)}
  .pr-tile.miss .b{background:repeating-linear-gradient(45deg,#FFE7A3 0 8px,#FFF3CC 8px 16px);box-shadow:0 0 0 2px #FFC83D inset}
  .pr-tile:active:not(.flip) .f{transform:translateY(2px);box-shadow:0 2px 0 #EFE8D3}
  .pr-tile.hop{animation:prHop .5s var(--spring)}
  @keyframes prHop{40%{transform:rotateY(180deg) translateY(-10px) scale(1.06)}}
  .pr-lv{display:flex;gap:8px;align-items:center;justify-content:center;margin:2px 0 14px;font-size:13px;font-weight:700;color:var(--ink-2)}
  .pr-lv i{font-style:normal;padding:4px 10px;border-radius:99px;background:var(--yellow-soft);color:#7A5600}
  .pr-lv i.decoy{background:#ECE8FF;color:#5A47D6}`;

  const gridFor = (t) => (t <= 4 ? 3 : t <= 6 ? 4 : t <= 9 ? 5 : 6);

  BL.register({
    id: "pattern_recall",
    name: "Pattern Recall",
    tag: "Remember where the tiles flashed. Purple decoys show up as you level up.",
    tint: "#FFF3CC",
    chips: ["Memory", "60 sec"],
    icon: `<svg viewBox="0 0 48 48">${[0, 1, 2].map((r) => [0, 1, 2].map((c) => `<rect x="${5 + c * 13.5}" y="${5 + r * 13.5}" width="11" height="11" rx="3.2" fill="${[1, 5, 8].includes(r * 3 + c) ? "#FFB800" : r * 3 + c === 3 ? "#8E7BFF" : "#fff"}" stroke="#1E2235" stroke-width="1.4"/>`).join("")).join("")}</svg>`,
    formatBest: (s) => `${s.toLocaleString("en-IN")} pts`,
    intro: {
      desc: "A 60-second spatial memory sprint. It keeps getting harder for as long as you keep getting it right.",
      how: ["Watch which tiles flash yellow", "Tap only those tiles. Perfect round = level up and bonus seconds", "Level 5+: ignore the purple decoys. A wrong tap costs 3s"],
      science: "Trains visuospatial working memory and inhibition, the skill of ignoring what doesn’t matter.",
      cta: "Start sprint",
    },
    start(body, api) {
      const rng = api.rng;
      body.innerHTML = `<style>${css}</style>
        ${BL.timerBarHTML("prT")}
        <div class="status" id="prS" style="margin-top:10px">Get ready…</div>
        <div class="pr-wrap"><div class="pr-lv" id="prLv"></div><div class="pr-grid" id="prG"></div></div>`;
      const grid = $("#prG", body), status = $("#prS", body), lv = $("#prLv", body);
      api.pills.innerHTML = `<span class="pill" id="prC">x1</span><span class="pill yellow" id="prP">0</span>`;
      const say = (t) => { status.textContent = t; status.classList.remove("flash"); void status.offsetWidth; status.classList.add("flash"); };
      let level = 1, pts = 0, streak = 0, perfect = 0, rounds = 0, maxLevel = 1, over = false, resolveTurn = null;
      const setPts = (v) => { pts = v; $("#prP").textContent = v.toLocaleString("en-IN"); };
      const mult = () => Math.min(5, 1 + Math.floor(streak / 2));
      const tilesFor = (l) => Math.min(14, l + 2);
      const decoysFor = (l) => (l >= 5 ? Math.min(4, Math.floor((l - 3) / 2)) : 0);
      const flashFor = (l, t) => Math.max(650, (l >= 8 ? 1000 : 1300) + t * 70 - l * 40);

      let timer;
      function end() { over = true; if (resolveTurn) resolveTurn(null); }

      async function play() {
        await BL.countdown(body);
        if (!api.alive()) return;
        timer = BL.timer(api, DURATION, { el: $("#prT", body), onEnd: end });
        while (!over && api.alive()) {
          rounds++;
          const tiles = tilesFor(level), decoys = decoysFor(level);
          const n = gridFor(tiles + decoys);
          lv.innerHTML = `<i>Level ${level}</i><span>${tiles} tiles</span>${decoys ? `<i class="decoy">+${decoys} decoys</i>` : ""}`;
          grid.classList.add("out"); await wait(grid.children.length ? 250 : 0);
          if (over || !api.alive()) break;
          grid.innerHTML = "";
          grid.style.gridTemplateColumns = `repeat(${n},1fr)`;
          grid.style.gap = n > 4 ? "8px" : "10px";
          const cells = [];
          for (let i = 0; i < n * n; i++) { const c = h(`<div class="pr-tile" style="animation-delay:${i * 14}ms"><div class="f"></div><div class="b"></div></div>`); grid.appendChild(c); cells.push(c); }
          grid.classList.remove("out");
          const order = rng.shuffle([...Array(n * n).keys()]);
          const target = new Set(order.slice(0, tiles));
          const decoySet = new Set(order.slice(tiles, tiles + decoys));
          say(decoys ? "Watch the YELLOW ones only" : "Watch…");
          await wait(450 + n * n * 14);
          if (over || !api.alive()) break;
          target.forEach((i) => cells[i].classList.add("flip"));
          decoySet.forEach((i) => cells[i].classList.add("flip", "decoy"));
          sfx.tone(880, { type: "triangle", dur: 0.22, vol: 0.12 }); sfx.tone(1320, { type: "sine", dur: 0.25, vol: 0.05, delay: 0.05 });
          await wait(flashFor(level, tiles));
          if (over || !api.alive()) break;
          cells.forEach((c) => c.classList.remove("flip"));
          await wait(380);
          cells.forEach((c) => c.classList.remove("decoy"));
          if (over || !api.alive()) break;
          say(`Your turn · find ${tiles}`);
          const result = await new Promise((resolve) => {
            resolveTurn = resolve;
            let found = 0, done = false;
            cells.forEach((c, i) => (c.onpointerdown = (ev) => {
              if (done || over || c.classList.contains("flip")) return;
              haptic(8);
              if (target.has(i)) {
                found++; c.classList.add("flip", "ok");
                sfx.tone(523.25 * Math.pow(2, (found - 1) / 7), { type: "triangle", dur: 0.16, vol: 0.15 });
                const gain = 10 * mult(); setPts(pts + gain);
                if (found === tiles) { done = true; resolve(true); }
              } else {
                done = true; c.classList.add("flip", "bad"); grid.classList.add("shake"); sfx.bad(); haptic([30, 40, 30]);
                setTimeout(() => grid.classList.remove("shake"), 460);
                target.forEach((j) => { if (!cells[j].classList.contains("flip")) cells[j].classList.add("flip", "miss"); });
                if (decoySet.has(i)) BL.toast("That was a decoy 💜");
                resolve(false);
              }
            }));
          });
          resolveTurn = null;
          if (result === null || !api.alive()) break;
          if (result) {
            perfect++; streak++;
            const bonus = tiles * 10 * mult();
            setPts(pts + bonus); timer.add(level < 8 ? 2 : 1);
            $("#prC").textContent = "x" + mult();
            target.forEach((i) => setTimeout(() => cells[i].classList.add("hop"), [...target].indexOf(i) * 40));
            sfx.good();
            BL.combo(body, streak >= 3 ? `+${bonus} · ${streak} in a row 🔥` : `Perfect! +${bonus}`);
            level++; maxLevel = Math.max(maxLevel, level);
            if (level === 5) { await wait(500); BL.levelBanner(body, "LEVEL 5", "Decoys unlocked 💜"); await wait(900); }
            if (level === 8) { await wait(500); BL.levelBanner(body, "LEVEL 8", "Faster flashes ⚡"); await wait(900); }
            await wait(700);
          } else {
            streak = 0; $("#prC").textContent = "x1";
            timer.add(-3);
            say("−3s · here’s where they were");
            level = Math.max(1, level - 1);
            await wait(1200);
          }
        }
        if (!api.alive()) return;
        say("Time!");
        await wait(500);
        api.finish({
          score: pts, level: maxLevel,
          title: maxLevel >= 8 ? "Photographic memory 📸" : maxLevel >= 5 ? "Pattern pro" : "Good sprint",
          sub: `Reached level ${maxLevel}${maxLevel >= 5 ? " and beat the decoys" : ""}`,
          big: pts.toLocaleString("en-IN"),
          stats: [["top level", maxLevel], ["perfect", `${perfect}/${rounds}`], ["best tiles", tilesFor(maxLevel - 1 || 1)]],
          meta: { rounds, perfect },
        });
      }
      play();
      return () => {};
    },
  });
})();
