// Fridge display. Plain ES2015 so it runs in older built-in browsers.
(function () {
  "use strict";

  var POLL_MS = 20000;
  var CALENDAR_MS = 5 * 60 * 1000;
  var board = null;
  var busy = {};
  var loadedAt = Date.now();

  var $board = document.getElementById("board");
  var $title = document.getElementById("title");
  var $day = document.getElementById("day");
  var $clock = document.getElementById("clock");
  var $offline = document.getElementById("offline");
  var $confetti = document.getElementById("confetti");
  var $todayCal = document.getElementById("today-cal");
  var $todayEvents = document.getElementById("today-events");
  var todayEvents = null;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function allDone(kid) {
    return kid.chores.length > 0 && kid.chores.every(function (c) { return c.done; });
  }

  function render() {
    $title.textContent = board.title;
    document.title = board.title;
    $day.textContent = board.weekday;
    $board.innerHTML = "";

    if (!board.kids.length) {
      var setup = el("div", "setup");
      setup.appendChild(document.createTextNode("No kids set up yet. Open "));
      var link = el("a", null, "settings");
      link.href = "/admin";
      setup.appendChild(link);
      setup.appendChild(document.createTextNode(" to add some."));
      $board.appendChild(setup);
      return;
    }

    board.kids.forEach(function (kid) {
      var col = el("section", "kid");
      col.style.setProperty("--kid", kid.color);

      var head = el("div", "kid-head");
      head.appendChild(el("div", "avatar", kid.emoji));
      head.appendChild(el("div", "kid-name", kid.name));
      head.appendChild(el("div", "stars", "⭐ " + kid.stars_week));
      col.appendChild(head);

      var doneCount = kid.chores.filter(function (c) { return c.done; }).length;
      var bar = el("div", "progress");
      var fill = el("span");
      fill.style.width = kid.chores.length ? (100 * doneCount / kid.chores.length) + "%" : "0";
      bar.appendChild(fill);
      col.appendChild(bar);

      var list = el("div", "chores");
      if (!kid.chores.length) list.appendChild(el("div", "empty", "No chores today 🎈"));

      kid.chores.forEach(function (chore) {
        var key = kid.id + "/" + chore.id;
        var btn = el("button", "chore" + (chore.done ? " done" : "") + (busy[key] ? " busy" : ""));
        btn.type = "button";
        btn.appendChild(el("span", "icon", chore.emoji));
        btn.appendChild(el("span", "label", chore.title));
        if (chore.stars > 1) btn.appendChild(el("span", "pts", "⭐×" + chore.stars));
        btn.appendChild(el("span", "check", "✓"));
        btn.addEventListener("click", function () { toggle(kid, chore, key); });
        list.appendChild(btn);
      });
      col.appendChild(list);

      if (allDone(kid)) col.appendChild(el("div", "all-done", "All done! 🎉"));
      $board.appendChild(col);
    });
  }

  function api(method, path, body) {
    return fetch(path, {
      method: method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store"
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw new Error(data.error || res.statusText);
        return data;
      });
    });
  }

  function online(ok) { $offline.hidden = ok; }

  function refresh() {
    if (Object.keys(busy).length) return Promise.resolve();
    return api("GET", "/api/board").then(function (data) {
      board = data;
      online(true);
      render();
    }, function () { online(false); });
  }

  function toggle(kid, chore, key) {
    if (busy[key]) return;
    var wasDone = allDone(kid);
    busy[key] = true;
    chore.done = !chore.done; // optimistic
    render();

    api("POST", "/api/toggle", { kid: kid.id, chore: chore.id }).then(function (data) {
      delete busy[key];
      board = data;
      online(true);
      render();
      var after = board.kids.filter(function (k) { return k.id === kid.id; })[0];
      var btn = findButton(kid.id, chore.id);
      if (btn && btn.classList.contains("done")) btn.classList.add("pop");
      if (after && !wasDone && allDone(after)) celebrate(after.color);
    }, function () {
      delete busy[key];
      online(false);
      refresh();
    });
  }

  function findButton(kidId, choreId) {
    var k = board.kids.map(function (x) { return x.id; }).indexOf(kidId);
    if (k < 0) return null;
    var c = board.kids[k].chores.map(function (x) { return x.id; }).indexOf(choreId);
    var col = $board.children[k];
    return col ? col.querySelectorAll(".chore")[c] : null;
  }

  function celebrate(color) {
    var colors = [color, "#ffd23f", "#ff6b9a", "#3ec1ff", "#7ed957"];
    for (var i = 0; i < 90; i++) {
      var p = document.createElement("i");
      p.style.left = Math.random() * 100 + "vw";
      p.style.background = colors[i % colors.length];
      p.style.animationDuration = 1.8 + Math.random() * 1.8 + "s";
      p.style.animationDelay = Math.random() * 0.5 + "s";
      p.style.transform = "rotate(" + Math.random() * 360 + "deg)";
      $confetti.appendChild(p);
    }
    setTimeout(function () { $confetti.innerHTML = ""; }, 4500);
  }

  function pad(n) { return n < 10 ? "0" + n : "" + n; }

  // ---------- today's calendar events ----------

  function time12(hhmm) {
    var p = hhmm.split(":"), h = +p[0];
    return ((h + 11) % 12 + 1) + (p[1] === "00" ? "" : ":" + p[1]) + (h < 12 ? " am" : " pm");
  }

  function eventLabel(ev) {
    if (ev.all_day) return "All day";
    if (!ev.start) return "until " + time12(ev.end);
    return time12(ev.start) + (ev.end ? " – " + time12(ev.end) : "");
  }

  function renderToday() {
    if (!todayEvents) return;
    var now = new Date();
    var nowHHMM = pad(now.getHours()) + ":" + pad(now.getMinutes());
    $todayEvents.innerHTML = "";
    if (!todayEvents.length) $todayEvents.appendChild(el("div", "today-empty", "Nothing on the calendar today"));
    todayEvents.forEach(function (ev) {
      // Fade out events that are over (timed events only; all-day ones last all day).
      var over = !ev.all_day && (ev.end || ev.start) < nowHHMM;
      var row = el("div", "today-event" + (over ? " over" : ""));
      row.style.setProperty("--cal", ev.color);
      row.appendChild(el("span", "today-time", eventLabel(ev)));
      row.appendChild(el("span", "today-title", ev.title));
      $todayEvents.appendChild(row);
    });
  }

  function loadToday() {
    return api("GET", "/api/calendar?days=1").then(function (data) {
      $todayCal.hidden = !data.configured;
      todayEvents = data.days.length ? data.days[0].events : [];
      renderToday();
    }, function () { /* keep showing what we had */ });
  }

  function tick() {
    var now = new Date();
    var h = now.getHours();
    $clock.textContent = ((h + 11) % 12 + 1) + ":" + pad(now.getMinutes()) + (h < 12 ? " am" : " pm");

    // New day: fetch the fresh board right away instead of waiting for the poll.
    var today = now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate());
    if (board && board.date !== today && now.getSeconds() % 10 === 0) { refresh(); loadToday(); }
    if (now.getSeconds() === 0) renderToday(); // fade events as they finish

    // A fridge never closes its tabs; reload overnight to stay fresh.
    if (h === 3 && Date.now() - loadedAt > 6 * 3600 * 1000) location.reload();
  }

  refresh();
  loadToday();
  tick();
  setInterval(tick, 1000);
  setInterval(refresh, POLL_MS);
  setInterval(loadToday, CALENDAR_MS);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) refresh(); });
})();
