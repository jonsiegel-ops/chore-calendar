// Calendar agenda screen. Plain ES2015 so it runs in older built-in browsers.
(function () {
  "use strict";

  var REFRESH_MS = 5 * 60 * 1000;     // the server re-fetches iCloud every 15 minutes
  var IDLE_RETURN_MS = 5 * 60 * 1000; // go back to the chart if nobody touches the screen
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var idleTimer = null;

  var $agenda = document.getElementById("agenda");
  var $legend = document.getElementById("legend");
  var $day = document.getElementById("day");
  var $clock = document.getElementById("clock");
  var $offline = document.getElementById("offline");

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function pad(n) { return n < 10 ? "0" + n : "" + n; }

  function time12(hhmm) {
    var p = hhmm.split(":"), h = +p[0];
    return ((h + 11) % 12 + 1) + (p[1] === "00" ? "" : ":" + p[1]) + (h < 12 ? " am" : " pm");
  }

  function dayTitle(day, i) {
    if (i === 0) return "Today";
    if (i === 1) return "Tomorrow";
    var p = day.date.split("-");
    return day.weekday + ", " + MONTHS[+p[1] - 1] + " " + +p[2];
  }

  function eventTime(ev) {
    var box = el("div", "cal-time");
    if (ev.all_day) box.textContent = "All day";
    else if (!ev.start) box.textContent = "until " + time12(ev.end);
    else {
      box.textContent = time12(ev.start);
      if (ev.end) box.appendChild(el("div", "cal-until", "to " + time12(ev.end)));
    }
    return box;
  }

  function render(data) {
    $legend.innerHTML = "";
    if (data.calendars.length > 1) {
      data.calendars.forEach(function (c) {
        var chip = el("span", "legend-chip", c.name);
        chip.style.setProperty("--cal", c.color);
        $legend.appendChild(chip);
      });
    }

    $agenda.innerHTML = "";
    if (!data.configured) {
      var setup = el("div", "setup");
      setup.appendChild(document.createTextNode("No calendars yet. Add an iCloud calendar link in "));
      var link = el("a", null, "Settings");
      link.href = "/admin";
      setup.appendChild(link);
      setup.appendChild(document.createTextNode("."));
      $agenda.appendChild(setup);
      return;
    }

    data.days.forEach(function (day, i) {
      // Always show today and tomorrow; skip later days with nothing on them.
      if (!day.events.length && i > 1) return;
      var card = el("section", "cal-day" + (i === 0 ? " today" : ""));
      card.appendChild(el("h2", "cal-day-title", dayTitle(day, i)));
      if (!day.events.length) card.appendChild(el("div", "cal-empty", "Nothing scheduled"));

      day.events.forEach(function (ev) {
        var row = el("div", "cal-event");
        row.style.setProperty("--cal", ev.color);
        row.appendChild(eventTime(ev));
        var body = el("div", "cal-body");
        body.appendChild(el("div", "cal-title", ev.title));
        var meta = [ev.location, data.calendars.length > 1 ? ev.calendar : ""].filter(Boolean).join(" · ");
        if (meta) body.appendChild(el("div", "cal-meta", meta));
        row.appendChild(body);
        card.appendChild(row);
      });
      $agenda.appendChild(card);
    });

    data.warnings.forEach(function (w) { $agenda.appendChild(el("div", "cal-warning", "⚠️ " + w)); });
  }

  function load() {
    return fetch("/api/calendar", { cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error(res.statusText);
      return res.json();
    }).then(function (data) {
      $offline.hidden = true;
      render(data);
    }, function () { $offline.hidden = false; });
  }

  function tick() {
    var now = new Date(), h = now.getHours();
    $day.textContent = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][now.getDay()];
    $clock.textContent = ((h + 11) % 12 + 1) + ":" + pad(now.getMinutes()) + (h < 12 ? " am" : " pm");
  }

  function resetIdle() {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(function () { location.href = "/"; }, IDLE_RETURN_MS);
  }

  ["click", "touchstart", "scroll"].forEach(function (ev) { document.addEventListener(ev, resetIdle, true); });

  load();
  tick();
  resetIdle();
  setInterval(tick, 1000);
  setInterval(load, REFRESH_MS);
})();
