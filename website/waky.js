(function () {
  "use strict";
  var config = window.WAKY || {};
  var $ = function (selector, root) { return (root || document).querySelector(selector); };
  var $$ = function (selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); };

  $$(".js-version").forEach(function (el) { if (config.version) el.textContent = "V" + config.version; });
  $$(".js-repo").forEach(function (el) { if (config.repoUrl) el.href = config.repoUrl; });
  $$ ("[data-download]").forEach(function (el) { if (config.downloadUrl) { el.href = config.downloadUrl; el.setAttribute("download", ""); } });
  $$(".js-sha").forEach(function (el) { if (config.sha256) el.textContent = config.sha256; });

  var hero = $(".hero-sheet");
  if (hero) requestAnimationFrame(function () { hero.classList.add("is-ready"); });

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var revealItems = $$(".reveal");
  if (reduceMotion || !("IntersectionObserver" in window)) {
    revealItems.forEach(function (el) { el.classList.add("is-visible"); });
  } else {
    var revealObserver = new IntersectionObserver(function (entries, observer) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -32px 0px" });
    revealItems.forEach(function (el) { revealObserver.observe(el); });
  }

  var scenarios = {
    email: {
      label: "Email", title: "Subject: About tomorrow’s exam",
      said: "um tell sir I can't come to the exam tomorrow because I feel sick can you make this sound professional",
      output: "Dear Sir,\n\nI’m feeling unwell and won’t be able to attend tomorrow’s exam. Please let me know what options are available.\n\nThank you for your understanding.",
      badge: "No filler words"
    },
    notes: {
      label: "Notes", title: "Friday launch", said: "okay for Friday we need to update the product page ask Maya for final copy and send the preview to the team",
      output: "• Update the product page\n• Ask Maya for the final copy\n• Send the preview to the team", badge: "3 ideas grouped"
    },
    hinglish: {
      label: "Hinglish", title: "A quick update", said: "kal tak bhej dunga, just need Maya's final feedback first",
      output: "I’ll send it by tomorrow. I just need Maya’s final feedback first.", badge: "Meaning kept intact"
    },
    prompt: {
      label: "Prompt", title: "Product launch brief", said: "help me make a prompt for a product designer to write a launch brief make it short and include who it's for and the format",
      output: "Act as a product designer. Write a concise launch brief for the intended audience. Include the product’s value, audience, and a clear format with short sections.", badge: "Prompt shaped"
    }
  };
  var demo = $("#demo"), record = $("#recordButton"), stateText = $("#demoState");
  var saidText = $("#demoSaid"), output = $("#demoOutput"), title = $("#demoTitle"), badge = $("#demoBadge"), appName = $("#demoAppName");
  var wave = $("#demoWave"), busy = false, activeScenario = "email", finishTimer = 0, resetTimer = 0;

  function writeScenario(key) {
    var scenario = scenarios[key];
    if (!scenario || !demo) return;
    activeScenario = key;
    saidText.textContent = scenario.said;
    title.textContent = scenario.title;
    output.innerHTML = scenario.output.split("\n").map(function (line) { return line ? line.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;") : "&nbsp;"; }).join("<br>");
    badge.textContent = scenario.badge;
    appName.textContent = scenario.label;
    $$(".scenario-tab").forEach(function (tab) {
      var selected = tab.getAttribute("data-scenario") === key;
      tab.classList.toggle("is-active", selected);
      tab.setAttribute("aria-selected", selected ? "true" : "false");
    });
  }
  function startDemo() {
    if (!demo || busy) return;
    clearTimeout(finishTimer); clearTimeout(resetTimer); busy = true;
    demo.classList.remove("is-processing", "is-complete");
    demo.classList.add("is-listening");
    record.classList.remove("is-processing"); record.classList.add("is-listening");
    wave.classList.add("is-listening");
    stateText.textContent = "Listening to your thought";
  }
  function finishDemo() {
    if (!demo || !busy || demo.classList.contains("is-processing")) return;
    demo.classList.remove("is-listening"); demo.classList.add("is-processing");
    record.classList.remove("is-listening"); record.classList.add("is-processing");
    wave.classList.remove("is-listening"); stateText.textContent = "Shaping the words";
    finishTimer = setTimeout(function () {
      writeScenario(activeScenario);
      demo.classList.remove("is-processing"); demo.classList.add("is-complete");
      record.classList.remove("is-processing");
      stateText.textContent = "Ready to paste";
      busy = false;
      resetTimer = setTimeout(function () {
        demo.classList.remove("is-complete");
        stateText.textContent = "Ready when you are";
      }, 1800);
    }, 630);
  }
  function runTappedDemo() {
    if (busy) return;
    startDemo();
    finishTimer = setTimeout(finishDemo, 1000);
  }
  if (demo && record) {
    writeScenario(activeScenario);
    record.addEventListener("pointerdown", function (event) { if (event.button === 0) startDemo(); });
    record.addEventListener("pointerup", finishDemo);
    record.addEventListener("pointercancel", finishDemo);
    record.addEventListener("click", function (event) {
      if (event.detail === 0 || !busy) runTappedDemo();
    });
    $$(".scenario-tab").forEach(function (tab) {
      tab.addEventListener("click", function () { if (!busy) writeScenario(tab.getAttribute("data-scenario")); });
      tab.addEventListener("keydown", function (event) {
        if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
        event.preventDefault();
        var tabs = $$(".scenario-tab"), index = tabs.indexOf(tab), next = (index + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length;
        tabs[next].focus(); tabs[next].click();
      });
    });
    $$("[data-pick]").forEach(function (button) {
      button.addEventListener("click", function () {
        var target = button.getAttribute("data-pick");
        writeScenario(target);
        $("#studio").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
      });
    });
    document.addEventListener("keydown", function (event) {
      if (event.code !== "Space" || event.repeat) return;
      var target = event.target;
      if (target && (/INPUT|TEXTAREA|BUTTON|A/.test(target.tagName) || target.isContentEditable)) return;
      var rect = demo.getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > window.innerHeight) return;
      event.preventDefault(); startDemo();
    });
    document.addEventListener("keyup", function (event) { if (event.code === "Space" && busy) finishDemo(); });
  }
})();
