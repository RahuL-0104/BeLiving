/* Mandala Rush
   Challenge (Daily / Practice · 60s): a random, named sketch appears with a coloured
   reference. Pick a colour, tap a ring, match the reference. Finish a sketch → bonus +
   a brand-new sketch. From sketch 3 the reference hides (memory mode, peek costs 3s).
   Calm: untimed free colouring of a random named sketch, saved automatically. */
(function () {
  const { h, $, sfx, haptic, LS } = BL;
  const TAU = Math.PI * 2;
  const DURATION = 60;
  const P = (r, a) => [+(r * Math.sin(a)).toFixed(2), +(-r * Math.cos(a)).toFixed(2)];

  /* ---------- sketch generator ---------- */
  const FAMILIES = {
    Lotus: { w: { petals: 5, kites: 1, dots: 1, sectors: 1 }, nouns: ["Lotus", "Bloom", "Kamal"] },
    Rangoli: { w: { dots: 3, kites: 3, petals: 2, sectors: 1 }, nouns: ["Rangoli", "Kolam", "Diya"] },
    Sun: { w: { kites: 4, sectors: 2, petals: 1, dots: 1 }, nouns: ["Sun", "Surya", "Sunrise"] },
    Chakra: { w: { sectors: 4, dots: 2, kites: 1, petals: 1 }, nouns: ["Chakra", "Wheel", "Compass"] },
    Star: { w: { kites: 3, petals: 2, sectors: 1, dots: 1 }, nouns: ["Star", "Tara", "Spark"] },
    Peacock: { w: { petals: 4, dots: 2, sectors: 1, kites: 1 }, nouns: ["Peacock", "Mor", "Feather"] },
  };
  const ADJ = ["Golden", "Monsoon", "Midnight", "Saffron", "Jasmine", "Coral", "Mystic", "Silent", "Royal", "Mango", "Lunar", "Velvet", "Temple", "Ocean", "Holi", "Marigold", "Cosmic", "Zen"];
  const THEMES = {
    Sunset: ["#FFC83D", "#FF8A5B", "#FF5C8A", "#C84B9E", "#6A4C93", "#FFE3A3"],
    Ocean: ["#0FA3B1", "#7ED9C3", "#2D6CDF", "#B5E2FA", "#F7A072", "#1E2235"],
    Peacock: ["#0B6E4F", "#2A9D8F", "#264653", "#E9C46A", "#6A4C93", "#8EC5FF"],
    Holi: ["#FF3E7F", "#FFC83D", "#33C1FF", "#7AE582", "#B983FF", "#FF8A00"],
    Mehendi: ["#8B5E34", "#D4A373", "#E9EDC9", "#CCD5AE", "#BC6C25", "#606C38"],
    Candy: ["#FFB4A2", "#FF8FAB", "#C9A7FF", "#8EC5FF", "#B8E986", "#FFE5A3"],
  };
  const FREE = ["#FFC83D", "#FFB4A2", "#FF8FAB", "#C9A7FF", "#8EC5FF", "#7ED9C3", "#B8E986", "#FFE5A3", "#F4A259", "#5B6CFF", "#2D3047", "#FFFFFF"];

  function weighted(rng, w) { const t = Object.values(w).reduce((a, b) => a + b, 0); let x = rng() * t; for (const [k, v] of Object.entries(w)) { if ((x -= v) < 0) return k; } return Object.keys(w)[0]; }

  function makeSketch(rng, difficulty = 1) {
    const fam = rng.pick(Object.keys(FAMILIES));
    const F = FAMILIES[fam];
    const name = `${rng.pick(ADJ)} ${rng.pick(F.nouns)}`;
    const theme = rng.pick(Object.keys(THEMES));
    const layers = [];
    let r = 196;
    layers.push({ t: "circle", r });
    const bands = Math.min(6, 3 + Math.floor(difficulty / 2) + rng.int(2));
    const bw = (196 - 30) / bands;
    for (let b = 0; b < bands; b++) {
      const inner = Math.max(26, r - bw * (0.85 + rng() * 0.3));
      const type = weighted(rng, F.w);
      const n = rng.pick(inner > 120 ? [12, 16, 16, 20, 24] : inner > 60 ? [8, 10, 12, 12] : [6, 8, 8]);
      if (type === "petals") {
        layers.push({ t: "petals", n, a: inner, b: r - 2, w: 1.6 / n * (1.1 + rng() * 0.6) * (n / 8) ** 0.2 });
        if (rng() < 0.55) layers.push({ t: "petals", n, a: inner, b: r - (r - inner) * 0.28, w: 1.1 / n * (n / 8) ** 0.2, off: 0.5 });
      } else if (type === "kites") {
        layers.push({ t: "kites", n, a: inner, b: r - 2, w: 0.9 / n * TAU / 2.6 });
        if (rng() < 0.5) layers.push({ t: "kites", n, a: inner + (r - inner) * 0.15, b: r - (r - inner) * 0.35, w: 0.55 / n * TAU / 2.6, off: 0.5 });
      } else if (type === "sectors") {
        const mid = inner + (r - inner) * (0.45 + rng() * 0.2);
        layers.push({ t: "sectors", n, a: mid, b: r - 3, gap: 0.035 });
        layers.push({ t: "circle", r: mid - 3 });
        if (rng() < 0.6) layers.push({ t: "dots", n, r: (mid + inner) / 2, s: Math.min(9, (mid - inner) / 3), off: 0.5 });
      } else {
        const s = Math.min(11, (r - inner) / 3.2);
        layers.push({ t: "dots", n: Math.min(32, Math.round((TAU * (r - s - 4)) / (s * 3.2))), r: r - s - 4, s });
        if (r - inner > 30) layers.push({ t: "petals", n: rng.pick([8, 12]), a: inner, b: r - s * 2 - 8, w: 0.18, off: 0.5 });
      }
      layers.push({ t: "circle", r: inner });
      r = inner;
    }
    layers.push({ t: "petals", n: rng.pick([5, 6, 8]), a: 4, b: r - 3, w: 0.5 });
    layers.push({ t: "circle", r: Math.max(5, r * 0.25) });

    // target colours: neighbours never share a colour
    const pal = THEMES[theme];
    let prev = null;
    const target = layers.map(() => { let c; do { c = rng.pick(pal); } while (c === prev); prev = c; return c; });
    return { name, family: fam, theme, layers, target };
  }

  function shapes(layer) {
    const out = [];
    const n = layer.n || 1, off = (layer.off || 0) * (TAU / n);
    for (let i = 0; i < n; i++) {
      const th = off + (i * TAU) / n;
      if (layer.t === "circle") out.push(`<circle r="${layer.r}"/>`);
      else if (layer.t === "dots") { const [x, y] = P(layer.r, th); out.push(`<circle cx="${x}" cy="${y}" r="${layer.s.toFixed(2)}"/>`); }
      else if (layer.t === "petals") {
        const { a, b, w } = layer, d = b - a;
        const base = P(a, th), tip = P(b, th);
        out.push(`<path d="M${base}C${P(a + d * 0.25, th - w)} ${P(a + d * 0.82, th - w * 0.55)} ${tip}C${P(a + d * 0.82, th + w * 0.55)} ${P(a + d * 0.25, th + w)} ${base}Z"/>`);
      } else if (layer.t === "kites") {
        const { a, b, w } = layer, m = a + (b - a) * 0.45;
        out.push(`<path d="M${P(a, th)}L${P(m, th - w)}L${P(b, th)}L${P(m, th + w)}Z"/>`);
      } else if (layer.t === "sectors") {
        const { a, b, gap } = layer, s0 = th - Math.PI / n + gap, s1 = th + Math.PI / n - gap;
        out.push(`<path d="M${P(a, s0)}L${P(b, s0)}A${b} ${b} 0 0 1 ${P(b, s1)}L${P(a, s1)}A${a} ${a} 0 0 0 ${P(a, s0)}Z"/>`);
      }
    }
    return out;
  }
  function svgBody(sk) {
    let html = "";
    sk.layers.forEach((layer, li) => shapes(layer).forEach((sh, i) => (html += sh.replace(/^<(\w+)/, `<$1 class="mz" data-l="${li}" data-i="${i}"`))));
    return html;
  }
  function refSvg(sk) {
    let html = "";
    sk.layers.forEach((layer, li) => shapes(layer).forEach((sh) => (html += sh.replace(/^<(\w+)/, `<$1 fill="${sk.target[li]}"`))));
    return `<svg viewBox="-200 -200 400 400"><g stroke="#1E2235" stroke-width="3">${html}</g></svg>`;
  }

  const css = `
  .mr-top{display:flex;align-items:center;gap:12px;padding:6px 20px 0}
  .mr-title{flex:1;min-width:0}
  .mr-title small{display:block;font-size:11px;letter-spacing:1.4px;font-weight:700;color:var(--muted);text-transform:uppercase}
  .mr-title b{display:block;font-size:22px;letter-spacing:-.4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .mr-title b.in{animation:mrName .6s var(--spring)}
  @keyframes mrName{from{opacity:0;transform:translateY(10px) scale(.95)}}
  .mr-ref{position:relative;width:78px;height:78px;border-radius:20px;background:#fff;border:1px solid var(--line);box-shadow:var(--shadow-sm);padding:5px;flex:0 0 auto;overflow:hidden}
  .mr-ref svg{width:100%;height:100%;transition:filter .4s,opacity .4s}
  .mr-ref.hidden svg{filter:blur(10px);opacity:.35}
  .mr-ref button{position:absolute;inset:0;font-size:11px;font-weight:700;color:var(--ink);display:none;place-items:center;letter-spacing:.3px}
  .mr-ref.hidden button{display:grid}
  .mr-ref small{position:absolute;left:0;right:0;bottom:2px;text-align:center;font-size:9px;font-weight:700;letter-spacing:1px;color:var(--muted)}
  .mr-stage{flex:1;min-height:0;display:grid;place-items:center;padding:4px 14px;position:relative}
  .mr-svg{width:100%;max-height:100%;aspect-ratio:1;touch-action:manipulation;filter:drop-shadow(0 12px 26px rgba(120,90,0,.16));transition:transform .6s var(--spring),opacity .4s}
  .mr-svg.out{transform:scale(.6) rotate(-40deg);opacity:0}
  .mr-svg.enter{animation:mrIn .7s var(--spring)}
  @keyframes mrIn{from{transform:scale(.5) rotate(60deg);opacity:0}}
  .mz{fill:#fff;stroke:#1E2235;stroke-width:1.3;stroke-linejoin:round;transition:fill .4s cubic-bezier(.22,1,.36,1);cursor:pointer}
  .mz.hint{animation:mzHint 1.2s ease-in-out infinite}
  @keyframes mzHint{50%{fill:#FFF3CC}}
  .mz.wrong{animation:mzWrong .45s}
  @keyframes mzWrong{30%{fill:#FFB3B3}}
  .mr-pal{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;padding:12px 18px 6px}
  .mr-pal button{width:42px;height:42px;border-radius:50%;transition:transform .35s var(--spring),box-shadow .3s;box-shadow:0 4px 10px -3px rgba(0,0,0,.25)}
  .mr-pal button.on{transform:scale(1.18) translateY(-3px);outline:3px solid #1E2235;outline-offset:3px}
  .mr-bottom{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:8px 16px 18px}
  .mr-bottom .btn{padding:12px 4px;font-size:13px;flex-direction:column;gap:2px}
  .mr-bottom .btn span{font-size:18px}
  .mr-prog{display:flex;justify-content:center;gap:5px;padding:4px 0 14px}
  .mr-prog i{width:8px;height:8px;border-radius:50%;background:#EFE8D3;transition:all .35s var(--spring)}
  .mr-prog i.on{background:var(--teal);transform:scale(1.2)}`;

  BL.register({
    id: "mandala",
    name: "Mandala Rush",
    tag: "A new named sketch every time. Match the colours before the clock runs out.",
    tint: "#FFF0D6",
    chips: ["Focus", "60 sec"],
    modes: [["daily", "Daily · 60s"], ["practice", "Practice"], ["calm", "Calm"]],
    icon: `<svg viewBox="0 0 48 48"><g transform="translate(24 24)">${[0, 1, 2, 3, 4, 5, 6, 7].map((i) => `<path transform="rotate(${i * 45})" d="M0 -4C-5 -9 -5 -15 0 -21C5 -15 5 -9 0 -4Z" fill="${["#FFC83D", "#FF8FAB", "#7ED9C3", "#C9A7FF"][i % 4]}" stroke="#1E2235" stroke-width="1.4"/>`).join("")}<circle r="5" fill="#FFF" stroke="#1E2235" stroke-width="1.4"/></g></svg>`,
    formatBest: (s) => `${s.toLocaleString("en-IN")} pts`,
    intro: {
      desc: "Every round is a fresh, named sketch. Match the reference colours fast. Finish one and the next appears.",
      how: ["Pick a colour, tap a ring to fill it", "Match the reference: right colours chain a combo", "From sketch 3 the reference hides. Peek costs 3 seconds"],
      science: "Colour-matching under time trains visual attention and working memory. Calm mode is pure, untimed colouring.",
      cta: "Start",
    },
    start(body, api) {
      return api.mode === "calm" ? calm(body, api) : rush(body, api);
    },
  });

  /* ================= CHALLENGE ================= */
  function rush(body, api) {
    const rng = api.rng;
    body.innerHTML = `<style>${css}</style>
      ${BL.timerBarHTML("mrT")}
      <div class="mr-top">
        <div class="mr-title"><small id="mrK">Sketch 1</small><b id="mrN">…</b></div>
        <div class="mr-ref" id="mrRef"><div id="mrRefSvg"></div><button id="mrPeek">👁 PEEK<br>−3s</button><small>MATCH</small></div>
      </div>
      <div class="mr-stage"><svg class="mr-svg" id="mrSvg" viewBox="-200 -200 400 400"></svg></div>
      <div class="mr-prog" id="mrProg"></div>
      <div class="mr-pal" id="mrPal"></div>
      <div style="height:16px"></div>`;
    api.pills.innerHTML = `<span class="pill" id="mrC">x1</span><span class="pill yellow" id="mrP">0</span>`;
    const svg = $("#mrSvg", body), pal = $("#mrPal", body), ref = $("#mrRef", body), prog = $("#mrProg", body);
    let pts = 0, combo = 0, color = null, sk = null, idx = 0, done = new Set(), correct = 0, wrong = 0, sketches = 0, live = false;
    const setPts = (v) => { pts = Math.max(0, v); $("#mrP").textContent = pts.toLocaleString("en-IN"); };
    const mult = () => Math.min(4, 1 + Math.floor(combo / 3));

    function load() {
      idx++;
      sk = makeSketch(rng, idx);
      done = new Set();
      $("#mrK", body).textContent = `Sketch ${idx} · ${sk.theme}`;
      const nm = $("#mrN", body); nm.textContent = sk.name; nm.classList.remove("in"); void nm.offsetWidth; nm.classList.add("in");
      svg.innerHTML = svgBody(sk);
      svg.classList.remove("out", "enter"); void svg.offsetWidth; svg.classList.add("enter");
      $("#mrRefSvg", body).innerHTML = refSvg(sk);
      prog.innerHTML = sk.layers.map(() => "<i></i>").join("");
      // palette = sketch colours + 2 decoys, shuffled
      const used = [...new Set(sk.target)];
      const decoys = rng.shuffle(FREE.filter((c) => !used.includes(c) && c !== "#FFFFFF")).slice(0, idx >= 2 ? 2 : 1);
      const colours = rng.shuffle([...used, ...decoys]);
      pal.innerHTML = "";
      colours.forEach((c) => {
        const b = h(`<button aria-label="${c}" style="background:${c}"></button>`);
        b.onclick = () => { color = c; sfx.tone(520 + colours.indexOf(c) * 50, { dur: 0.07, vol: 0.08 }); haptic(5); pal.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); };
        pal.appendChild(b);
      });
      color = null;
      // memory mode from sketch 3: show the reference briefly, then hide it
      ref.classList.remove("hidden");
      if (idx >= 3) {
        BL.levelBanner(body, `SKETCH ${idx} · MEMORY MODE`, "Remember the colours 👀");
        api.later(() => api.alive() && ref.classList.add("hidden"), 2600);
      } else if (idx > 1) BL.levelBanner(body, `SKETCH ${idx}`, sk.name);
    }

    $("#mrPeek", body).onclick = () => {
      if (!live) return;
      timer.add(-3); sfx.soft(); ref.classList.remove("hidden");
      api.later(() => api.alive() && ref.classList.add("hidden"), 1400);
    };

    svg.addEventListener("pointerdown", (ev) => {
      if (!live) return;
      const t = ev.target.closest(".mz");
      if (!t) return;
      const li = +t.dataset.l;
      if (done.has(li)) return;
      const group = [...svg.querySelectorAll(`.mz[data-l="${li}"]`)];
      if (!color) { BL.toast("Pick a colour first 🎨"); return; }
      const br = body.getBoundingClientRect();
      if (color === sk.target[li]) {
        done.add(li); correct++; combo++;
        const gain = 10 * mult();
        setPts(pts + gain);
        const n = group.length, start = +t.dataset.i;
        group.forEach((e) => { const d = Math.min(Math.abs(+e.dataset.i - start), n - Math.abs(+e.dataset.i - start)); e.style.transitionDelay = d * 25 + "ms"; e.style.fill = color; });
        setTimeout(() => group.forEach((e) => (e.style.transitionDelay = "")), n * 26 + 450);
        prog.children[li].classList.add("on");
        sfx.piano([523.25, 587.33, 659.25, 783.99, 880, 1046.5][combo % 6] / (combo % 12 < 6 ? 1 : 2) * 1, { dur: 1, vol: 0.15 });
        haptic(6);
        BL.floatPts(body, ev.clientX - br.left - 12, ev.clientY - br.top - 30, "+" + gain);
        if (combo % 3 === 0 && mult() > 1) { $("#mrC").textContent = "x" + mult(); BL.combo(body, `Combo x${mult()} 🔥`); }
        if (done.size === sk.layers.length) {
          sketches++;
          const bonus = 50 + idx * 10;
          setPts(pts + bonus); timer.add(5);
          BL.combo(body, `Sketch done! +${bonus} · +5s`);
          sfx.win();
          live = false;
          svg.classList.add("out");
          api.later(() => { if (api.alive()) { load(); live = true; } }, 650);
        }
      } else {
        wrong++; combo = 0; $("#mrC").textContent = "x1";
        setPts(pts - 5);
        group.forEach((e) => { e.classList.remove("wrong"); void e.getBBox(); e.classList.add("wrong"); });
        setTimeout(() => group.forEach((e) => e.classList.remove("wrong")), 460);
        BL.floatPts(body, ev.clientX - br.left - 12, ev.clientY - br.top - 30, "−5", true);
        sfx.bad(); haptic([25, 30, 25]);
      }
    });

    let timer = { add() {}, stop() {} };
    (async () => {
      load();
      await BL.countdown(body);
      if (!api.alive()) return;
      live = true;
      timer = BL.timer(api, DURATION, { el: $("#mrT", body), onEnd: end });
    })();

    function end() {
      live = false;
      const acc = correct + wrong ? Math.round((correct / (correct + wrong)) * 100) : 0;
      // partial credit for the unfinished sketch is already in points
      api.finish({
        score: pts, level: sketches,
        emoji: "🪷",
        title: sketches >= 4 ? "Colour master 🎨" : sketches >= 2 ? "Quick hands!" : "Nice colouring",
        sub: `${sketches} sketch${sketches === 1 ? "" : "es"} completed · last one was “${sk.name}”`,
        big: pts.toLocaleString("en-IN"),
        stats: [["sketches", sketches], ["accuracy", acc + "%"], ["rings", correct]],
        meta: { sketches, accuracy: acc },
      });
    }
    return () => {};
  }

  /* ================= CALM ================= */
  function calm(body, api) {
    let seed = LS.get("mandala_calm_seed", null) ?? Math.floor(Math.random() * 1e9);
    let sk, els, byLayer, undo = [];
    let color = LS.get("mandala_color", FREE[0]);
    let sym = LS.get("mandala_sym", true);
    const t0 = Date.now();

    body.innerHTML = `<style>${css}</style>
      <div class="mr-top" style="padding-top:2px">
        <div class="mr-title"><small id="mcK">Calm colouring</small><b id="mcN">…</b></div>
        <button class="icon-btn" id="mcNew" aria-label="New sketch" style="width:auto;padding:0 12px;font-weight:600;font-size:13px">🎲 New</button>
      </div>
      <div class="mr-stage"><svg class="mr-svg" id="mcSvg" viewBox="-200 -200 400 400"></svg></div>
      <div class="mr-pal" id="mcPal" style="flex-wrap:nowrap;overflow-x:auto;justify-content:flex-start;scrollbar-width:none"></div>
      <div class="mr-bottom">
        <button class="btn ghost" id="mcSym"></button>
        <button class="btn ghost" id="mcUndo"><span>↶</span>Undo</button>
        <button class="btn ghost" id="mcSave"><span>⤓</span>Save</button>
        <button class="btn" id="mcDone"><span>✓</span>Done</button>
      </div>`;
    api.pills.innerHTML = `<span class="pill" id="mcPct">0%</span>`;
    const svg = $("#mcSvg", body), pal = $("#mcPal", body);

    function key() { return "mandala_calm_" + seed; }
    function progress() {
      const n = els.filter((e) => e.style.fill && !/^(#fff(fff)?|rgb\(255, 255, 255\))$/i.test(e.style.fill)).length;
      const p = Math.round((n / els.length) * 100); $("#mcPct").textContent = p + "%"; return p;
    }
    function load(newOne) {
      if (newOne) { seed = Math.floor(Math.random() * 1e9); }
      LS.set("mandala_calm_seed", seed);
      sk = makeSketch(BL.rng(seed), 4);
      $("#mcN", body).textContent = sk.name;
      $("#mcK", body).textContent = `Calm colouring · ${sk.family}`;
      svg.innerHTML = svgBody(sk);
      svg.classList.remove("enter"); void svg.offsetWidth; svg.classList.add("enter");
      els = [...svg.querySelectorAll(".mz")];
      byLayer = {}; els.forEach((e) => (byLayer[e.dataset.l] = byLayer[e.dataset.l] || []).push(e));
      const saved = LS.get(key(), null);
      if (saved && saved.length === els.length) els.forEach((e, i) => (e.style.fill = saved[i]));
      undo = []; svg._done = false; progress();
    }
    const persist = () => LS.set(key(), els.map((e) => e.style.fill || ""));

    FREE.forEach((c) => {
      const b = h(`<button aria-label="${c}" style="flex:0 0 42px;background:${c};${c === "#FFFFFF" ? "border:1.5px solid #E5DFCD" : ""}"></button>`);
      b.dataset.c = c;
      b.onclick = () => { color = c; LS.set("mandala_color", c); sfx.tone(500 + FREE.indexOf(c) * 40, { dur: 0.08, vol: 0.08 }); haptic(5); mark(); };
      pal.appendChild(b);
    });
    const mark = () => pal.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.c === color));
    mark();
    const symBtn = $("#mcSym", body);
    const drawSym = () => { symBtn.innerHTML = `<span>${sym ? "❋" : "◦"}</span>${sym ? "Symmetry" : "Single"}`; symBtn.style.background = sym ? "var(--yellow-soft)" : ""; };
    drawSym();
    symBtn.onclick = () => { sym = !sym; LS.set("mandala_sym", sym); sfx.tap(); drawSym(); };

    let note = 0;
    svg.addEventListener("pointerdown", (ev) => {
      const t = ev.target.closest(".mz"); if (!t) return;
      const group = sym ? byLayer[t.dataset.l] : [t];
      undo.push(group.map((e) => [e, e.style.fill])); if (undo.length > 60) undo.shift();
      const n = group.length, start = +t.dataset.i;
      group.forEach((e) => { const d = Math.min(Math.abs(+e.dataset.i - start), n - Math.abs(+e.dataset.i - start)); e.style.transitionDelay = d * 28 + "ms"; e.style.fill = color; });
      setTimeout(() => group.forEach((e) => (e.style.transitionDelay = "")), n * 30 + 500);
      sfx.piano([523.25, 587.33, 659.25, 783.99, 880, 1046.5][note++ % 6] / 2, { dur: 1.4, vol: 0.14 });
      haptic(6); persist();
      if (progress() >= 100 && !svg._done) { svg._done = true; sfx.win(); BL.confetti(70); }
    });
    $("#mcUndo", body).onclick = () => { const last = undo.pop(); if (!last) return BL.toast("Nothing to undo"); last.forEach(([e, f]) => (e.style.fill = f)); sfx.soft(); persist(); progress(); };
    $("#mcNew", body).onclick = () => { sfx.whoosh(); load(true); };

    async function exportPng() {
      const clone = svg.cloneNode(true);
      clone.setAttribute("width", 1200); clone.setAttribute("height", 1200);
      clone.querySelectorAll(".mz").forEach((e, i) => { e.setAttribute("fill", els[i].style.fill || "#fff"); e.setAttribute("stroke", "#1E2235"); e.setAttribute("stroke-width", "1.3"); });
      const src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(clone));
      const img = new Image();
      await new Promise((r, j) => { img.onload = r; img.onerror = j; img.src = src; });
      const cv = document.createElement("canvas"); cv.width = 1300; cv.height = 1420;
      const g = cv.getContext("2d");
      g.fillStyle = "#FFFDF6"; g.fillRect(0, 0, 1300, 1420);
      g.fillStyle = "#1E2235"; g.font = "700 56px Outfit, sans-serif"; g.textAlign = "center"; g.fillText(sk.name, 650, 96);
      g.drawImage(img, 50, 150, 1200, 1200);
      g.fillStyle = "#C9A24A"; g.font = "600 26px Outfit, sans-serif"; g.textAlign = "right"; g.fillText("made mindfully on BeLiving", 1270, 1400);
      const a = document.createElement("a"); a.download = `beliving-${sk.name.toLowerCase().replace(/\s+/g, "-")}.png`; a.href = cv.toDataURL("image/png"); a.click();
      BL.toast("Saved to your downloads");
    }
    $("#mcSave", body).onclick = () => { sfx.tap(); exportPng().catch(() => BL.toast("Couldn’t save image")); };
    $("#mcDone", body).onclick = () => {
      const p = progress(), mins = Math.max(1, Math.round((Date.now() - t0) / 60000));
      api.finish({
        score: p, emoji: "🪷", celebrate: p >= 100, againLabel: "Keep colouring",
        title: p >= 100 ? `“${sk.name}” complete` : "Calm moment logged",
        sub: `${mins} min of mindful colouring. Your progress is saved.`,
        big: p + "%",
        stats: [["sketch", sk.family], ["shapes", els.length], ["minutes", mins]],
        extraBtn: { label: "⤓ Save as image", onClick: () => exportPng() },
        meta: { sketch: sk.name },
      });
    };
    load(false);
    return () => {};
  }
})();
