/* Waky FX v9: self-running "How it works" loop and the key-features theatre. No scroll or click needed. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var reduce = /[?&]still/.test(location.search);
  var clamp = function (v, a, b) { return v < a ? a : v > b ? b : v; };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var esc = function (s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); };
  var GL = "01#%&*+=?/<>[]{}";
  function watch(el) { var on = false; if ("IntersectionObserver" in window) new IntersectionObserver(function (es) { on = es[0].isIntersecting; }, { threshold: .15 }).observe(el); else on = true; return function () { return on; }; }

  /* ---------------- HOW IT WORKS ---------------- */
  (function how() {
    var sec = $("#how"); if (!sec) return;
    var RAW = "um tell Maya I’ll send the deck uh tomorrow morning", OUT = "Hi Maya,\n\nI’ll send the deck over tomorrow morning.\n\nBest, Nayan";
    var DUR = [2600, 4000, 3200, 3800], TOT = DUR.reduce(function (a, b) { return a + b; }, 0);
    var steps = $$(".hw-s", sec), wave = $("#hwWave"), raw = $("#hwRaw"), mid = $("#hwMid"), out = $("#hwOut"), pl = $("#hwPL"), chip = $("#hwChip"), track = $("#hwTrack");
    var idx = -1, t0 = performance.now(), vis = false, G = " .:-=+*#%@";
    function morph(a, b, q) { var L = Math.max(a.length, b.length), o = "", k = q * L; for (var i = 0; i < L; i++) { if (i < k) o += b[i] || ""; else { var ch = a[i] || ""; o += ch && ch !== " " && Math.random() < .45 ? GL[(Math.random() * GL.length) | 0] : ch; } } return o; }
    function marked() { return RAW.replace(/\b(um|uh)\b/g, '<s class="f">$1</s>'); }
    function render(now) {
      var el = (now - t0) % TOT, i = 0, acc = 0; while (i < 3 && el >= acc + DUR[i]) { acc += DUR[i]; i++; }
      var q = clamp((el - acc) / DUR[i], 0, 1);
      track.style.setProperty("--p", (el / TOT).toFixed(4));
      if (i !== idx) {
        idx = i; sec.setAttribute("data-st", i);
        steps.forEach(function (s, k) { s.classList.toggle("on", k === i); s.classList.toggle("past", k < i); });
        pl.textContent = ["Listening", "Listening", "Writing…", "Pasted"][i];
        chip.classList.toggle("show", i >= 2);
      }
      var t = now / 150, o = "", amp = i < 2 ? 1 : 0;
      for (var x = 0; x < 34; x++) { var v = amp * (.5 + .5 * Math.sin(x * .6 + t * 2.2)) * (.3 + .7 * Math.abs(Math.sin(x * .19 - t * .9))); if (i === 0) v *= clamp(q * 3, 0, 1); o += G[Math.min(9, Math.floor(v * 10))]; }
      wave.textContent = i < 2 ? o : ".".repeat(34);
      raw.textContent = i === 1 ? RAW.slice(0, Math.ceil(clamp(q * 1.15, 0, 1) * RAW.length)) : i === 0 ? "" : RAW;
      raw.style.opacity = i === 1 ? 1 : .35;
      if (i < 2) mid.innerHTML = '<span class="dim">waiting for speech…</span>';
      else if (i === 2) mid.innerHTML = q < .35 ? marked() : esc(morph(RAW, "Hi Maya, I’ll send the deck over tomorrow morning.", clamp((q - .35) / .55, 0, 1)));
      else mid.innerHTML = "Hi Maya, I’ll send the deck over tomorrow morning.";
      out.innerHTML = i < 3 ? '<span class="dim">…</span>' : esc(OUT.slice(0, Math.ceil(clamp(q * 2.4, 0, 1) * OUT.length))) + (q < .5 ? '<span class="caret"></span>' : "");
    }
    function loop(now) { if (vis) render(now); setTimeout(function () { requestAnimationFrame(loop); }, 70); }
    if (reduce) { t0 = performance.now() - (DUR[0] + DUR[1] + DUR[2] + 2200); render(performance.now()); return; }
    if ("IntersectionObserver" in window) new IntersectionObserver(function (es) { var v = es[0].isIntersecting; if (v && !vis) t0 = performance.now(); vis = v; }, { threshold: .2 }).observe(sec); else vis = true;
    requestAnimationFrame(loop);
  })();

  /* ---------------- FEATURES THEATRE ---------------- */
  (function features() {
    var list = $("#ftList"), stage = $("#ftStage"); if (!list || !stage) return;
    var F = [
      { k: "Clean text", d: "Fillers, false starts and wrong words are removed. What is left sounds like you.", p: [["clean-up on", "um so tell Maya I’ll uh send the deck like tomorrow", "Tell Maya I’ll send the deck tomorrow."], ["clean-up on", "i think we should uh maybe move the call to thursday", "I think we should move the call to Thursday."]] },
      { k: "Spoken modes", d: "Say the shape you want. Email, bullets, a prompt, a shorter version.", p: [["mode: write email", "write email ask Maya for the final copy", "Hi Maya,\n\nCould you send the final copy when you can?\n\nThanks, Nayan"], ["mode: bullet points", "bullet points update the page ask for copy share the preview", "• Update the page\n• Ask for the copy\n• Share the preview"], ["mode: make it shorter", "make it shorter we should probably think about pushing the launch back a bit", "Let’s push the launch."]] },
      { k: "Hinglish to English", d: "Speak Hindi and English in one breath. The text comes out in clean English.", p: [["hindi + english", "kal tak bhej dunga bas final feedback chahiye", "I’ll send it by tomorrow. I just need the final feedback."], ["hindi + english", "thoda time chahiye meeting shuru karte hain", "I need a little more time. Let’s start the meeting."]] },
      { k: "Snippets", d: "Say a short phrase, get the long thing. Emails, links, addresses.", p: [["snippet: my email", "send it to my email", "Send it to your.email@example.com"], ["snippet: my portfolio", "here is my portfolio", "Here is your-portfolio.example.com"]] },
      { k: "Per-app profiles", d: "The same sentence, written for where you are typing.", p: [["app: Slack", "can you send the deck tomorrow", "can you send the deck tomorrow?"], ["app: Outlook", "can you send the deck tomorrow", "Could you please send the deck by tomorrow morning? Thank you."], ["app: VS Code", "can you send the deck tomorrow", "// TODO: send the deck tomorrow"]] },
      { k: "Rewrite a selection", d: "Select text, hold the key, say what to change. It is replaced in place.", p: [["selection: 1 paragraph", "[I think we maybe should push the launch back a little] make it shorter", "Let’s push the launch."], ["selection: 1 sentence", "[send the thing] make it more formal", "Please send the document at your earliest convenience."]] },
      { k: "Local or cloud", d: "Groq with your own key, or Whisper entirely on your PC. No audio is ever saved.", p: [["route: groq, your key", "any sentence you say out loud", "Sent to Groq with your key. Nothing is stored."], ["route: local whisper", "any sentence you say out loud", "Transcribed on this PC. Speech never leaves it."]] }
    ];
    var ctx = $("#ftCtx"), idxE = $("#ftIdx"), inE = $("#ftIn"), outE = $("#ftOut"), on = watch(stage), cur = -1, tok = { dead: false }, hold = 0;
    F.forEach(function (f, i) {
      var li = document.createElement("li"), tot = f.p.length * 4.6;
      li.innerHTML = '<button type="button"><b>0' + (i + 1) + '</b><strong>' + f.k + '</strong><span class="d">' + f.d + '</span></button>'; li.style.setProperty("--dur", tot + "s");
      var bt = li.querySelector("button"); bt.addEventListener("click", function () { hold = Date.now() + 9000; go(i); }); bt.addEventListener("pointerenter", function (e) { if (e.pointerType === "mouse" && cur !== i) { hold = Date.now() + 9000; go(i); } });
      list.appendChild(li);
    });
    var lis = $$("li", list);
    function type(el, text, ms, t) { return new Promise(function (res) { var i = 0; (function f() { if (t.dead) return res(); i = Math.min(text.length, i + 1); el.textContent = text.slice(0, i); if (i < text.length) setTimeout(f, ms); else res(); })(); }); }
    async function go(i) {
      tok.dead = true; var t = tok = { dead: false }; cur = i;
      lis.forEach(function (l, k) { l.classList.remove("on"); if (k === i) { void l.offsetWidth; l.classList.add("on"); } });
      idxE.textContent = "0" + (i + 1) + " / 0" + F.length;
      for (var n = 0; n < F[i].p.length; n++) {
        var p = F[i].p[n]; ctx.textContent = p[0]; inE.textContent = ""; outE.textContent = ""; stage.classList.remove("done");
        await type(inE, p[1], 20, t); if (t.dead) return; await sleep(380); if (t.dead) return;
        stage.classList.add("done"); await type(outE, p[2], 13, t); if (t.dead) return; await sleep(1900); if (t.dead) return;
        while (!on()) { await sleep(400); if (t.dead) return; }
      }
      if (t.dead) return; if (Date.now() < hold) { go(i); return; } go((i + 1) % F.length);
    }
    if (reduce) { lis[0].classList.add("on"); ctx.textContent = F[0].p[0][0]; inE.textContent = F[0].p[0][1]; outE.textContent = F[0].p[0][2]; stage.classList.add("done"); return; }
    (async function boot() { while (!on()) await sleep(300); go(0); })();
  })();

  /* ---------------- CLOSING TERMINAL ---------------- */
  (function term() {
    var out = $("#ctOut"); if (!out) return;
    var on = watch(out), buf = [], cur = "", W8 = " .:-=+*#%@";
    function render() { out.innerHTML = buf.join("\n") + (buf.length ? "\n" : "") + cur + '<span class="caret"></span>'; }
    async function typeLine(pre, text, cls, ms) { cur = pre; for (var i = 1; i <= text.length; i++) { cur = pre + (cls ? '<span class="' + cls + '">' : "") + esc(text.slice(0, i)) + (cls ? "</span>" : ""); render(); await sleep(ms); } buf.push(cur); cur = ""; render(); }
    async function wave(ms) { var t0 = Date.now(); while (Date.now() - t0 < ms) { var s = ""; for (var x = 0; x < 28; x++) s += W8[Math.min(9, Math.floor((.5 + .5 * Math.sin(x * .6 + Date.now() / 90)) * (.3 + .7 * Math.abs(Math.sin(x * .2 - Date.now() / 200))) * 10))]; cur = '<span class="g">● listening</span>  <span class="w">' + s + "</span>"; render(); await sleep(70); } buf.push('<span class="g">● listening</span>  <span class="d">' + ".".repeat(28) + "</span>"); cur = ""; render(); }
    async function run() {
      while (true) {
        while (!on()) await sleep(400);
        buf = []; cur = ""; render();
        await typeLine('<span class="d">$ </span>', "hold ctrl + win", "w", 55); await sleep(250);
        await wave(1800);
        await typeLine('<span class="d">you   › </span>', "um tell Maya I’ll send the deck uh tomorrow morning", "", 26); await sleep(500);
        await typeLine('<span class="d">waky  › </span>', "cleaning…", "d", 40); await sleep(500);
        buf.push('<span class="g">✓ pasted</span>'); render(); await sleep(250);
        await typeLine("", "Hi Maya,", "w", 30); await typeLine("", "I’ll send the deck over tomorrow morning.", "w", 18); await typeLine("", "Best, Nayan", "w", 30);
        await sleep(300); buf.push('<span class="d">enter not pressed · 0 audio saved</span>'); render(); await sleep(4200);
      }
    }
    if (reduce) { buf = ['<span class="d">$ </span><span class="w">hold ctrl + win</span>', '<span class="g">✓ pasted</span>', "Hi Maya,", "I’ll send the deck over tomorrow morning.", "Best, Nayan"]; render(); return; }
    run();
  })();

  /* ---------------- SPEED RACE ---------------- */
  (function speed() {
    var K = $("#spK"), Wk = $("#spW"); if (!K) return; var on = watch(K), S = "Tell Maya I’ll send the deck over tomorrow morning and ask for the final copy.";
    var kb = $("#spKb"), wb = $("#spWb"), kw = $("#spKw"), ww = $("#spWw");
    if (reduce) { K.textContent = S.slice(0, 20); Wk.textContent = S; kb.style.width = "22%"; wb.style.width = "75%"; kw.textContent = "45 wpm"; ww.textContent = "160 wpm"; return; }
    (async function () { while (true) { while (!on()) await sleep(400);
      K.textContent = ""; Wk.textContent = ""; kb.style.cssText = "width:0;transition:none"; wb.style.cssText = "width:0;transition:none"; kw.textContent = "0 wpm"; ww.textContent = "0 wpm"; await sleep(500);
      var t0 = Date.now(), T = 6500;
      kb.style.cssText = "width:22%;transition:width " + T + "ms linear"; wb.style.cssText = "width:75%;transition:width 1700ms cubic-bezier(.2,.8,.2,1)";
      while (Date.now() - t0 < T) { var e = Date.now() - t0; K.textContent = S.slice(0, Math.floor(e / 95)); Wk.textContent = S.slice(0, Math.min(S.length, Math.floor(Math.max(0, e - 200) / 22)));
        kw.textContent = Math.round(Math.min(1, e / T) * 45) + " wpm"; ww.textContent = Math.round(Math.min(1, e / 1700) * 160) + " wpm"; await sleep(50); }
      await sleep(2600); } })();
  })();

  /* ---------------- TONE + VOCABULARY ---------------- */
  (function tone() {
    var tabs = $$("#tvTabs button"), out = $("#tvOut"); if (!out) return; var on = watch(out), T = ["Hi Maya,\n\nI will send you the deck tomorrow.\n\nKind regards, Nayan", "Hey Maya, I’ll send the deck tomorrow!", "maya, deck coming tmrw"], cur = -1, tok = { dead: false }, hold = 0;
    function type(el, text, ms, t) { return new Promise(function (res) { var i = 0; (function f() { if (t.dead) return res(); i = Math.min(text.length, i + 1); el.textContent = text.slice(0, i); if (i < text.length) setTimeout(f, ms); else res(); })(); }); }
    function set(i) { tok.dead = true; var t = tok = { dead: false }; cur = i; tabs.forEach(function (b, k) { b.classList.toggle("on", k === i); }); type(out, T[i], 16, t); }
    tabs.forEach(function (b, i) { b.addEventListener("click", function () { hold = Date.now() + 8000; set(i); }); b.addEventListener("pointerenter", function (e) { if (e.pointerType === "mouse" && cur !== i) { hold = Date.now() + 8000; set(i); } }); });
    set(0); if (!reduce) setInterval(function () { if (on() && Date.now() > hold) set((cur + 1) % 3); }, 3800);
    var vo = $("#vcOut"), tag = $("#vcTag"), btn = $("#vcBtn"), heard = $("#vcHeard"), von = watch(vo);
    var N = [["Aditee", "Aditya", "ask Aditee about the report"], ["Sarah", "Sara", "send it to Sarah"]];
    if (reduce) { vo.textContent = "Ask Aditya about the report."; return; }
    (async function () { var n = 0; while (true) { while (!von()) await sleep(400); var p = N[n++ % N.length];
      $(".vc-f b").textContent = p[0]; $("#vcTo").textContent = p[1]; heard.textContent = p[2]; vo.textContent = ""; tag.textContent = "Learning…"; tag.classList.remove("ok"); btn.classList.remove("dn"); await sleep(1400);
      btn.classList.add("dn"); await sleep(250); btn.classList.remove("dn"); tag.textContent = "Added"; tag.classList.add("ok");
      var fix = p[2].replace(p[0], p[1]); fix = fix.charAt(0).toUpperCase() + fix.slice(1) + "."; await type(vo, fix, 22, { dead: false }); await sleep(2800); } })();
  })();
})();
