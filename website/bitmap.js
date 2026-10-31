/* Waky bitmap: light 1-bit ordered-dither renderer (Bayer 8x8). White dots on transparent. Used for page bands and the $0. */
(function () {
  "use strict";
  var reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var BAYER = (function () {
    var m = [[0, 2], [3, 1]], n = 2;
    while (n < 8) { var o = []; for (var y = 0; y < n * 2; y++) { o.push([]); for (var x = 0; x < n * 2; x++) o[y].push(m[y % n][x % n] * 4 + [[0, 2], [3, 1]][Math.floor(y / n)][Math.floor(x / n)]); } m = o; n *= 2; }
    var f = new Float32Array(64); for (var i = 0; i < 64; i++) f[i] = (m[i >> 3][i & 7] + .5) / 64; return f;
  })();
  var bump = function (d) { d = 1 - d * d; return d > 0 ? d * d : 0; }; // cheap smooth bump, no exp()

  /* mode: "band" (calm ribbon header) or "text" (dithered word the cursor pushes) */
  window.BitmapField = function (cv, o) {
    o = o || {}; var mode = o.mode || "band", px = o.px || 4, c = cv.getContext("2d"), w = 0, h = 0, img, buf, off = null;
    var P = { x: -99, y: -99, tx: -99, ty: -99, a: 0, on: false }, vis = true, raf = 0, last = 0, host = o.host || cv.parentNode, ys = [new Float32Array(1), new Float32Array(1), new Float32Array(1)];
    function size() {
      var r = cv.getBoundingClientRect(); w = Math.max(8, Math.ceil(r.width / px)); h = Math.max(8, Math.ceil(r.height / px));
      cv.width = w; cv.height = h; img = c.createImageData(w, h); buf = new Uint32Array(img.data.buffer); ys = [new Float32Array(w), new Float32Array(w), new Float32Array(w)];
      if (mode === "text") {
        var m = document.createElement("canvas"); m.width = w; m.height = h; var g = m.getContext("2d", { willReadFrequently: true });
        g.fillStyle = "#fff"; g.textAlign = "center"; var fs = Math.min(h * 1.05, w / 1.1); g.font = "700 " + fs + "px Inter, system-ui, sans-serif"; g.fillText(o.text || "$0", w / 2, h / 2 + fs * .34);
        var d = g.getImageData(0, 0, w, h).data; off = new Float32Array(w * h); for (var i = 0; i < off.length; i++) off[i] = d[i * 4 + 3] / 255;
      }
    }
    var ON = 0xFFEEEEEE;
    function draw(now) {
      var t = now / 1000; P.x += (P.tx - P.x) * .2; P.y += (P.ty - P.y) * .2; P.a += ((P.on ? 1 : 0) - P.a) * .12;
      var R = (o.radius || .14) * Math.max(w, h), R2 = R * R, pa = P.a;
      if (mode === "band") {
        for (var k = 0; k < 3; k++) for (var x = 0; x < w; x++) {
          var u = x / w, env = Math.sin(Math.PI * u), y0 = .55 + .13 * Math.sin(u * 6.283 * (1 + .35 * k) - t * (.55 + .2 * k) + k * 2) * (.35 + .65 * env);
          if (pa > .01) { var q = (x - P.x) / (w * .22); y0 += (P.y / h - y0) * .22 * pa * bump(q); }
          ys[k][x] = y0;
        }
      }
      for (var y = 0; y < h; y++) {
        var v = y / h, row = (y & 7) * 8;
        for (var x2 = 0; x2 < w; x2++) {
          var val = 0;
          if (mode === "band") {
            var u2 = x2 / w; for (var j = 0; j < 3; j++) val += bump((v - ys[j][x2]) / (.1 + .04 * j)) * (1 - .26 * j);
            val *= (.55 + .45 * Math.sin(Math.PI * u2)) * (.75 + .25 * Math.sin(u2 * 40 + t * 1.5 + v * 18));
          } else { val = off[y * w + x2] * (.55 + .4 * (1 - v)); }
          if (pa > .01) { var dx = x2 - P.x, dy = y - P.y, dd = (dx * dx + dy * dy) / R2; if (dd < 1) val += (mode === "text" ? .5 : .9) * bump(Math.sqrt(dd)) * pa; }
          if (o.dim) val *= o.dim(x2 / w, v);
          buf[y * w + x2] = val > BAYER[row + (x2 & 7)] ? ON : 0;
        }
      }
      c.putImageData(img, 0, 0);
    }
    function loop(now) { if (now - last > 40) { last = now; draw(now); } raf = vis && !reduce ? requestAnimationFrame(loop) : 0; }
    function kick() { if (!raf) raf = requestAnimationFrame(loop); }
    size(); draw(o.still || 4000); if (!reduce) kick();
    var rt; addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { size(); draw(performance.now()); }, 150); });
    if ("IntersectionObserver" in window) new IntersectionObserver(function (es) { vis = es[0].isIntersecting; if (vis) kick(); }).observe(cv);
    document.addEventListener("visibilitychange", function () { vis = !document.hidden; if (vis) kick(); });
    host.addEventListener("pointermove", function (e) { var r = cv.getBoundingClientRect(); P.tx = (e.clientX - r.left) / px; P.ty = (e.clientY - r.top) / px; if (!P.on) { P.x = P.tx; P.y = P.ty; } P.on = e.pointerType !== "touch"; });
    host.addEventListener("pointerleave", function () { P.on = false; });
  };
})();
