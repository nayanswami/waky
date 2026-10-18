(function () {
  var cfg = window.WAKY || {};
  document.querySelectorAll(".js-sha").forEach(function (el) { if (cfg.sha256) el.textContent = cfg.sha256; });
  document.querySelectorAll(".js-repo").forEach(function (a) { if (cfg.repoUrl) a.href = cfg.repoUrl; });
  document.querySelectorAll(".js-download").forEach(function (a) {
    if (cfg.downloadUrl) { a.href = cfg.downloadUrl; a.setAttribute("download", ""); }
  });
})();
