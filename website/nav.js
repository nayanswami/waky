/* Header: full-width at the top, condenses into a floating pill once you scroll, with a dithered read-progress line. */
(function () {
  var h = document.querySelector(".header"); if (!h) return;
  var ticking = false, lastY = 0;
  function frame() {
    ticking = false;
    var y = window.scrollY || 0, d = document.documentElement, max = Math.max(1, d.scrollHeight - innerHeight);
    document.body.classList.toggle("scrolled", y > 28);
    h.style.setProperty("--p", Math.min(1, y / max).toFixed(4));
    lastY = y;
  }
  addEventListener("scroll", function () { if (!ticking) { ticking = true; requestAnimationFrame(frame); } }, { passive: true });
  frame();
  /* mark the current section in the nav on the landing page */
  var links = [].slice.call(document.querySelectorAll("#site-nav a")), map = {};
  links.forEach(function (a) { var m = (a.getAttribute("href") || "").match(/^#(.+)/); if (m) map[m[1]] = a; });
  if ("IntersectionObserver" in window && Object.keys(map).length) {
    var io = new IntersectionObserver(function (es) { es.forEach(function (e) { var a = map[e.target.id]; if (a) a.classList.toggle("here", e.isIntersecting); }); }, { rootMargin: "-40% 0px -50% 0px" });
    Object.keys(map).forEach(function (id) { var s = document.getElementById(id); if (s) io.observe(s); });
  }
})();
