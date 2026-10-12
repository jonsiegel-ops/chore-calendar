// Shared by every fridge page: night mode, full screen on tap, and the photo
// screensaver (only on pages whose <body> has data-screensaver).
// Plain ES2015 so it runs in older built-in browsers.
(function () {
  "use strict";

  var REFRESH_MS = 2 * 60 * 1000; // picks up settings changes within a couple of minutes
  var settings = null;
  var photos = [];
  var idleTimer = null;
  var saver = null; // screensaver state while it's showing

  function pad(n) { return n < 10 ? "0" + n : "" + n; }

  function load() {
    return fetch("/api/display", { cache: "no-store" }).then(function (res) {
      return res.ok ? res.json() : null;
    }).then(function (data) {
      if (!data) return;
      var first = !settings;
      settings = data.display;
      photos = data.photos;
      applyNight();
      if (first) resetIdle(); // later refreshes mustn't restart the idle countdown
    }, function () { /* try again at the next refresh */ });
  }

  // ---------- night mode ----------

  function isNight() {
    if (!settings || !settings.night_mode || settings.night_start === settings.night_end) return false;
    var now = new Date(), t = pad(now.getHours()) + ":" + pad(now.getMinutes());
    var start = settings.night_start, end = settings.night_end;
    return start < end ? (t >= start && t < end) : (t >= start || t < end);
  }

  function applyNight() {
    document.documentElement.classList.toggle("night", isNight());
  }

  // ---------- full screen ----------
  // Browsers only allow full screen right after a tap, and leaving the page
  // exits it, so we ask again on the next tap after each page load.

  function goFullscreen() {
    var el = document.documentElement;
    var request = el.requestFullscreen || el.webkitRequestFullscreen;
    var current = document.fullscreenElement || document.webkitFullscreenElement;
    // Only on big screens: on a phone, full screen would just get in the way.
    if (!settings || !settings.fullscreen || current || !request || window.innerWidth <= 700) return;
    try {
      var result = request.call(el);
      if (result && result.catch) result.catch(function () { /* not allowed here */ });
    } catch (e) { /* not supported */ }
  }

  // ---------- screensaver ----------

  function resetIdle() {
    clearTimeout(idleTimer);
    if (!settings || !settings.screensaver || !photos.length || saver) return;
    if (!document.body || !document.body.hasAttribute("data-screensaver")) return;
    idleTimer = setTimeout(startSaver, settings.screensaver_minutes * 60 * 1000);
  }

  function shuffled(list) {
    var a = list.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1)), t = a[i];
      a[i] = a[j];
      a[j] = t;
    }
    return a;
  }

  function startSaver() {
    var root = document.createElement("div");
    root.className = "saver";
    root.innerHTML = '<img class="saver-img" alt=""><img class="saver-img" alt="">' +
      '<div class="saver-clock"><div class="saver-time"></div><div class="saver-date"></div></div>';
    document.body.appendChild(root);
    saver = { root: root, imgs: root.querySelectorAll(".saver-img"), front: 0, queue: [], timer: null, clock: null };

    // Swallow the tap that wakes the screen so it doesn't also tick off a chore.
    root.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); stopSaver(); }, true);

    tickSaverClock();
    saver.clock = setInterval(tickSaverClock, 1000);
    nextPhoto();
    saver.timer = setInterval(nextPhoto, settings.photo_seconds * 1000);
  }

  function nextPhoto() {
    if (!saver) return;
    if (!saver.queue.length) saver.queue = shuffled(photos);
    var name = saver.queue.pop();
    var back = saver.imgs[1 - saver.front];
    back.onload = function () {
      if (!saver) return;
      back.classList.add("shown");
      saver.imgs[saver.front].classList.remove("shown");
      saver.front = 1 - saver.front;
    };
    back.src = "/photos/" + encodeURIComponent(name);
  }

  function tickSaverClock() {
    if (!saver) return;
    var now = new Date(), h = now.getHours();
    var days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
    var months = ["January", "February", "March", "April", "May", "June", "July",
      "August", "September", "October", "November", "December"];
    saver.root.querySelector(".saver-time").textContent = ((h + 11) % 12 + 1) + ":" + pad(now.getMinutes());
    saver.root.querySelector(".saver-date").textContent =
      days[now.getDay()] + ", " + months[now.getMonth()] + " " + now.getDate();
  }

  function stopSaver() {
    if (!saver) return;
    clearInterval(saver.timer);
    clearInterval(saver.clock);
    saver.root.parentNode.removeChild(saver.root);
    saver = null;
    resetIdle();
  }

  // ---------- wiring ----------

  ["touchstart", "mousedown", "keydown", "scroll"].forEach(function (ev) {
    document.addEventListener(ev, resetIdle, true);
  });
  document.addEventListener("click", goFullscreen, true);

  applyNight();
  load();
  setInterval(applyNight, 30 * 1000);
  setInterval(load, REFRESH_MS);
})();
