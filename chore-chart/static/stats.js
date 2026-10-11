// Weekly stats screen. Plain ES2015 so it runs in older built-in browsers.
(function () {
  "use strict";

  var IDLE_RETURN_MS = 3 * 60 * 1000; // go back to the chart if nobody touches the screen
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var stats = null;
  var idleTimer = null;

  var $stats = document.getElementById("stats");
  var $week = document.getElementById("week");
  var $range = document.getElementById("range");
  var $prev = document.getElementById("prev");
  var $next = document.getElementById("next");
  var $offline = document.getElementById("offline");

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function parseDate(iso) {
    var p = iso.split("-");
    return new Date(+p[0], +p[1] - 1, +p[2]);
  }

  function shortDate(d) { return MONTHS[d.getMonth()] + " " + d.getDate(); }

  function isoDate(d) {
    var m = d.getMonth() + 1, day = d.getDate();
    return d.getFullYear() + "-" + (m < 10 ? "0" : "") + m + "-" + (day < 10 ? "0" : "") + day;
  }

  function shiftWeek(days) {
    var d = parseDate(stats.week_start);
    d.setDate(d.getDate() + days);
    load(isoDate(d));
  }

  function render() {
    var start = parseDate(stats.week_start);
    var end = parseDate(stats.days[6].date);
    $week.textContent = stats.is_current ? "This week" : "Week of " + shortDate(start);
    $range.textContent = shortDate(start) + " – " + shortDate(end);
    $prev.disabled = !stats.has_prev;
    $next.disabled = !stats.has_next;
    $stats.innerHTML = "";

    if (!stats.kids.length) {
      $stats.appendChild(el("div", "setup", "No kids set up yet."));
      return;
    }

    // Every kid's bars share one scale so the columns can be compared.
    var maxDay = 1;
    stats.kids.forEach(function (kid) {
      kid.days.forEach(function (d) { maxDay = Math.max(maxDay, d.done, d.assigned || 0); });
    });

    stats.kids.forEach(function (kid) {
      var col = el("section", "kid stat-card");
      col.style.setProperty("--kid", kid.color);

      var head = el("div", "kid-head");
      head.appendChild(el("div", "avatar", kid.emoji));
      head.appendChild(el("div", "kid-name", kid.name));
      head.appendChild(el("div", "stars", "⭐ " + kid.stars));
      col.appendChild(head);

      var total = el("div", "stat-total");
      total.appendChild(el("div", "stat-number", String(kid.done)));
      var sub = el("div", "stat-sub");
      sub.appendChild(el("div", "stat-label", kid.done === 1 ? "chore done" : "chores done"));
      if (kid.assigned) {
        var pct = Math.round(100 * Math.min(kid.done, kid.assigned) / kid.assigned);
        sub.appendChild(el("div", "stat-of", "of " + kid.assigned + (stats.is_current ? " so far" : "") + " · " + pct + "%"));
      }
      total.appendChild(sub);
      col.appendChild(total);

      var chart = el("div", "week-chart");
      kid.days.forEach(function (d, i) {
        var info = stats.days[i];
        var day = el("div", "wk-day" + (info.today ? " today" : "") + (info.future ? " future" : ""));
        day.appendChild(el("div", "wk-count", info.future ? "" : d.assigned ? d.done + "/" + d.assigned : String(d.done)));
        var track = el("div", "wk-track");
        if (d.assigned) {
          var goal = el("div", "wk-goal");
          goal.style.height = (100 * d.assigned / maxDay) + "%";
          track.appendChild(goal);
        }
        var bar = el("div", "wk-bar" + (d.assigned && d.done >= d.assigned ? " full" : ""));
        bar.style.height = (100 * d.done / maxDay) + "%";
        track.appendChild(bar);
        day.appendChild(track);
        day.appendChild(el("div", "wk-label", info.label));
        chart.appendChild(day);
      });
      col.appendChild(chart);
      $stats.appendChild(col);
    });
  }

  function load(week) {
    var url = "/api/stats" + (week ? "?week=" + week : "");
    return fetch(url, { cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error(res.statusText);
      return res.json();
    }).then(function (data) {
      stats = data;
      $offline.hidden = true;
      render();
    }, function () { $offline.hidden = false; });
  }

  function resetIdle() {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(function () { location.href = "/"; }, IDLE_RETURN_MS);
  }

  $prev.addEventListener("click", function () { shiftWeek(-7); });
  $next.addEventListener("click", function () { shiftWeek(7); });
  ["click", "touchstart"].forEach(function (ev) { document.addEventListener(ev, resetIdle); });

  load();
  resetIdle();
  // Keep the current week live while it's on screen.
  setInterval(function () { if (stats && stats.is_current) load(); }, 20000);
})();
