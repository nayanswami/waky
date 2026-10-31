(function () {
  var cfg = window.WAKY || {}, $ = function (s) { return document.querySelector(s); };
  document.querySelectorAll(".js-download").forEach(function (a) { if (cfg.downloadUrl) { a.href = cfg.downloadUrl; a.setAttribute("download", ""); } });
  document.querySelectorAll(".js-repo").forEach(function (a) { if (cfg.repoUrl) a.href = cfg.repoUrl; });
  document.querySelectorAll(".js-version").forEach(function (a) { if (cfg.version) a.textContent = "V" + cfg.version; });
  document.querySelectorAll(".js-size").forEach(function (a) { if (cfg.size) a.textContent = cfg.size; });
  document.querySelectorAll(".js-sha").forEach(function (a) { if (cfg.sha256) a.textContent = cfg.sha256; });
  var body = document.body, burger = $(".burger");
  function set(o) { body.classList.toggle("menu-open", o); burger.setAttribute("aria-expanded", o); burger.setAttribute("aria-label", o ? "Close menu" : "Open menu"); }
  burger.addEventListener("click", function () { set(!body.classList.contains("menu-open")); });
  document.querySelectorAll("#site-nav a").forEach(function (a) { a.addEventListener("click", function () { set(false); }); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") set(false); });
  matchMedia("(min-width: 901px)").addEventListener("change", function (m) { if (m.matches) set(false); });
  var band = $("#band"); if (band) new BitmapField(band, { mode: "band", px: 4, host: band.parentNode, dim: function (u, v) { var dx = (u - .5) / .4, dy = (v - .52) / .5, r = Math.sqrt(dx * dx + dy * dy); return .12 + .88 * Math.min(1, Math.max(0, (r - .3) / .7)); } });
  var led = $("#led"); if (led) { var go = function () { new BitmapField(led, { mode: "text", text: "$0", px: 6, host: led, radius: .16 }); }; if (document.fonts && document.fonts.load) document.fonts.load("700 100px Inter").then(go); else go(); }
})();
