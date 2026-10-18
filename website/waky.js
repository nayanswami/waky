(function () {
  "use strict";
  var cfg = window.WAKY || {};
  var RM = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var fine = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  var hasGsap = typeof window.gsap !== "undefined";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var wait = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var clamp = function (v, a, b) { return Math.max(a, Math.min(b, v)); };
  var lerp = function (a, b, t) { return a + (b - a) * t; };
  var smooth = function (a, b, t) { var x = clamp((t - a) / (b - a), 0, 1); return x * x * (3 - 2 * x); };

  /* ---------- download buttons ---------- */
  $$(".js-version").forEach(function (el) { if (cfg.version) el.textContent = "V" + cfg.version; });
  $$(".js-size").forEach(function (el) { if (cfg.size) el.textContent = cfg.size.toUpperCase(); });
  $$(".js-repo").forEach(function (a) { if (cfg.repoUrl) a.href = cfg.repoUrl; });
  var note = $(".js-note");
  $$(".js-download").forEach(function (a) {
    if (cfg.downloadUrl) { a.href = cfg.downloadUrl; a.setAttribute("download", ""); }
    else a.addEventListener("click", function (e) { e.preventDefault(); if (note) { note.classList.add("show"); note.scrollIntoView({ block: "center" }); } });
  });

  if (!hasGsap) { // CDN blocked: show everything, skip motion
    $$(".js-hide").forEach(function (e) { e.classList.remove("js-hide"); e.style.opacity = 1; e.style.transform = "none"; });
    var l0 = $(".loader"); if (l0) l0.style.display = "none";
    return;
  }
  gsap.registerPlugin(ScrollTrigger);
  gsap.ticker.lagSmoothing(0);

  /* ---------- helpers ---------- */
  function splitWords(el) {
    function walk(node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (n) {
        if (n.nodeType === 3) {
          var frag = document.createDocumentFragment();
          n.textContent.split(/(\s+)/).forEach(function (part) {
            if (!part) return;
            if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(" ")); return; }
            var m = document.createElement("span"); m.className = "wm"; m.style.cssText = "display:inline-block;overflow:hidden;vertical-align:top;padding:0 .05em .16em;margin:0 -.05em -.16em";
            var i = document.createElement("span"); i.className = "wi"; i.style.display = "inline-block"; i.textContent = part;
            m.appendChild(i); frag.appendChild(m);
          });
          node.replaceChild(frag, n);
        } else if (n.nodeType === 1 && n.tagName !== "BR") walk(n);
      });
    }
    walk(el);
    return $$(".wi", el);
  }

  /* ---------- progress + nav ---------- */
  gsap.to(".progress span", { scaleX: 1, ease: "none", scrollTrigger: { start: 0, end: "max", scrub: 0.2 } });
  var shell = $(".nav-shell"), lastY = 0;
  ScrollTrigger.create({ start: 0, end: "max", onUpdate: function (s) { var y = s.scroll(); shell.classList.toggle("hide", y > lastY && y > 500); lastY = y; } });

  /* ---------- magnetic + tilt ---------- */
  if (fine && !RM) {
    $$("[data-magnetic]").forEach(function (el) {
      var qx = gsap.quickTo(el, "x", { duration: 0.5, ease: "elastic.out(1,.5)" }), qy = gsap.quickTo(el, "y", { duration: 0.5, ease: "elastic.out(1,.5)" });
      el.addEventListener("pointermove", function (e) { var r = el.getBoundingClientRect(); qx((e.clientX - (r.left + r.width / 2)) * 0.25); qy((e.clientY - (r.top + r.height / 2)) * 0.3); });
      el.addEventListener("pointerleave", function () { qx(0); qy(0); });
    });
    $$("[data-tilt]").forEach(function (el) {
      var max = el.classList.contains("deck") ? 1.2 : 3;
      gsap.set(el, { transformPerspective: 900 });
      var rX = gsap.quickTo(el, "rotationX", { duration: 0.7, ease: "power3" }), rY = gsap.quickTo(el, "rotationY", { duration: 0.7, ease: "power3" });
      el.addEventListener("pointermove", function (e) { var r = el.getBoundingClientRect(); rY(((e.clientX - r.left) / r.width - 0.5) * max * 2); rX(-((e.clientY - r.top) / r.height - 0.5) * max * 2); });
      el.addEventListener("pointerleave", function () { rX(0); rY(0); });
    });
  }

  /* ---------- intro: loader wipe, hero ---------- */
  var heroH1 = $(".hero .display");
  var heroWords = splitWords(heroH1);
  var heroIn = $$(".hero [data-in]");
  function intro() {
    var loader = $(".loader");
    gsap.set(loader, { clipPath: "circle(150% at 50% 50%)" });
    var tl = gsap.timeline({ defaults: { ease: "expo.out" } });
    tl.to(".loader-mark", { scale: 1.15, duration: 0.5, delay: 0.5 })
      .to(loader, { clipPath: "circle(0% at 50% 50%)", duration: 1.1, ease: "expo.inOut" }, ">-0.05")
      .set(loader, { display: "none" })
      .from(heroWords, { yPercent: 115, rotate: 5, duration: 1.2, stagger: 0.08 }, "-=0.7")
      .to(heroIn, { opacity: 1, y: 0, duration: 0.9, stagger: 0.09 }, "-=0.9")
      .from(".nav", { y: -50, opacity: 0, duration: 0.9 }, "-=1.1")
      .from(".obj", { scale: 0.5, opacity: 0, rotate: function (i) { return (i % 2 ? 1 : -1) * 18; }, duration: 1.3, stagger: 0.1, ease: "elastic.out(1,.6)" }, "-=1.0");
  }
  if (RM) { $$(".js-hide").forEach(function (e) { e.style.opacity = 1; e.style.transform = "none"; }); var lo = $(".loader"); if (lo) lo.style.display = "none"; }
  else { var started = false, go = function () { if (started) return; started = true; intro(); }; window.addEventListener("load", go); setTimeout(go, 2500); }

  /* ---------- hero parallax ---------- */
  if (!RM) {
    var objs = $$(".obj");
    if (fine) window.addEventListener("pointermove", function (e) {
      var nx = e.clientX / window.innerWidth - 0.5, ny = e.clientY / window.innerHeight - 0.5;
      objs.forEach(function (o) { var d = +o.getAttribute("data-d") || 20; gsap.to(o, { x: nx * d * 2, y: ny * d * 2, duration: 1.2, ease: "power3.out", overwrite: "auto" }); });
    }, { passive: true });
    gsap.to(".b1", { yPercent: 25, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true } });
    gsap.to(".o-mail, .o-pill, .o-note", { yPercent: -30, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true } });
  }

  /* ---------- marquee strip ---------- */
  var phrases = ["write email", "bullet points", "prompt mode", "make it shorter", "blog mode", "Hinglish in, English out", "humanize this", "extend", "casual tone"];
  var track = $("[data-track]");
  if (track) {
    var group = phrases.map(function (p) { return "<span>" + p + "</span>"; }).join("");
    track.innerHTML = group + group + group + group;
    if (!RM) {
      var mq = gsap.fromTo(track, { xPercent: 0 }, { xPercent: -50, duration: 40, ease: "none", repeat: -1 });
      ScrollTrigger.create({ trigger: ".strip", start: "top bottom", end: "bottom top", onUpdate: function (s) {
        gsap.to(mq, { timeScale: 1 + Math.abs(s.getVelocity()) / 260, duration: 0.25, overwrite: true });
        gsap.to(mq, { timeScale: 1, duration: 1.2, delay: 0.25, overwrite: "auto" });
      } });
    }
  }

  /* ---------- scroll reveals ---------- */
  $$("[data-split]").forEach(function (el) {
    if (el === heroH1) return;
    var words = splitWords(el);
    if (RM) return;
    gsap.from(words, { yPercent: 115, rotate: 4, duration: 1.1, ease: "expo.out", stagger: 0.05, scrollTrigger: { trigger: el, start: "top 88%", once: true } });
  });
  if (!RM) {
    gsap.set("[data-reveal]", { opacity: 0 });
    ScrollTrigger.batch("[data-reveal]", { start: "top 90%", once: true, onEnter: function (els) { gsap.fromTo(els, { y: 60, opacity: 0, rotate: 2 }, { y: 0, opacity: 1, rotate: 0, duration: 1, stagger: 0.12, ease: "expo.out", overwrite: true }); } });
  }

  /* ---------- story: a sentence as squares (scroll-scrubbed) ---------- */
  var cv = $("#dots");
  if (cv) {
    var W = [["Um,", "f"], ["so", "f"], ["I", "k"], ["was", "k"], ["thinking", "k"], ["we", "k"], ["should", "k"], ["move", "k"], ["the", "k"], ["the", "r"], ["demo", "k"], ["to", "k"], ["Thursday,", "x"], ["no", "x"], ["wait,", "x"], ["Friday,", "k"], ["because", "k"], ["uh", "f"], ["Rahul", "k"], ["is", "k"], ["out", "k"], ["until", "k"], ["then.", "k"], ["Can", "k"], ["you,", "k"], ["like,", "f"], ["tell", "k"], ["him", "k"], ["to", "k"], ["send", "k"], ["the", "k"], ["the", "r"], ["slides", "k"], ["by", "k"], ["Thursday", "k"], ["night?", "k"]];
    var COL = { k: "#2e62ff", f: "#ffc933", r: "#9b6bff", x: "#ff6b57" };
    var S = 560, SIZE = 38;
    var seed = 7; var rnd = function () { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    var counters = { k: 0, f: 0, r: 0, x: 0 };
    var items = W.map(function (w, i) {
      var it = { t: w[0], k: w[1], i: i };
      it.ax = 40 + (i % 6) * 88 + (rnd() - 0.5) * 26; it.ay = 40 + Math.floor(i / 6) * 88 + (rnd() - 0.5) * 26; it.ar = (rnd() - 0.5) * 0.5;
      var n = counters[it.k]++;
      if (it.k === "k") { it.bx = 18 + (n % 6) * 54; it.by = 58 + Math.floor(n / 6) * 54; }
      else if (it.k === "f") { it.bx = 388 + (n % 2) * 54; it.by = 58 + Math.floor(n / 2) * 54; }
      else if (it.k === "r") { it.bx = 388 + n * 54; it.by = 190; }
      else { it.bx = 388 + n * 54; it.by = 270; }
      return it;
    });
    // final paragraph layout for kept words
    var fx = 24, fy = 150, line = 0, maxW = 512;
    items.forEach(function (it) {
      if (it.k !== "k") return;
      it.rw = 18 + it.t.length * 9.2;
      if (fx + it.rw > maxW) { fx = 24; fy += 38; }
      it.cx = fx; it.cy = fy; fx += it.rw + 8;
    });
    var ctx = cv.getContext("2d"), dpr = 1;
    var P = 0;
    function resize() { dpr = Math.min(2, window.devicePixelRatio || 1); var w = cv.clientWidth; cv.width = w * dpr; cv.height = w * dpr; draw(); }
    function rr(x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
    function mix(c1, c2, t) { var a = parseInt(c1.slice(1), 16), b = parseInt(c2.slice(1), 16); var r = Math.round(lerp(a >> 16, b >> 16, t)), g = Math.round(lerp((a >> 8) & 255, (b >> 8) & 255, t)), bl = Math.round(lerp(a & 255, b & 255, t)); return "rgb(" + r + "," + g + "," + bl + ")"; }
    function draw() {
      var s = cv.width / S; ctx.setTransform(s, 0, 0, s, 0, 0); ctx.clearRect(0, 0, S, S);
      var e1 = smooth(0.06, 0.34, P), eCol = smooth(0.2, 0.4, P), eRem = smooth(0.5, 0.66, P), e3 = smooth(0.62, 0.92, P);
      ctx.font = "500 11px 'JetBrains Mono', monospace"; ctx.textBaseline = "alphabetic";
      if (e1 > 0.7 && eRem < 0.6) { ctx.globalAlpha = smooth(0.7, 1, e1) * (1 - smooth(0.2, 0.6, eRem)); ctx.fillStyle = "#0e0e2c"; ctx.fillText("KEPT 27", 18, 44); ctx.fillText("FILLER 4", 388, 44); ctx.fillText("REPEAT 2", 388, 176); ctx.fillText("CHANGED MIND 3", 388, 256); ctx.globalAlpha = 1; }
      items.forEach(function (it) {
        var x = lerp(it.ax, it.bx, e1), y = lerp(it.ay, it.by, e1), rot = lerp(it.ar, 0, e1), w = SIZE, h = SIZE, alpha = 1;
        if (it.k === "k") { x = lerp(x, it.cx, e3); y = lerp(y, it.cy, e3); w = lerp(SIZE, it.rw, e3); h = lerp(SIZE, 28, e3); rot = rot * (1 - e3); }
        else { var sc = 1 - eRem; alpha = sc; w = h = SIZE * sc; x += (SIZE - w) / 2; y += (SIZE - h) / 2; if (alpha <= 0.01) return; }
        ctx.globalAlpha = alpha; ctx.save(); ctx.translate(x + w / 2, y + h / 2); ctx.rotate(rot);
        ctx.fillStyle = mix("#c3c6dc", COL[it.k], eCol); rr(-w / 2, -h / 2, w, h, 7); ctx.fill();
        if (it.k === "k" && e3 > 0.8) { ctx.globalAlpha = smooth(0.8, 1, e3); ctx.fillStyle = "#fff"; ctx.font = "600 13px 'Inter', sans-serif"; ctx.textAlign = "center"; ctx.fillText(it.t, 0, 4.5); ctx.textAlign = "start"; }
        ctx.restore(); ctx.globalAlpha = 1;
      });
    }
    var cnt = $("#storyCount"), lineEl = $("#storyLine"), fin = $("#storyFinal"), lastStage = -1;
    function stage(p) {
      var st = p < 0.2 ? 0 : p < 0.5 ? 1 : p < 0.62 ? 2 : 3;
      if (st !== lastStage) {
        lastStage = st;
        var txt = [["36 WORDS SAID", "Scroll. Every square is a word you spoke."], ["SORTED INTO 4 KINDS", "Fillers, repeats and changes of mind get found. The rest is what you meant."], ["REMOVING 9 WORDS", "Four fillers, two repeats, and three words you took back."], ["27 WORDS KEPT", "Nothing added. Nothing invented. Just what you meant."]][st];
        cnt.textContent = txt[0]; lineEl.textContent = txt[1];
      }
      fin.classList.toggle("on", p > 0.92);
    }
    window.addEventListener("resize", resize);
    if (RM) { P = 1; resize(); stage(1); }
    else {
      ScrollTrigger.create({ trigger: ".story", start: "top top", end: "bottom bottom", scrub: 0.4, onUpdate: function (s) { P = s.progress; draw(); stage(P); } });
      resize(); stage(0);
    }
  }

  /* ---------- pills + hold ---------- */
  function setPill(p, s) { if (p) p.setAttribute("data-state", s); }
  function holdable(btn, onStart, onStop) {
    var down = false;
    function start(e) { if (down) return; down = true; if (e && e.pointerId != null && btn.setPointerCapture) try { btn.setPointerCapture(e.pointerId); } catch (err) {} onStart(); }
    function stop() { if (!down) return; down = false; onStop(); }
    btn.addEventListener("pointerdown", start); btn.addEventListener("pointerup", stop); btn.addEventListener("pointercancel", stop); btn.addEventListener("lostpointercapture", stop);
    btn.addEventListener("keydown", function (e) { if (e.code === "Enter" && !e.repeat) start(); });
    btn.addEventListener("keyup", function (e) { if (e.code === "Enter") stop(); });
  }

  /* ---------- hero demo ---------- */
  var scenarios = [
    { tab: "Email", label: "write email · professional tone", chips: ["filler ×1", "mode: email", "tone: professional"],
      said: [["um ", "fill"], ["tell sir that I am not feeling well so I cannot attend tomorrow's exam, please let me know what I can do, ", ""], ["write email", "cmd"], [" ", ""], ["professional tone", "cmd"]],
      out: "Subject: Request regarding tomorrow's exam\n\nDear Sir,\n\nI am not feeling well and will not be able to attend tomorrow's exam. I would be grateful if you could let me know what options are available.\n\nThank you for your understanding.\n\nRegards,\nNayan" },
    { tab: "Bullets", label: "bullet points", chips: ["filler ×1", "mode: bullets"],
      said: [["so today I finished the homepage design, ", ""], ["uh ", "fill"], ["fixed the navbar and updated the hero section, ", ""], ["bullet points", "cmd"]],
      out: "Progress today\n\n- Finished the homepage design\n- Fixed the navbar\n- Updated the hero section" },
    { tab: "Hinglish", label: "auto English · casual tone", chips: ["Hinglish → English", "tone: casual"],
      said: [["kal tak main file bhej dunga, sir ko bol dena thoda late ho gaya, ", ""], ["casual tone", "cmd"]],
      out: "I will send the file by tomorrow. Could you let sir know it is running a little late?" },
    { tab: "Blog (yours)", label: "blog mode · a mode you wrote", chips: ["custom mode", "filler ×1"],
      said: [["blog mode ", "cmd"], ["my trip to Khajuraho was amazing, ", ""], ["like ", "fill"], ["the temples, the carvings, I went with friends and we stayed two days", ""]],
      out: "Two days in Khajuraho\n\nI did not expect a place of stone to feel so alive. The temples are covered in carvings so fine that I kept stopping mid-step just to look closer.\n\nI went with friends, and two days turned out to be the right amount of time: long enough to wander slowly, short enough to leave wanting more." }
  ];
  var saidEl = $("#said"), outEl = $("#out"), chipEl = $("#chipline"), labelEl = $(".js-mode-label"), scenEl = $("#scen"), heroPill = $("#hold .pill");
  var cur = 0, runId = 0, userTouched = false, deckVisible = false, busy = false, typed = 0, holdStart = 0, typer = null;
  function saidLen(s) { return s.said.reduce(function (n, seg) { return n + seg[0].length; }, 0); }
  function renderSaid(s, upto, caret) {
    saidEl.textContent = ""; var left = upto;
    s.said.forEach(function (seg) { if (left <= 0) return; var t = seg[0].slice(0, left); left -= seg[0].length; if (!t) return; var sp = document.createElement("span"); if (seg[1]) sp.className = seg[1]; sp.textContent = t; saidEl.appendChild(sp); });
    if (caret) { var c = document.createElement("span"); c.className = "caret"; saidEl.appendChild(c); }
  }
  function selectScen(i) { cur = i; $$("button", scenEl).forEach(function (b, n) { b.setAttribute("aria-selected", n === i ? "true" : "false"); }); labelEl.textContent = scenarios[i].label; }
  function showFinal(i) { var s = scenarios[i]; selectScen(i); renderSaid(s, saidLen(s), false); outEl.textContent = s.out; setPill(heroPill, "done"); chipEl.innerHTML = s.chips.map(function (c) { return '<span class="mchip">' + c + "</span>"; }).join(""); }
  scenarios.forEach(function (s, i) { var b = document.createElement("button"); b.type = "button"; b.setAttribute("role", "tab"); b.textContent = s.tab; b.addEventListener("click", function () { userTouched = true; runId++; busy = false; showFinal(i); setPill(heroPill, "idle"); }); scenEl.appendChild(b); });
  function beginDemo() {
    if (busy) return; busy = true; var my = ++runId; var s = scenarios[cur]; typed = 0; holdStart = performance.now();
    outEl.textContent = ""; chipEl.innerHTML = ""; renderSaid(s, 0, true); setPill(heroPill, "listening"); clearInterval(typer);
    typer = setInterval(function () { if (my !== runId) { clearInterval(typer); return; } typed = Math.min(saidLen(s), typed + 1); renderSaid(s, typed, true); if (typed >= saidLen(s)) clearInterval(typer); }, 30);
  }
  async function endDemo() {
    if (!busy) return; var my = runId; clearInterval(typer); var s = scenarios[cur], total = saidLen(s);
    while (typed < total) { if (my !== runId) return; typed = Math.min(total, typed + 4); renderSaid(s, typed, true); await wait(12); }
    if (my !== runId) return; renderSaid(s, total, false); setPill(heroPill, "processing"); await wait(750); if (my !== runId) return; setPill(heroPill, "done");
    for (var k = 1; k <= s.out.length; k += 2) { if (my !== runId) return; outEl.textContent = s.out.slice(0, k); await wait(8); }
    outEl.textContent = s.out; chipEl.innerHTML = s.chips.map(function (c) { return '<span class="mchip">' + c + "</span>"; }).join("");
    if (!RM) gsap.from("#chipline .mchip", { y: 10, opacity: 0, scale: 0.7, duration: 0.5, stagger: 0.08, ease: "back.out(2)" });
    busy = false;
    if (!userTouched) { await wait(3200); if (my === runId && !userTouched && deckVisible) { cur = (cur + 1) % scenarios.length; selectScen(cur); autoRun(); } }
  }
  async function autoRun() { beginDemo(); var my = runId; await wait(Math.min(3600, saidLen(scenarios[cur]) * 30 + 300)); if (my === runId && !userTouched) endDemo(); }
  holdable($("#hold"), function () { userTouched = true; if (busy) { runId++; busy = false; } beginDemo(); }, function () { if (performance.now() - holdStart < 250) { typed = 0; holdStart = performance.now(); setTimeout(endDemo, 60); } else endDemo(); });
  var deck = $(".deck");
  if (deck) { selectScen(0); showFinal(0); ScrollTrigger.create({ trigger: deck, start: "top 85%", end: "bottom 15%", onToggle: function (s) { deckVisible = s.isActive; if (s.isActive && !userTouched && !busy) setTimeout(function () { if (deckVisible && !userTouched && !busy) autoRun(); }, 500); } }); }

  var pill2 = $("#hold2 .pill"), stage2 = $(".stage-pill"), stage2Visible = false, t2;
  function releasePill2() { setPill(pill2, "processing"); t2 = setTimeout(function () { setPill(pill2, "done"); t2 = setTimeout(function () { setPill(pill2, "idle"); }, 1100); }, 700); }
  if (pill2) { holdable($("#hold2"), function () { clearTimeout(t2); setPill(pill2, "listening"); }, releasePill2); ScrollTrigger.create({ trigger: stage2, start: "top 80%", end: "bottom 20%", onToggle: function (s) { stage2Visible = s.isActive; } }); }
  var spaceDown = false, spaceTarget = null;
  window.addEventListener("keydown", function (e) {
    if (e.code !== "Space" || e.repeat || spaceDown) return;
    var a = document.activeElement, tag = a && a.tagName; if (tag === "INPUT" || tag === "TEXTAREA" || tag === "BUTTON" || tag === "A" || tag === "SUMMARY") return;
    var t = deckVisible ? "hero" : stage2Visible ? "stage" : null; if (!t) return;
    e.preventDefault(); spaceDown = true; spaceTarget = t;
    if (t === "hero") { userTouched = true; if (busy) { runId++; busy = false; } beginDemo(); } else { clearTimeout(t2); setPill(pill2, "listening"); }
  });
  window.addEventListener("keyup", function (e) { if (e.code !== "Space" || !spaceDown) return; spaceDown = false; if (spaceTarget === "hero") endDemo(); else releasePill2(); });

  /* ---------- modes rail: arrows + drag ---------- */
  var rail = $("#rail");
  if (rail) {
    var step = function () { var c = $(".mc", rail); return c ? c.getBoundingClientRect().width + 22 : 320; };
    $("#next").addEventListener("click", function () { rail.scrollBy({ left: step(), behavior: RM ? "auto" : "smooth" }); });
    $("#prev").addEventListener("click", function () { rail.scrollBy({ left: -step(), behavior: RM ? "auto" : "smooth" }); });
    var drag = null;
    rail.addEventListener("pointerdown", function (e) { if (e.pointerType === "touch") return; drag = { x: e.clientX, left: rail.scrollLeft }; rail.classList.add("drag"); });
    window.addEventListener("pointermove", function (e) { if (drag) rail.scrollLeft = drag.left - (e.clientX - drag.x); });
    window.addEventListener("pointerup", function () { if (drag) { drag = null; rail.classList.remove("drag"); } });
    rail.addEventListener("keydown", function (e) { if (e.key === "ArrowRight") rail.scrollBy({ left: step(), behavior: "smooth" }); if (e.key === "ArrowLeft") rail.scrollBy({ left: -step(), behavior: "smooth" }); });
  }

  /* ---------- tone toggle ---------- */
  var tones = ["Dear Priya, please note that the invoice is delayed because the client's payment is still pending. I will follow up with them tomorrow.", "Hey Priya, the invoice is running late. The client hasn't paid yet, so I'll chase them tomorrow.", "hey priya, invoice is late cuz the client hasn't paid. chasing them tmrw"];
  var toneOut = $("#toneOut"), tg = $("[data-toggle]");
  function typeInto(el, text, speed) {
    el.textContent = ""; var i = 0; var key = (el._k = (el._k || 0) + 1);
    return new Promise(function (res) { (function step() { if (el._k !== key) return res(); i = Math.min(text.length, i + Math.max(1, Math.round(speed))); el.textContent = text.slice(0, i); if (i < text.length) setTimeout(step, 14); else res(); })(); });
  }
  if (tg && toneOut) {
    var tbs = $$("button", tg), th = $(".thumb", tg);
    var setTone = function (i, instant) {
      tbs.forEach(function (b, n) { b.classList.toggle("on", n === i); });
      var b = tbs[i]; gsap.to(th, { x: b.offsetLeft - 4, width: b.offsetWidth, duration: instant || RM ? 0 : 0.55, ease: "expo.out" });
      if (instant || RM) toneOut.textContent = tones[i]; else typeInto(toneOut, tones[i], 3);
    };
    tbs.forEach(function (b, i) { b.addEventListener("click", function () { setTone(i); }); });
    setTone(0, true); window.addEventListener("load", function () { setTone(0, true); });
  }

  /* ---------- vocabulary ---------- */
  var vForm = $("#vocabForm"), vIn = $("#vocabIn"), vList = $("#vocabList");
  function addWord(w, animate) {
    var s = document.createElement("span"); s.className = "vword"; s.appendChild(document.createTextNode(w + " "));
    var x = document.createElement("button"); x.type = "button"; x.setAttribute("aria-label", "Remove " + w); x.textContent = "×"; s.appendChild(x); vList.appendChild(s);
    if (animate && !RM) gsap.from(s, { scale: 0, rotate: -14, duration: 0.8, ease: "elastic.out(1,.55)" });
    x.addEventListener("click", function () { if (RM) { s.remove(); return; } gsap.to(s, { scale: 0, opacity: 0, duration: 0.25, onComplete: function () { s.remove(); } }); });
  }
  if (vForm) { ["Khajuraho", "Groq", "Priya"].forEach(function (w) { addWord(w, false); }); vForm.addEventListener("submit", function (e) { e.preventDefault(); var w = vIn.value.trim().slice(0, 24); if (!w || $$(".vword", vList).length >= 12) return; addWord(w, true); vIn.value = ""; }); }

  /* ---------- languages ---------- */
  var words = ["नमस्ते", "Hello", "Kya haal hai", "Hola", "Bonjour", "こんにちは", "Hallo", "مرحبا", "Ciao"], lw = $("#langWord");
  if (lw && !RM) { var li = 0; setInterval(function () { li = (li + 1) % words.length; gsap.timeline().to(lw, { yPercent: -40, opacity: 0, rotate: -4, duration: 0.3, ease: "power2.in" }).call(function () { lw.textContent = words[li]; }).fromTo(lw, { yPercent: 40, rotate: 4 }, { yPercent: 0, opacity: 1, rotate: 0, duration: 0.6, ease: "expo.out" }); }, 2000); }

  /* ---------- pill picker ---------- */
  var pick = $("#pick");
  if (pick) $$("button", pick).forEach(function (b) { b.addEventListener("click", function () { $$("button", pick).forEach(function (x) { x.setAttribute("aria-checked", x === b ? "true" : "false"); }); document.documentElement.setAttribute("data-pill", b.getAttribute("data-style")); if (!RM) gsap.fromTo(b, { scale: 0.86 }, { scale: 1, duration: 0.7, ease: "elastic.out(1,.5)" }); }); });

  /* ---------- HUD: section index + keyboard hint ---------- */
  var secs = [["#top", "TOP"], ["#how", "HOW IT READS"], ["#try", "TRY IT"], ["#modes", "MODES"], ["#play", "MAKE IT YOURS"], ["#offline", "OFFLINE"], ["#pricing", "PRICE"], ["#faq", "QUESTIONS"]];
  var hudN = $("#hudN"), hudName = $("#hudName"), hudL = $("#hudL");
  secs.forEach(function (s, i) {
    var el = $(s[0]); if (!el) return;
    ScrollTrigger.create({ trigger: el, start: "top 50%", end: "bottom 50%", onToggle: function (st) { if (!st.isActive) return; hudN.textContent = ("0" + i).slice(-2); hudName.textContent = s[1]; hudL.textContent = s[0] === "#try" ? "HOLD SPACE TO TALK" : s[0] === "#how" ? "KEEP SCROLLING" : "SCROLL ↓"; } });
  });

  window.addEventListener("load", function () { ScrollTrigger.refresh(); });
})();
