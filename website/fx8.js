/* Waky FX v8: live-dithered statue (from the reference bitmap), scroll story, live feature tiles. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var reduce = matchMedia("(prefers-reduced-motion: reduce)").matches || /[?&]still/.test(location.search), fine = matchMedia("(pointer: fine)").matches;
  var cfg = window.WAKY || {};
  var clamp = function (v, a, b) { return v < a ? a : v > b ? b : v; };
  var hash = function (a, b) { var s = Math.sin(a * 127.1 + b * 311.7) * 43758.5453; return s - Math.floor(s); };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var esc = function (s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); };
  var ptr = { x: innerWidth * .7, y: innerHeight * .35, moved: 0 };
  var GL = "01#%&*+=?/<>[]{}";

  $$(".js-download").forEach(function (a) { if (cfg.downloadUrl) { a.href = cfg.downloadUrl; a.setAttribute("download", ""); } });
  $$(".js-repo").forEach(function (a) { if (cfg.repoUrl) a.href = cfg.repoUrl; });
  $$(".js-size").forEach(function (a) { if (cfg.size) a.textContent = cfg.size; });
  addEventListener("pointermove", function (e) { ptr.x = e.clientX; ptr.y = e.clientY; ptr.moved = performance.now(); }, { passive: true });

  /* progress bar + reveal */
  var bar = $("#sprog");
  function onScroll() { var h = document.documentElement; if (bar) bar.style.transform = "scaleX(" + (scrollY / Math.max(1, h.scrollHeight - innerHeight)).toFixed(4) + ")"; }
  addEventListener("scroll", onScroll, { passive: true }); onScroll();
  var io = "IntersectionObserver" in window ? new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); e.target.dispatchEvent(new CustomEvent("revealed")); } }); }, { threshold: .12, rootMargin: "0px 0px -40px 0px" }) : null;
  $$(".pxr").forEach(function (el) { if (io) io.observe(el); else el.classList.add("in"); });

  function scramble(el, dur) {
    if (reduce) return; var t = el.getAttribute("data-t") || el.textContent; el.setAttribute("data-t", t); dur = dur || 650; var t0 = performance.now();
    (function f(n) { var p = clamp((n - t0) / dur, 0, 1), o = ""; for (var i = 0; i < t.length; i++) o += t[i] === " " || i < p * t.length ? t[i] : GL[(Math.random() * GL.length) | 0]; el.textContent = o; if (p < 1) requestAnimationFrame(f); else el.textContent = t; })(t0);
  }
  $$("[data-scramble]").forEach(function (el) { el.addEventListener("pointerenter", function () { scramble(el, 450); }); });
  $$(".sc-in").forEach(function (el) { el.addEventListener("revealed", function () { scramble(el); }); });
  setTimeout(function () { $$("[data-scramble-load]").forEach(function (el) { scramble(el, 900); }); }, 500);
  if (fine && !reduce) $$(".btn").forEach(function (b) {
    b.addEventListener("pointermove", function (e) { var r = b.getBoundingClientRect(); b.style.translate = ((e.clientX - r.left - r.width / 2) * .16).toFixed(1) + "px " + ((e.clientY - r.top - r.height / 2) * .24).toFixed(1) + "px"; });
    b.addEventListener("pointerleave", function () { b.style.translate = "0 0"; });
  });

  function typeTo(el, text, speed, tok) { return new Promise(function (res) { var i = 0; (function f() { if (tok && tok.dead) return res(); i = Math.min(text.length, i + 1); el.textContent = text.slice(0, i); if (i < text.length) setTimeout(f, speed); else res(); })(); }); }
  function watch(el) { var on = false; if ("IntersectionObserver" in window) new IntersectionObserver(function (es) { on = es[0].isIntersecting; }, { threshold: .2 }).observe(el); else on = true; return function () { return on; }; }

  /* =====================================================================
     STATUE: the reference bitmap, re-dithered live. Cursor lights it, click sends a shockwave,
     scanline glitch rows tear across it, it scans in from the top on load.
     ===================================================================== */
  (function statue() {
    var cv = $("#statue"); if (!cv) return;
    var c = cv.getContext("2d"), S = 6, n = 0, bx, by, bw, ox, oy, vx, vy, dl, vis = true, lastF = 0, t0 = performance.now(), shock = { t: -9, x: 0, y: 0 }, cw0 = 1, ch0 = 1, last = 0;
    var src = new Image();
    src.onload = function () {
      var cr = (cv.getAttribute("data-crop") || "0,1,0,1").split(",").map(Number), iw = src.naturalWidth, ih = src.naturalHeight, x0 = iw * cr[0], x1 = iw * cr[1], y0 = ih * cr[2], y1 = ih * cr[3], cw = x1 - x0, ch = y1 - y0, light = cv.getAttribute("data-mode") === "light";
      var cols = +(cv.getAttribute("data-cols") || 200), rows = Math.round(cols * ch / cw);
      var oc = document.createElement("canvas"); oc.width = cols; oc.height = rows; var g = oc.getContext("2d", { willReadFrequently: true }); g.imageSmoothingQuality = "high"; g.drawImage(src, x0, y0, cw, ch, 0, 0, cols, rows);
      var d = g.getImageData(0, 0, cols, rows).data, tmp = [];
      for (var k = 0; k < cols * rows; k++) { var l = d[k * 4] / 255, v = clamp(((light ? l : 1 - l) - .06) * 1.25, 0, 1); if (v > .1) tmp.push(k, v); }
      n = tmp.length / 2; bx = new Float32Array(n); by = new Float32Array(n); bw = new Float32Array(n); ox = new Float32Array(n); oy = new Float32Array(n); vx = new Float32Array(n); vy = new Float32Array(n); dl = new Float32Array(n);
      for (var q = 0; q < n; q++) { var kk = tmp[q * 2], v2 = tmp[q * 2 + 1], cx = kk % cols, cy = (kk / cols) | 0; bx[q] = cx * S + S / 2; by[q] = cy * S + S / 2; bw[q] = S * (.4 + .6 * Math.sqrt(v2)); ox[q] = reduce ? 0 : (Math.random() - .5) * 700; oy[q] = reduce ? 0 : -300 - Math.random() * 500; dl[q] = reduce ? 0 : (cy / rows) * 900 + Math.random() * 700; }
      cv.width = cw0 = cols * S; cv.height = ch0 = rows * S; cv.style.setProperty("aspect-ratio", cols + " / " + rows, "important");
      t0 = performance.now(); if (reduce) frame(t0 + 5000); else requestAnimationFrame(frame);
    };
    src.src = cv.getAttribute("data-src") || "assets/statue-stipple.webp";
    function frame(now) {
      if (now - lastF < 28 && !reduce) { if (vis) requestAnimationFrame(frame); return; } lastF = now;
      var t = (now - t0), r = cv.getBoundingClientRect(), k = cw0 / Math.max(1, r.width), mx = (ptr.x - r.left) * k, my = (ptr.y - r.top) * k, near = now - ptr.moved < 4000 && mx > -200 && mx < cw0 + 200 && my > -200 && my < ch0 + 200;
      var R = cw0 * .09, R2 = R * R, wave = ((t / 1000) * .16) % 1.6, sa = (now - t0) / 1000 - shock.t;
      c.clearRect(0, 0, cw0, ch0); c.fillStyle = "#f2f2f2";
      for (var i = 0; i < n; i++) {
        if (t < dl[i]) continue;
        var fx = -ox[i] * .06, fy = -oy[i] * .06, px = bx[i] + ox[i], py = by[i] + oy[i];
        if (near) { var dx = px - mx, dy = py - my, d2 = dx * dx + dy * dy; if (d2 < R2 && d2 > .01) { var d = Math.sqrt(d2), f = (1 - d / R); f *= f * 7; fx += dx / d * f + (-dy / d) * f * .35; fy += dy / d * f + (dx / d) * f * .35; } }
        if (sa > 0 && sa < 1.6) { var sdx = px - shock.x, sdy = py - shock.y, sd = Math.sqrt(sdx * sdx + sdy * sdy), ring = sd - sa * cw0 * .8; if (ring > -40 && ring < 40 && sd > 1) { var sf = (1 - Math.abs(ring) / 40) * 9 * (1 - sa / 1.6); fx += sdx / sd * sf; fy += sdy / sd * sf; } }
        vx[i] = (vx[i] + fx) * .84; vy[i] = (vy[i] + fy) * .84; ox[i] += vx[i]; oy[i] += vy[i];
        var w = bw[i], yy = by[i] / ch0 * 1.6 - wave; if (yy > -.02 && yy < .02) w *= 1.22;
        c.fillRect(px - w / 2, py - w / 2, w, w);
      }
      if (vis && !reduce) requestAnimationFrame(frame);
    }
    document.addEventListener("pointerdown", function (e) { if (scrollY > innerHeight * .9 || e.target.closest("a,button")) return; var r = cv.getBoundingClientRect(), k = cw0 / Math.max(1, r.width); shock = { t: (performance.now() - t0) / 1000, x: (e.clientX - r.left) * k, y: (e.clientY - r.top) * k }; });
    if ("IntersectionObserver" in window) new IntersectionObserver(function (es) { var v = es[0].isIntersecting; if (v && !vis) { vis = true; if (!reduce) requestAnimationFrame(frame); } else if (!v) vis = false; }).observe(cv);
  })();

  /* =====================================================================
     LEOPARD: the galloping animal from the reference GIF (23 frames), re-rendered as pixel dots. Background only.
     ===================================================================== */
  (function leopard() {
    var cv = $("#leo"); if (!cv) return;
    var FR = 23, FW = 260, FH = 103, COLS = 6, S = 5, c = cv.getContext("2d"), frames = [], vis = true, last = 0, t0 = performance.now(), cur = -1;
    cv.width = FW * S; cv.height = FH * S;
    var img = new Image();
    img.onload = function () {
      var oc = document.createElement("canvas"); oc.width = img.naturalWidth; oc.height = img.naturalHeight; var g = oc.getContext("2d", { willReadFrequently: true }); g.drawImage(img, 0, 0);
      for (var k = 0; k < FR; k++) { var d = g.getImageData((k % COLS) * FW, ((k / COLS) | 0) * FH, FW, FH).data, a = new Float32Array(FW * FH); for (var p = 0; p < a.length; p++) a[p] = d[p * 4] / 255; frames.push(a); }
      if (reduce) draw(0); else requestAnimationFrame(frame);
    };
    img.src = "assets/leo-sheet.png";
    function draw(k) {
      if (k === cur) return; cur = k; var a = frames[k]; c.clearRect(0, 0, cv.width, cv.height); c.fillStyle = "#f2f2f2"; c.beginPath();
      for (var y = 0; y < FH; y++) for (var x = 0; x < FW; x++) { var v = a[y * FW + x]; if (v < .08) continue; var r = S * .5 * Math.sqrt(Math.min(1, v * 2.2)); c.moveTo(x * S + S / 2 + r, y * S + S / 2); c.arc(x * S + S / 2, y * S + S / 2, r, 0, 6.2832); }
      c.fill();
    }
    function frame(now) { if (frames.length) draw(Math.floor((now - t0) / 40) % FR); if (vis && !reduce) requestAnimationFrame(frame); }
    if ("IntersectionObserver" in window) new IntersectionObserver(function (es) { var v = es[0].isIntersecting; if (v && !vis) { vis = true; if (!reduce) requestAnimationFrame(frame); } else if (!v) vis = false; }).observe(cv);
  })();

  /* =====================================================================
     TRY IT: real keycaps + the Waky pill
     ===================================================================== */
  (function demo() {
    var root = $("#demo"); if (!root) return;
    var S = {
      email: { raw: "{um} tell Maya I’ll send the deck {uh} tomorrow morning", out: "Hi Maya,\n\nI’ll send the deck over tomorrow morning.\n\nBest, Nayan", app: "Email" },
      notes: { raw: "{okay so} bullet points update the page {uh} ask Maya for copy share the preview", out: "• Update the page\n• Ask Maya for the final copy\n• Share the preview", app: "Notes" },
      hinglish: { raw: "kal tak bhej dunga {um} bas final feedback chahiye", out: "I’ll send it by tomorrow. I just need the final feedback.", app: "Chat" }
    };
    var key = "email", run = 0, state = "idle", words = [], timers = [], interacted = false, vis = false;
    var said = $("#dSaid"), out = $("#dOut"), st = $("#dState"), app = $("#dApp"), k1 = $("#dK1"), k2 = $("#dK2"), pill = $("#dPill"), pl = $("#dPL");
    function later(f, ms) { timers.push(setTimeout(f, ms)); } function clr() { timers.forEach(clearTimeout); timers = []; run++; }
    function setState(s) { state = s; root.setAttribute("data-s", s); pill.setAttribute("data-s", s); st.textContent = { idle: "Ready", listen: "Listening", clean: "Cleaning up", write: "Writing", done: "Pasted" }[s]; pl.textContent = { idle: "Hold to talk", listen: "Listening", clean: "Cleaning up", write: "Writing…", done: "Pasted" }[s]; }
    function keys(on) { k1.classList.toggle("dn", on); setTimeout(function () { k2.classList.toggle("dn", on); }, on ? 80 : 0); }
    function load(k) {
      clr(); key = k; var sc = S[k]; words = []; said.innerHTML = ""; out.innerHTML = '<span class="ghost">Your words appear here.</span>'; app.textContent = sc.app; keys(false); root.classList.remove("cleaning");
      sc.raw.split(/(\{[^}]+\})/).filter(Boolean).forEach(function (p) { var mm = p.match(/^\{(.+)\}$/); (mm ? mm[1] : p).split(/\s+/).filter(Boolean).forEach(function (w) { var sp = document.createElement("span"); sp.className = "w" + (mm ? " f" : ""); sp.textContent = w; said.appendChild(sp); said.appendChild(document.createTextNode(" ")); words.push(sp); }); });
      setState("idle");
    }
    function start() { if (state !== "idle" && state !== "done") return; interacted = true; load(key); setState("listen"); keys(true); var my = run, i = 0; (function tick() { if (my !== run || state !== "listen") return; if (i < words.length) { words[i++].classList.add("on"); later(tick, 170 + Math.random() * 80); } else later(tick, 120); })(); }
    function end() {
      if (state !== "listen") return; keys(false); var my = run, rest = words.filter(function (w) { return !w.classList.contains("on"); });
      rest.forEach(function (w, i) { later(function () { w.classList.add("on"); }, i * 40); });
      later(function () { if (my !== run) return; setState("clean"); root.classList.add("cleaning"); later(function () { if (my !== run) return; root.classList.remove("cleaning"); setState("write"); var o = S[key].out, i = 0; (function ty() { if (my !== run) return; i = Math.min(o.length, i + 2); out.innerHTML = esc(o.slice(0, i)) + (i < o.length ? '<span class="caret"></span>' : ""); if (i < o.length) later(ty, 18); else setState("done"); })(); }, 1100); }, rest.length * 40 + 300);
    }
    [k1, k2].forEach(function (k) { k.addEventListener("pointerdown", function (e) { e.preventDefault(); try { k.setPointerCapture(e.pointerId); } catch (x) {} start(); }); ["pointerup", "pointercancel"].forEach(function (ev) { k.addEventListener(ev, end); }); });
    addEventListener("keydown", function (e) { if (e.code === "Space" && !e.repeat && vis && !/INPUT|TEXTAREA|BUTTON|A/.test(document.activeElement.tagName)) { e.preventDefault(); start(); } });
    addEventListener("keyup", function (e) { if (e.code === "Space") end(); });
    $$("#dTabs button").forEach(function (b) { b.addEventListener("click", function () { $$("#dTabs button").forEach(function (x) { x.classList.toggle("on", x === b); }); interacted = true; load(b.getAttribute("data-k")); }); });
    if ("IntersectionObserver" in window) new IntersectionObserver(function (es) { var v = es[0].isIntersecting; vis = v; if (v && !interacted && !reduce && !root.__a) { root.__a = 1; setTimeout(function () { if (!interacted) { start(); setTimeout(function () { if (state === "listen") end(); }, 2600); } }, 900); } }, { threshold: .45 }).observe(root);
    load("email");
  })();

  /* =====================================================================
     HOW IT WORKS: scroll-driven story, one sentence travels through Waky
     ===================================================================== */
  (function story() {
    var sec = $("#how"); if (!sec) return;
    var RAW = "um tell maya i’ll send the deck uh tomorrow morning", OUT = "Hi Maya,\n\nI’ll send the deck over tomorrow morning.\n\nBest, Nayan";
    var ST = [
      { t: "Hold the key", d: "Click into any text field and hold Ctrl + Win. A small black pill shows Waky is listening. You never open a window.", tag: "01 · LISTEN" },
      { t: "Say it your way", d: "Ramble, pause, say um. Switch between Hindi and English mid-sentence. Speech becomes text through Groq with your key, or Whisper on your PC.", tag: "02 · TRANSCRIBE" },
      { t: "Clean it. Shape it.", d: "Fillers go, punctuation is fixed, your vocabulary repairs misheard words. Say a mode (write email) and the sentence becomes a draft.", tag: "03 · CLEAN + SHAPE" },
      { t: "Let go. It’s written.", d: "The text is pasted where your cursor is. Waky never presses Enter, so you read it before you send it.", tag: "04 · PASTE" }
    ];
    var T = $("#flT"), D = $("#flD"), tag = $("#flTag"), body = $("#flBody"), pillE = $("#flPill"), pl = $("#flPL"), dots = $$("#flDots li"), win = $("#flWin"), fill = $("#flFill"), chip = $("#flChip"), last = -1;
    function morph(a, b, q) { var L = Math.max(a.length, b.length), o = "", k = q * L; for (var i = 0; i < L; i++) { if (i < k) o += b[i] || ""; else { var ch = a[i] || ""; o += ch && Math.random() < .5 ? GL[(Math.random() * GL.length) | 0] : ch; } } return o; }
    function update() {
      var r = sec.getBoundingClientRect(), total = sec.offsetHeight - innerHeight, p = clamp(-r.top / Math.max(1, total), 0, .9999), idx = Math.floor(p * 4), q = p * 4 - idx;
      fill.style.transform = "scaleY(" + p.toFixed(3) + ")";
      if (idx !== last) { last = idx; T.textContent = ST[idx].t; D.textContent = ST[idx].d; tag.textContent = ST[idx].tag; dots.forEach(function (d, i) { d.classList.toggle("on", i <= idx); d.classList.toggle("cur", i === idx); }); win.setAttribute("data-st", idx); pillE.setAttribute("data-s", ["listen", "listen", "work", "done"][idx]); pl.textContent = ["Listening", "Listening", "Writing…", "Pasted"][idx]; chip.classList.toggle("show", idx >= 2); T.classList.remove("swap"); void T.offsetWidth; T.classList.add("swap"); }
      var txt;
      if (idx === 0) txt = ""; else if (idx === 1) txt = RAW.slice(0, Math.ceil(q * RAW.length)); else if (idx === 2) txt = morph(RAW, OUT, q); else txt = OUT;
      body.innerHTML = esc(txt) + (idx < 3 ? '<span class="caret"></span>' : "");
      body.classList.toggle("raw", idx === 1 || (idx === 2 && q < .5));
    }
    addEventListener("scroll", update, { passive: true }); addEventListener("resize", update); update();
  })();

  /* =====================================================================
     FEATURE TILES: each one is a small live demo
     ===================================================================== */
  (function tiles() {
    var clean = $("#tClean");
    if (clean) {
      var on = watch(clean), ph = 0, FR = "um so tell Maya I’ll uh send the deck like tomorrow";
      clean.innerHTML = FR.replace(/\b(um|so|uh|like)\b/g, '<span class="f">$1</span>');
      setInterval(function () { if (!on()) return; ph = (ph + 1) % 4; clean.setAttribute("data-p", ph); $("#tCleanOut").classList.toggle("show", ph >= 2); }, 1500);
    }
    var mo = $("#tMout");
    if (mo) {
      var M = [["write email", "Hi Maya,\nI’ll send the deck tomorrow.\nBest, Nayan"], ["bullet points", "• Update the page\n• Ask for copy\n• Share the preview"], ["prompt mode", "Role: Designer\nTask: Launch brief\nFormat: Short"], ["make it shorter", "Let’s push the launch."]], mi = -1, mon = watch(mo), chips = $$("#tChips span"), tok = { dead: false };
      var setM = function (i) { mi = i; tok.dead = true; tok = { dead: false }; chips.forEach(function (c, k) { c.classList.toggle("on", k === i); }); typeTo(mo, M[i][1], 14, tok); };
      chips.forEach(function (c, i) { c.addEventListener("click", function () { setM(i); }); c.addEventListener("pointerenter", function () { setM(i); }); });
      setM(0); setInterval(function () { if (mon()) setM((mi + 1) % M.length); }, 3600);
    }
    function loopPair(a, b, pairs, gap) { var on = watch(a); (async function () { var n = 0; while (true) { while (!on()) await sleep(300); var p = pairs[n++ % pairs.length]; a.textContent = ""; b.textContent = ""; b.classList.remove("show"); await typeTo(a, p[0], 55); await sleep(350); b.classList.add("show"); await typeTo(b, p[1], 26); await sleep(gap || 2200); } })(); }
    var hf = $("#tHiF"), hto = $("#tHiT"); if (hf) loopPair(hf, hto, [["kal tak bhej dunga", "I’ll send it by tomorrow."], ["thoda time chahiye", "I need a little more time."], ["meeting shuru karte hain", "Let’s start the meeting."]]);
    var sn = $("#tSnIn"), so = $("#tSnOut"); if (sn) loopPair(sn, so, [["my email", "your.email@example.com"], ["my portfolio", "your-portfolio.example.com"], ["my phone number", "+91-0000000000"]]);
    var pc = $$("#tProf button"), po = $("#tProfOut");
    if (pc.length) { var PT = { Chat: "can you send the deck tomorrow?", Email: "Could you please send the deck by tomorrow morning? Thank you.", Code: "send the deck tomorrow" }, ptok = { dead: false }, pi = 0, pon = watch(po);
      var setP = function (k) { pc.forEach(function (b) { b.classList.toggle("on", b.textContent === k); }); ptok.dead = true; ptok = { dead: false }; typeTo(po, PT[k], 16, ptok); };
      pc.forEach(function (b) { b.addEventListener("click", function () { setP(b.textContent); }); }); setP("Chat"); setInterval(function () { if (pon()) { pi = (pi + 1) % 3; setP(["Chat", "Email", "Code"][pi]); } }, 4200); }
    var rw = $("#tRw"); if (rw) { var rp = 0, ron = watch(rw), R1 = "I think we maybe should push the launch back a little"; rw.innerHTML = esc(R1); setInterval(function () { if (!ron()) return; rp = (rp + 1) % 3; if (rp === 0) rw.innerHTML = esc(R1); if (rp === 1) rw.innerHTML = "<mark>" + esc(R1) + "</mark>"; if (rp === 2) rw.innerHTML = '<mark class="done">Let’s push the launch.</mark>'; }, 1700); }
    var heat = $("#tHeat"); if (heat) { var h = ""; for (var i = 0; i < 70; i++) h += '<i style="--l:' + ((hash(i, 3) * 5) | 0) + ";--d:" + (hash(i, 9) * 3).toFixed(2) + 's"></i>'; heat.innerHTML = h; }
    var f9 = $("#tF9"), bars = $("#tBars"); if (f9) f9.addEventListener("click", function () { f9.classList.toggle("dn"); bars.classList.toggle("on", f9.classList.contains("dn")); $("#tF9T").textContent = f9.classList.contains("dn") ? "Listening hands-free" : "Tap to start, tap to stop"; });
    var rt = $("#tRoute"); if (rt) $$("button", rt).forEach(function (b) { b.addEventListener("click", function () { $$("button", rt).forEach(function (x) { x.classList.toggle("on", x === b); }); $("#tRouteT").textContent = b.textContent === "Cloud" ? "Groq with your own key. Nothing is stored." : "Whisper on your PC. Speech never leaves it."; }); });
  })();

  /* decorative dithered type + band */
  if (window.BitmapField) {
    var led = $("#led"); if (led) { var go = function () { new BitmapField(led, { mode: "text", text: "$0", px: 6, host: led, radius: .16 }); }; if (document.fonts && document.fonts.load) document.fonts.load("700 100px Inter").then(go); else go(); }
    var band = $("#band2"); if (band) new BitmapField(band, { mode: "band", px: 4, host: band.parentNode });
  }
})();
