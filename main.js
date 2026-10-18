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

  /* ---------- download buttons ---------- */
  $$(".js-version").forEach(function (el) { if (cfg.version) el.textContent = "v" + cfg.version; });
  $$(".js-size").forEach(function (el) { if (cfg.size) el.textContent = cfg.size; });
  $$(".js-repo").forEach(function (a) { if (cfg.repoUrl) a.href = cfg.repoUrl; });
  var note = $(".js-note");
  $$(".js-download").forEach(function (a) {
    if (cfg.downloadUrl) { a.href = cfg.downloadUrl; a.setAttribute("download", ""); }
    else a.addEventListener("click", function (e) {
      e.preventDefault();
      if (note) { note.classList.add("show"); note.scrollIntoView({ block: "center", behavior: RM ? "auto" : "smooth" }); }
    });
  });

  if (!hasGsap) { // network blocked the CDN: show everything, skip motion
    $$(".js-hide").forEach(function (e) { e.classList.remove("js-hide"); e.style.opacity = 1; e.style.transform = "none"; });
    var c = $(".curtain"); if (c) c.style.display = "none";
    return;
  }
  gsap.registerPlugin(ScrollTrigger);
  gsap.ticker.lagSmoothing(0); // keep wall-clock timing even when the tab is throttled

  /* ---------- helpers ---------- */
  function splitWords(el) { // wraps each word in a masked inner span, keeps <em>/<br>
    function walk(node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (n) {
        if (n.nodeType === 3) {
          var frag = document.createDocumentFragment();
          n.textContent.split(/(\s+)/).forEach(function (part) {
            if (!part) return;
            if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(" ")); return; }
            var m = document.createElement("span"); m.className = "wm"; m.style.cssText = "display:inline-block;overflow:hidden;vertical-align:top;padding:0 .04em .14em;margin:0 -.04em -.14em";
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

  /* ---------- scroll progress ---------- */
  gsap.to(".progress span", { scaleX: 1, ease: "none", scrollTrigger: { start: 0, end: "max", scrub: 0.2 } });

  /* ---------- nav: hide on scroll down, seg indicator ---------- */
  var shell = $(".nav-shell");
  var lastY = 0;
  ScrollTrigger.create({ start: 0, end: "max", onUpdate: function (s) {
    var y = s.scroll();
    shell.classList.toggle("hide", y > lastY && y > 400);
    lastY = y;
  } });
  var seg = $("[data-seg]");
  var segLinks = $$("a", seg);
  var thumb = $(".seg-thumb", seg);
  function moveThumb(a) {
    if (!thumb || !a) return;
    segLinks.forEach(function (l) { l.classList.toggle("on", l === a); });
    gsap.to(thumb, { x: a.offsetLeft - 4, width: a.offsetWidth, duration: RM ? 0 : 0.5, ease: "expo.out" });
  }
  if (segLinks.length) {
    gsap.set(thumb, { x: segLinks[0].offsetLeft - 4, width: segLinks[0].offsetWidth });
    segLinks.forEach(function (a) {
      var sec = $(a.getAttribute("href"));
      if (!sec) return;
      ScrollTrigger.create({ trigger: sec, start: "top 55%", end: "bottom 55%", onToggle: function (s) { if (s.isActive) moveThumb(a); } });
    });
    window.addEventListener("load", function () { moveThumb($("a.on", seg) || segLinks[0]); });
  }

  /* ---------- magnetic + tilt ---------- */
  if (fine && !RM) {
    $$("[data-magnetic]").forEach(function (el) {
      var qx = gsap.quickTo(el, "x", { duration: 0.5, ease: "elastic.out(1,.5)" }), qy = gsap.quickTo(el, "y", { duration: 0.5, ease: "elastic.out(1,.5)" });
      el.addEventListener("pointermove", function (e) {
        var r = el.getBoundingClientRect();
        qx((e.clientX - (r.left + r.width / 2)) * 0.28); qy((e.clientY - (r.top + r.height / 2)) * 0.34);
      });
      el.addEventListener("pointerleave", function () { qx(0); qy(0); });
    });
    $$("[data-tilt]").forEach(function (el) {
      var big = el.classList.contains("deck") || el.classList.contains("paper");
      var max = big ? 1.6 : 3.5;
      gsap.set(el, { transformPerspective: 900 });
      var rX = gsap.quickTo(el, "rotationX", { duration: 0.6, ease: "power3" }), rY = gsap.quickTo(el, "rotationY", { duration: 0.6, ease: "power3" });
      el.addEventListener("pointermove", function (e) {
        var r = el.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width - 0.5, py = (e.clientY - r.top) / r.height - 0.5;
        rY(px * max * 2); rX(-py * max * 2);
      });
      el.addEventListener("pointerleave", function () { rX(0); rY(0); });
    });
  }

  /* ---------- intro: curtain, hero entrance ---------- */
  var heroH1 = $(".hero .display");
  var heroWords = splitWords(heroH1);
  var heroIn = $$(".hero [data-in]");
  function intro() {
    var tl = gsap.timeline({ defaults: { ease: "expo.out" } });
    tl.to(".curtain", { yPercent: -100, duration: 1.0, ease: "expo.inOut", delay: 0.25 })
      .set(".curtain", { display: "none" })
      .from(heroWords, { yPercent: 115, rotate: 4, duration: 1.2, stagger: 0.07 }, "-=0.55")
      .to(heroIn, { opacity: 1, y: 0, duration: 0.9, stagger: 0.1 }, "-=0.8")
      .from(".nav", { y: -40, opacity: 0, duration: 0.8 }, "-=1.1")
      .from(".wd", { scale: 0.8, opacity: 0, y: 30, duration: 1.1, stagger: 0.12, ease: "expo.out" }, "-=1.0");
  }
  if (RM) { $$(".js-hide").forEach(function (e) { e.style.opacity = 1; e.style.transform = "none"; }); var cu = $(".curtain"); if (cu) cu.style.display = "none"; }
  else {
    gsap.set(heroWords, { yPercent: 0 });
    var started = false;
    var go = function () { if (started) return; started = true; intro(); };
    window.addEventListener("load", go); setTimeout(go, 2500);
  }

  /* ---------- hero parallax ---------- */
  if (!RM) {
    var shapes = $$(".wd");
    if (fine) {
      window.addEventListener("pointermove", function (e) {
        var nx = e.clientX / window.innerWidth - 0.5, ny = e.clientY / window.innerHeight - 0.5;
        shapes.forEach(function (s) { var d = +s.getAttribute("data-depth") || 20; gsap.to(s, { x: nx * d * 2, y: ny * d * 2, duration: 1.2, ease: "power3.out", overwrite: "auto" }); });
      }, { passive: true });
    }
    gsap.to(".wd1, .wd3", { yPercent: 40, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true } });
    gsap.to(".wd2, .wd4", { yPercent: -30, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true } });
  }

  /* ---------- ribbons (velocity-reactive marquee) ---------- */
  var phrases = ["write email, professional tone", "bullet points", "prompt mode", "make it shorter", "blog mode", "Hinglish in, English out", "humanize this", "extend", "casual tone"];
  var tweens = [];
  $$(".track").forEach(function (track) {
    var dir = +track.getAttribute("data-track") || 1;
    var group = phrases.map(function (p) { return "<span>" + p + "</span>"; }).join("");
    track.innerHTML = group + group + group + group;
    if (RM) return;
    var tw = gsap.fromTo(track, { xPercent: dir > 0 ? 0 : -50 }, { xPercent: dir > 0 ? -50 : 0, duration: 38, ease: "none", repeat: -1 });
    tweens.push(tw);
  });
  if (!RM) {
    ScrollTrigger.create({ trigger: ".ribbons", start: "top bottom", end: "bottom top", onUpdate: function (s) {
      var v = s.getVelocity();
      gsap.to(tweens, { timeScale: 1 + Math.abs(v) / 320, duration: 0.25, overwrite: true });
      gsap.to(tweens, { timeScale: 1, duration: 1.2, delay: 0.25, overwrite: "auto" });
    } });
  }

  /* ---------- scroll reveals ---------- */
  $$("[data-split]").forEach(function (el) {
    if (el === heroH1) return;
    var words = splitWords(el);
    if (RM) return;
    gsap.from(words, { yPercent: 115, rotate: 3, duration: 1.1, ease: "expo.out", stagger: 0.045, scrollTrigger: { trigger: el, start: "top 88%", once: true } });
  });
  if (!RM) {
    ScrollTrigger.batch("[data-reveal]", {
      start: "top 90%", once: true,
      onEnter: function (els) { gsap.fromTo(els, { y: 50, opacity: 0, rotate: 1.5 }, { y: 0, opacity: 1, rotate: 0, duration: 0.9, stagger: 0.12, ease: "expo.out", overwrite: true }); }
    });
    gsap.set("[data-reveal]", { opacity: 0 });
  }

  /* ---------- pills ---------- */
  function setPill(p, s) { if (p) p.setAttribute("data-state", s); }
  function holdable(btn, pill, onStart, onStop) {
    var down = false;
    function start(e) { if (down) return; down = true; if (e && e.pointerId != null && btn.setPointerCapture) try { btn.setPointerCapture(e.pointerId); } catch (err) {} onStart(); }
    function stop() { if (!down) return; down = false; onStop(); }
    btn.addEventListener("pointerdown", start);
    btn.addEventListener("pointerup", stop); btn.addEventListener("pointercancel", stop); btn.addEventListener("lostpointercapture", stop);
    btn.addEventListener("keydown", function (e) { if (e.code === "Enter" && !e.repeat) { start(); } });
    btn.addEventListener("keyup", function (e) { if (e.code === "Enter") stop(); });
    return { start: start, stop: stop, isDown: function () { return down; } };
  }

  /* ---------- hero demo ---------- */
  var scenarios = [
    { id: "email", tab: "Email", label: "write email · professional tone", chips: ["filler ×1", "mode: email", "tone: professional"],
      said: [["um ", "fill"], ["tell sir that I am not feeling well so I cannot attend tomorrow's exam, please let me know what I can do, ", ""], ["write email", "cmd"], [" ", ""], ["professional tone", "cmd"]],
      out: "Subject: Request regarding tomorrow's exam\n\nDear Sir,\n\nI am not feeling well and will not be able to attend tomorrow's exam. I would be grateful if you could let me know what options are available.\n\nThank you for your understanding.\n\nRegards,\nNayan" },
    { id: "bullets", tab: "Bullets", label: "bullet points", chips: ["filler ×1", "mode: bullets"],
      said: [["so today I finished the homepage design, ", ""], ["uh ", "fill"], ["fixed the navbar and updated the hero section, ", ""], ["bullet points", "cmd"]],
      out: "Progress today\n\n- Finished the homepage design\n- Fixed the navbar\n- Updated the hero section" },
    { id: "hinglish", tab: "Hinglish", label: "auto English · casual tone", chips: ["Hinglish → English", "tone: casual"],
      said: [["kal tak main file bhej dunga, sir ko bol dena thoda late ho gaya, ", ""], ["casual tone", "cmd"]],
      out: "I will send the file by tomorrow. Could you let sir know it is running a little late?" },
    { id: "blog", tab: "Blog (yours)", label: "blog mode · a mode you wrote", chips: ["custom mode", "filler ×1"],
      said: [["blog mode ", "cmd"], ["my trip to Khajuraho was amazing, ", ""], ["like ", "fill"], ["the temples, the carvings, I went with friends and we stayed two days", ""]],
      out: "Two days in Khajuraho\n\nI did not expect a place of stone to feel so alive. The temples are covered in carvings so fine that I kept stopping mid-step just to look closer.\n\nI went with friends, and two days turned out to be the right amount of time: long enough to wander slowly, short enough to leave wanting more." }
  ];
  var saidEl = $("#said"), outEl = $("#out"), chipEl = $("#chipline"), labelEl = $(".js-mode-label"), scenEl = $("#scen");
  var heroPill = $("#hold .pill");
  var cur = 0, runId = 0, userTouched = false, deckVisible = false, busy = false;
  function saidLen(s) { return s.said.reduce(function (n, seg) { return n + seg[0].length; }, 0); }
  function renderSaid(s, upto, caret) {
    saidEl.textContent = ""; var left = upto;
    s.said.forEach(function (seg) {
      if (left <= 0) return;
      var t = seg[0].slice(0, left); left -= seg[0].length; if (!t) return;
      var sp = document.createElement("span"); if (seg[1]) sp.className = seg[1]; sp.textContent = t; saidEl.appendChild(sp);
    });
    if (caret) { var c = document.createElement("span"); c.className = "caret"; saidEl.appendChild(c); }
  }
  function selectScen(i) {
    cur = i; $$("button", scenEl).forEach(function (b, n) { b.setAttribute("aria-selected", n === i ? "true" : "false"); });
    labelEl.textContent = scenarios[i].label;
  }
  function showFinal(i) {
    var s = scenarios[i]; selectScen(i); renderSaid(s, saidLen(s), false); outEl.textContent = s.out; setPill(heroPill, "done");
    chipEl.innerHTML = s.chips.map(function (c) { return '<span class="mchip">' + c + "</span>"; }).join("");
  }
  scenarios.forEach(function (s, i) {
    var b = document.createElement("button"); b.type = "button"; b.setAttribute("role", "tab"); b.textContent = s.tab;
    b.addEventListener("click", function () { userTouched = true; runId++; busy = false; showFinal(i); setPill(heroPill, "idle"); });
    scenEl.appendChild(b);
  });
  var typed = 0, holdStart = 0, typer = null;
  function beginDemo() {
    if (busy) return; busy = true; var my = ++runId;
    var s = scenarios[cur]; typed = 0; holdStart = performance.now();
    outEl.textContent = ""; chipEl.innerHTML = ""; renderSaid(s, 0, true); setPill(heroPill, "listening");
    clearInterval(typer);
    typer = setInterval(function () {
      if (my !== runId) { clearInterval(typer); return; }
      typed = Math.min(saidLen(s), typed + 1); renderSaid(s, typed, true);
      if (typed >= saidLen(s)) clearInterval(typer);
    }, 30);
  }
  async function endDemo() {
    if (!busy) return; var my = runId; clearInterval(typer);
    var s = scenarios[cur], total = saidLen(s);
    while (typed < total) { if (my !== runId) return; typed = Math.min(total, typed + 4); renderSaid(s, typed, true); await wait(12); }
    if (my !== runId) return; renderSaid(s, total, false);
    setPill(heroPill, "processing"); await wait(750); if (my !== runId) return;
    setPill(heroPill, "done");
    for (var k = 1; k <= s.out.length; k += 2) { if (my !== runId) return; outEl.textContent = s.out.slice(0, k); await wait(8); }
    outEl.textContent = s.out;
    chipEl.innerHTML = s.chips.map(function (c) { return '<span class="mchip">' + c + "</span>"; }).join("");
    if (!RM) gsap.from("#chipline .mchip", { y: 10, opacity: 0, scale: 0.7, duration: 0.5, stagger: 0.08, ease: "back.out(2)" });
    busy = false; if (!userTouched) { await wait(3200); if (my === runId && !userTouched && deckVisible) { cur = (cur + 1) % scenarios.length; selectScen(cur); autoRun(); } }
  }
  async function autoRun() { beginDemo(); var my = runId; await wait(Math.min(3600, saidLen(scenarios[cur]) * 30 + 300)); if (my === runId && !userTouched) endDemo(); }
  var holdHero = holdable($("#hold"), heroPill, function () { userTouched = true; if (busy) { runId++; busy = false; } beginDemo(); }, function () {
    if (performance.now() - holdStart < 250) { /* a tap plays the whole thing */ typed = 0; holdStart = performance.now(); setTimeout(endDemo, 60); } else endDemo();
  });
  var ds = $(".deck");
  if (ds) {
    selectScen(0); showFinal(0);
    ScrollTrigger.create({ trigger: ds, start: "top 85%", end: "bottom 15%", onToggle: function (s) {
      deckVisible = s.isActive;
      if (s.isActive && !userTouched && !busy) { setTimeout(function () { if (deckVisible && !userTouched && !busy) autoRun(); }, 500); }
    } });
  }
  // second holdable: pill style picker stage
  var pill2 = $("#hold2 .pill"), stage2 = $(".stage-pill"), stage2Visible = false;
  if (pill2) {
    var t2;
    holdable($("#hold2"), pill2, function () { clearTimeout(t2); setPill(pill2, "listening"); stage2.classList.add("active"); }, function () {
      setPill(pill2, "processing"); t2 = setTimeout(function () { setPill(pill2, "done"); stage2.classList.remove("active"); t2 = setTimeout(function () { setPill(pill2, "idle"); }, 1100); }, 700);
    });
    ScrollTrigger.create({ trigger: stage2, start: "top 80%", end: "bottom 20%", onToggle: function (s) { stage2Visible = s.isActive; } });
  }
  // Space = hold-to-talk for whichever demo is on screen
  var spaceDown = false, spaceTarget = null;
  window.addEventListener("keydown", function (e) {
    if (e.code !== "Space" || e.repeat || spaceDown) return;
    var a = document.activeElement, tag = a && a.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "BUTTON" || tag === "A" || tag === "SUMMARY") return;
    var t = deckVisible ? "hero" : stage2Visible ? "stage" : null; if (!t) return;
    e.preventDefault(); spaceDown = true; spaceTarget = t;
    if (t === "hero") { userTouched = true; if (busy) { runId++; busy = false; } beginDemo(); }
    else { clearTimeout(t2); setPill(pill2, "listening"); stage2.classList.add("active"); }
  });
  window.addEventListener("keyup", function (e) {
    if (e.code !== "Space" || !spaceDown) return; spaceDown = false;
    if (spaceTarget === "hero") endDemo();
    else { setPill(pill2, "processing"); t2 = setTimeout(function () { setPill(pill2, "done"); stage2.classList.remove("active"); t2 = setTimeout(function () { setPill(pill2, "idle"); }, 1100); }, 700); }
  });

  /* ---------- messy -> clean (scroll scrubbed) ---------- */
  var para = $("#para");
  var toks = [
    ["Um, so ", "f"], ["I was thinking we should move the ", ""], ["the ", "r"], ["demo to ", ""], ["Thursday, no wait, ", "x"], ["Friday", ""], [", because ", ""], ["uh ", "f"],
    ["Rahul is out until then. Can you", ""], [", like,", "f"], [" tell him to send the ", ""], ["the ", "r"], ["slides by Thursday night?", ""]
  ];
  if (para) {
    toks.forEach(function (t) {
      var s = document.createElement("span"); s.className = "tok" + (t[1] ? " rm " + t[1] : ""); s.textContent = t[0]; para.appendChild(s);
    });
    var rm = $$(".tok.rm", para), chipsL = $$(".legend li"), stamps = $$(".stamp");
    stamps[0].classList.add("on");
    var final = function () { gsap.set(rm, { width: 0, opacity: 0 }); chipsL.forEach(function (l) { l.classList.add("on"); }); stamps[1].classList.add("on"); stamps[0].classList.remove("on"); para.style.color = "var(--ink)"; };
    var build = function () {
      rm.forEach(function (n) { n.style.width = ""; n.style.opacity = ""; });
      rm.forEach(function (n) { n.dataset.w = n.scrollWidth; });
      if (RM) { final(); return; }
      var tl = gsap.timeline({ scrollTrigger: { trigger: ".clean", start: "top top", end: "bottom bottom", scrub: 0.6 } });
      rm.forEach(function (n) { gsap.set(n, { width: +n.dataset.w }); });
      tl.to({}, { duration: 2.9 })
        .to(rm, { width: 0, opacity: 0, duration: 1.6, stagger: 0.18, ease: "power2.inOut" }, ">")
        .to(para, { color: "#17130d", duration: 0.5 }, ">-0.4")
        .to({}, { duration: 0.9 });
      // keep legend and stamp in sync when scrubbing backwards
      ScrollTrigger.create({ trigger: ".clean", start: "top top", end: "bottom bottom", onUpdate: function (s) {
        var p = s.progress;
        var th = { f: 0.09, x: 0.19, r: 0.29 };
        chipsL[0].classList.toggle("on", p > th.f); chipsL[1].classList.toggle("on", p > th.x); chipsL[2].classList.toggle("on", p > th.r);
        rm.forEach(function (n) { n.classList.toggle("hl", p > th[n.classList.contains("f") ? "f" : n.classList.contains("x") ? "x" : "r"]); });
        stamps[1].classList.toggle("on", p > 0.78); stamps[0].classList.toggle("on", p <= 0.78);
      } });
    };
    (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(function () { build(); ScrollTrigger.refresh(); });
  }

  /* ---------- speed race ---------- */
  var raceMsg = "Hey team, quick update: the design review moved to Thursday at 3, and I will share the latest mockups tonight so everyone can comment before then.";
  var lanes = $$(".lane");
  function race() {
    lanes.forEach(function (l) {
      var t = $("[data-text]", l), bar = $(".bar i", l), n = $("[data-count]", l), target = +n.getAttribute("data-count");
      var dur = l.getAttribute("data-lane") === "key" ? 7 : 7 * (40 / 160);
      var o = { c: 0, p: 0 };
      gsap.killTweensOf([o, bar]);
      t.textContent = "";
      gsap.fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: dur, ease: "none" });
      gsap.to(o, { c: target, duration: dur, ease: "none", onUpdate: function () { n.textContent = Math.round(o.c); } });
      gsap.to(o, { p: raceMsg.length, duration: dur, ease: "none", onUpdate: function () { t.textContent = raceMsg.slice(0, Math.round(o.p)); } });
    });
  }
  if (lanes.length) {
    if (RM) { lanes.forEach(function (l) { $("[data-text]", l).textContent = raceMsg; $(".bar i", l).style.transform = "scaleX(1)"; $("[data-count]", l).textContent = $("[data-count]", l).getAttribute("data-count"); }); }
    else {
      ScrollTrigger.create({ trigger: ".race", start: "top 75%", once: true, onEnter: race });
      var rb = $("[data-replay]"); if (rb) rb.addEventListener("click", race);
    }
  }

  /* ---------- tone toggle ---------- */
  var tones = [
    "Dear Priya, please note that the invoice is delayed because the client's payment is still pending. I will follow up with them tomorrow.",
    "Hey Priya, the invoice is running late. The client hasn't paid yet, so I'll chase them tomorrow.",
    "hey priya, invoice is late cuz the client hasn't paid. chasing them tmrw"
  ];
  var toneOut = $("#toneOut"), tg = $("[data-toggle]");
  function typeInto(el, text, speed, id) {
    el.textContent = ""; var i = 0; var key = (el._k = (el._k || 0) + 1);
    return new Promise(function (res) {
      (function step() {
        if (el._k !== key) return res();
        i = Math.min(text.length, i + Math.max(1, Math.round(speed))); el.textContent = text.slice(0, i);
        if (i < text.length) setTimeout(step, 14); else res();
      })();
    });
  }
  if (tg && toneOut) {
    var tbs = $$("button", tg), th = $(".thumb", tg);
    var setTone = function (i, instant) {
      tbs.forEach(function (b, n) { b.classList.toggle("on", n === i); });
      var b = tbs[i]; gsap.to(th, { x: b.offsetLeft - 4, width: b.offsetWidth, duration: instant || RM ? 0 : 0.5, ease: "expo.out" });
      if (instant || RM) toneOut.textContent = tones[i]; else typeInto(toneOut, tones[i], 3);
    };
    tbs.forEach(function (b, i) { b.addEventListener("click", function () { setTone(i); }); });
    window.addEventListener("load", function () { setTone(0, true); });
    setTone(0, true);
  }

  /* ---------- modes ---------- */
  var modes = [
    { k: "Email", n: "write email", t: "Subject: Moving the demo to Friday\n\nHi Rahul,\n\nCould we move the demo from Thursday to Friday? I would also appreciate the slides by Thursday night.\n\nThanks,\nNayan" },
    { k: "Bullets", n: "bullet points", t: "Demo update\n\n- Moved from Thursday to Friday\n- Rahul is out until then\n- Slides due Thursday night" },
    { k: "Prompt", n: "prompt mode", t: "Role: senior product designer.\nTask: critique the onboarding screens below.\nRequirements: be specific, rank issues by impact, suggest one fix each.\nOutput: a numbered list." },
    { k: "Blog", n: "blog mode (you wrote it)", t: "Why I moved the demo\n\nSometimes the best schedule change is the one that lets the right person be in the room. Here is what changed, and why Friday works better." },
    { k: "Your mode", n: "name · trigger · instruction · format", t: "Name:  Standup\nSay:   \"standup mode\"\nDo:    Turn my rambling into Yesterday, Today, Blockers.\nShape: three short lines, no fluff." }
  ];
  var chipsEl = $("#modeChips"), mName = $("#modeName"), mText = $("#modeText");
  if (chipsEl) {
    modes.forEach(function (m, i) {
      var b = document.createElement("button"); b.type = "button"; b.setAttribute("role", "tab"); b.textContent = m.k; b.setAttribute("aria-selected", i === 0 ? "true" : "false");
      b.addEventListener("click", function () { setMode(i); }); chipsEl.appendChild(b);
    });
    var setMode = function (i) {
      $$("button", chipsEl).forEach(function (b, n) { b.setAttribute("aria-selected", n === i ? "true" : "false"); });
      mName.textContent = "say: " + modes[i].n; if (RM) mText.textContent = modes[i].t; else typeInto(mText, modes[i].t, 4);
    };
    setMode(0);
  }

  /* ---------- vocabulary ---------- */
  var vForm = $("#vocabForm"), vIn = $("#vocabIn"), vList = $("#vocabList");
  function addWord(w, animate) {
    var s = document.createElement("span"); s.className = "vword"; s.appendChild(document.createTextNode(w + " "));
    var x = document.createElement("button"); x.type = "button"; x.setAttribute("aria-label", "Remove " + w); x.textContent = "×"; s.appendChild(x); vList.appendChild(s);
    if (animate && !RM) gsap.from(s, { scale: 0, rotate: -12, duration: 0.7, ease: "elastic.out(1,.55)" });
    x.addEventListener("click", function () { if (RM) { s.remove(); return; } gsap.to(s, { scale: 0, opacity: 0, duration: 0.25, onComplete: function () { s.remove(); } }); });
  }
  if (vForm) {
    ["Khajuraho", "Groq", "Priya"].forEach(function (w) { addWord(w, false); });
    vForm.addEventListener("submit", function (e) {
      e.preventDefault(); var w = vIn.value.trim().slice(0, 24); if (!w || $$(".vword", vList).length >= 12) return;
      addWord(w, true); vIn.value = "";
    });
  }

  /* ---------- selected-text rewrite ---------- */
  var rwText = $("#rwText"), rwBtn = $("#rwBtn"), rwPill = $("#rwPill");
  var longT = "Our team has been working on the redesign for several weeks now, and we have made a lot of progress on many different parts of the product, but there is still more to do before launch.";
  var shortT = "The redesign is well underway. A few parts remain before launch.";
  var rwShort = false, rwBusy = false;
  if (rwText) {
    rwText.textContent = longT;
    rwBtn.addEventListener("click", async function () {
      if (rwBusy) return; rwBusy = true;
      var target = rwShort ? longT : shortT, cmd = rwShort ? '"Make it shorter"' : '"Undo"';
      if (RM) { rwText.textContent = target; rwShort = !rwShort; rwBtn.textContent = cmd; rwBusy = false; return; }
      rwText.innerHTML = '<span class="sel"></span>'; $(".sel", rwText).textContent = rwText.dataset.cur || (rwShort ? shortT : longT);
      gsap.fromTo(".sel", { backgroundSize: "0% 100%" }, { backgroundSize: "100% 100%", duration: 0.7, ease: "power2.out" });
      $(".sel", rwText).style.backgroundImage = "linear-gradient(rgba(46,98,255,.30), rgba(46,98,255,.30))";
      $(".sel", rwText).style.backgroundRepeat = "no-repeat"; $(".sel", rwText).style.backgroundColor = "transparent";
      await wait(800); setPill(rwPill, "listening"); await wait(1100); setPill(rwPill, "processing"); await wait(650); setPill(rwPill, "done");
      await typeInto(rwText, target, 2); rwText.dataset.cur = target; rwShort = !rwShort; rwBtn.textContent = cmd;
      await wait(700); setPill(rwPill, "idle"); rwBusy = false;
    });
  }

  /* ---------- languages ---------- */
  var words = ["नमस्ते", "Hello", "Kya haal hai", "Hola", "Bonjour", "こんにちは", "Hallo", "مرحبا", "Ciao"];
  var lw = $("#langWord");
  if (lw && !RM) {
    var li = 0;
    setInterval(function () {
      li = (li + 1) % words.length;
      gsap.timeline().to(lw, { yPercent: -40, opacity: 0, rotate: -4, filter: "blur(6px)", duration: 0.35, ease: "power2.in" })
        .call(function () { lw.textContent = words[li]; })
        .fromTo(lw, { yPercent: 40, rotate: 4 }, { yPercent: 0, opacity: 1, rotate: 0, filter: "blur(0px)", duration: 0.6, ease: "expo.out" });
    }, 2100);
  }
  if (lw && !RM) gsap.to(".r1", { rotate: 360, duration: 90, repeat: -1, ease: "none" });

  /* ---------- apps ---------- */
  var apps = [["Gmail", "#2e62ff"], ["WhatsApp Web", "#1f9d6b"], ["Notion", "#17130d"], ["ChatGPT", "#8f7cf0"], ["Slack", "#ffb000"], ["Word", "#2f6fed"], ["VS Code", "#2f6fed"], ["Chrome", "#2e62ff"], ["LinkedIn", "#2f6fed"], ["Teams", "#8f7cf0"], ["Google Docs", "#2f6fed"], ["Any text box", "#ffb000"]];
  var appsEl = $("#apps");
  if (appsEl) {
    apps.forEach(function (a) { var d = document.createElement("span"); d.className = "app"; d.style.setProperty("--c", a[1]); d.textContent = a[0]; appsEl.appendChild(d); });
    var tiles = $$(".app", appsEl);
    if (!RM) {
      gsap.set(tiles, { opacity: 0 });
      ScrollTrigger.create({ trigger: appsEl, start: "top 85%", once: true, onEnter: function () {
        gsap.fromTo(tiles, { y: function () { return gsap.utils.random(60, 140); }, x: function () { return gsap.utils.random(-80, 80); }, rotate: function () { return gsap.utils.random(-25, 25); }, opacity: 0 }, { y: 0, x: 0, rotate: 0, opacity: 1, duration: 1.1, stagger: { each: 0.06, from: "random" }, ease: "elastic.out(1,.7)" });
      } });
      var ai = 0; setInterval(function () { tiles.forEach(function (t) { t.classList.remove("lit"); }); tiles[ai % tiles.length].classList.add("lit"); ai++; }, 900);
    }
  }

  /* ---------- pill picker ---------- */
  var pick = $("#pick");
  if (pick) $$("button", pick).forEach(function (b) {
    b.addEventListener("click", function () {
      $$("button", pick).forEach(function (x) { x.setAttribute("aria-checked", x === b ? "true" : "false"); });
      document.documentElement.setAttribute("data-pill", b.getAttribute("data-style"));
      if (!RM) { gsap.fromTo(b, { scale: 0.88 }, { scale: 1, duration: 0.6, ease: "elastic.out(1,.5)" }); gsap.fromTo(".nav .brand img", { rotate: -20 }, { rotate: 0, duration: 0.8, ease: "elastic.out(1,.4)" }); }
    });
  });

  /* ---------- offline flow ---------- */
  if (!RM) {
    var glow = $(".flow-line .glow");
    if (glow) gsap.fromTo(glow, { strokeDashoffset: 0 }, { strokeDashoffset: -1000, duration: 3.2, ease: "none", repeat: -1 });
    gsap.from(".node", { y: 40, opacity: 0, duration: 0.9, stagger: 0.2, ease: "expo.out", scrollTrigger: { trigger: ".flow", start: "top 80%", once: true } });
  }

  /* ---------- final ---------- */
  var wm = $(".wordmark");
  if (wm && !RM) {
    gsap.fromTo(wm, { yPercent: 40 }, { yPercent: 18, ease: "none", scrollTrigger: { trigger: ".final", start: "top bottom", end: "bottom bottom", scrub: true } });
    if (fine) $(".final").addEventListener("pointermove", function (e) { gsap.to(wm, { x: (e.clientX / window.innerWidth - 0.5) * -40, duration: 1, ease: "power3.out" }); });
  }

  window.addEventListener("load", function () { ScrollTrigger.refresh(); });
})();
