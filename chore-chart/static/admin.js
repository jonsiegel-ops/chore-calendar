(function () {
  "use strict";

  var DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  var PALETTE = ["#ff7a45", "#3b82f6", "#22b573", "#a259ff", "#ff4f8b", "#f5b700"];
  var config = null;
  var pin = sessionStorageGet("chorePin");

  var $kids = document.getElementById("kids");
  var $chores = document.getElementById("chores");
  var $calendars = document.getElementById("calendars");
  var $title = document.getElementById("title");
  var $pin = document.getElementById("pin");
  var $status = document.getElementById("status");

  function sessionStorageGet(k) { try { return sessionStorage.getItem(k) || ""; } catch (e) { return ""; } }
  function sessionStorageSet(k, v) { try { sessionStorage.setItem(k, v); } catch (e) { /* private mode */ } }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function field(cls, labelText, input) {
    var wrap = el("div", cls);
    wrap.appendChild(el("label", null, labelText));
    wrap.appendChild(input);
    return wrap;
  }

  function textInput(value, onInput, type) {
    var i = document.createElement("input");
    i.type = type || "text";
    i.value = value;
    i.addEventListener("input", function () { onInput(i.value); });
    return i;
  }

  function status(msg, isErr) {
    $status.textContent = msg;
    $status.className = isErr ? "err" : "";
  }

  function request(method, body) {
    return fetch("/api/config", {
      method: method,
      headers: { "Content-Type": "application/json", "X-Admin-Pin": pin },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store"
    }).then(function (res) {
      if (res.status === 401) {
        var entered = prompt("Enter the settings PIN");
        if (entered === null) throw new Error("PIN required");
        pin = entered;
        sessionStorageSet("chorePin", pin);
        return request(method, body);
      }
      return res.json().then(function (data) {
        if (!res.ok) throw new Error(data.error || res.statusText);
        return data;
      });
    });
  }

  // ---------- rendering ----------

  function renderKids() {
    $kids.innerHTML = "";
    config.kids.forEach(function (kid, idx) {
      var row = el("div", "row");
      row.appendChild(field("f-emoji", "Emoji", textInput(kid.emoji || "", function (v) { kid.emoji = v; })));
      row.appendChild(field("f-name", "Name", textInput(kid.name, function (v) { kid.name = v; renderChores(); })));
      row.appendChild(field("", "Color", textInput(kid.color || "#4f7cff", function (v) { kid.color = v; renderChores(); }, "color")));
      var del = el("button", "btn danger", "Remove");
      del.type = "button";
      del.addEventListener("click", function () {
        if (!confirm("Remove " + (kid.name || "this kid") + "?")) return;
        config.kids.splice(idx, 1);
        config.chores.forEach(function (c) { c.kids = c.kids.filter(function (k) { return k !== kid.id; }); });
        renderAll();
      });
      row.appendChild(del);
      $kids.appendChild(row);
    });
  }

  function chip(label, on, onClick, extraCls, color) {
    var b = el("button", "chip" + (extraCls ? " " + extraCls : "") + (on ? " on" : ""), label);
    b.type = "button";
    if (color) b.style.setProperty("--c", color);
    b.addEventListener("click", onClick);
    return b;
  }

  function toggleIn(list, value) {
    var i = list.indexOf(value);
    if (i >= 0) list.splice(i, 1); else list.push(value);
  }

  function renderChores() {
    $chores.innerHTML = "";
    config.chores.forEach(function (chore, idx) {
      var row = el("div", "row");
      row.appendChild(field("f-emoji", "Emoji", textInput(chore.emoji || "", function (v) { chore.emoji = v; })));
      row.appendChild(field("f-name", "Chore", textInput(chore.title, function (v) { chore.title = v; })));
      var stars = textInput(String(chore.stars || 1), function (v) { chore.stars = parseInt(v, 10) || 1; }, "number");
      stars.min = 1; stars.max = 10;
      row.appendChild(field("f-stars", "Stars", stars));
      var del = el("button", "btn danger", "Remove");
      del.type = "button";
      del.addEventListener("click", function () { config.chores.splice(idx, 1); renderChores(); });
      row.appendChild(del);

      row.appendChild(el("div", "group-label", "Who"));
      var who = el("div", "chips");
      config.kids.forEach(function (kid) {
        if (!kid.id) return; // new kids get an id once saved
        who.appendChild(chip(kid.name || "?", chore.kids.indexOf(kid.id) >= 0, function () {
          toggleIn(chore.kids, kid.id); renderChores();
        }, "kid", kid.color));
      });
      if (config.kids.some(function (k) { return !k.id; })) who.appendChild(el("span", "group-label", "Save to assign newly added kids."));
      row.appendChild(who);

      row.appendChild(el("div", "group-label", "Which days"));
      var days = el("div", "chips");
      DAYS.forEach(function (name, d) {
        days.appendChild(chip(name, chore.days.indexOf(d) >= 0, function () {
          toggleIn(chore.days, d); renderChores();
        }));
      });
      row.appendChild(days);
      $chores.appendChild(row);
    });
  }

  function renderCalendars() {
    $calendars.innerHTML = "";
    config.calendars.forEach(function (cal, idx) {
      var row = el("div", "row");
      row.appendChild(field("f-name", "Name", textInput(cal.name || "", function (v) { cal.name = v; })));
      row.appendChild(field("", "Color", textInput(cal.color || "#4f7cff", function (v) { cal.color = v; }, "color")));
      var del = el("button", "btn danger", "Remove");
      del.type = "button";
      del.addEventListener("click", function () { config.calendars.splice(idx, 1); renderCalendars(); });
      row.appendChild(del);
      var url = textInput(cal.url || "", function (v) { cal.url = v.trim(); });
      url.placeholder = "webcal://p…-caldav.icloud.com/published/2/…";
      url.autocomplete = "off";
      row.appendChild(field("f-url", "Calendar link", url));
      $calendars.appendChild(row);
    });
  }

  function renderAll() {
    $title.value = config.title || "";
    $pin.value = config.admin_pin || "";
    renderKids();
    renderChores();
    renderCalendars();
  }

  // ---------- actions ----------

  $title.addEventListener("input", function () { config.title = $title.value; });
  $pin.addEventListener("input", function () { config.admin_pin = $pin.value; });

  document.getElementById("add-kid").addEventListener("click", function () {
    config.kids.push({ name: "", emoji: "🙂", color: PALETTE[config.kids.length % PALETTE.length] });
    renderAll();
  });

  document.getElementById("add-chore").addEventListener("click", function () {
    config.chores.push({
      title: "", emoji: "✅", stars: 1,
      kids: config.kids.filter(function (k) { return k.id; }).map(function (k) { return k.id; }),
      days: [0, 1, 2, 3, 4, 5, 6]
    });
    renderChores();
  });

  document.getElementById("add-calendar").addEventListener("click", function () {
    config.calendars.push({ name: "", url: "", color: PALETTE[(config.calendars.length + 2) % PALETTE.length] });
    renderCalendars();
  });

  document.getElementById("save").addEventListener("click", function () {
    status("Saving…");
    request("PUT", config).then(function (saved) {
      config = saved;
      config.calendars = config.calendars || [];
      pin = saved.admin_pin || "";
      sessionStorageSet("chorePin", pin);
      renderAll();
      status("Saved ✓ The fridge will update within 20 seconds.");
    }, function (e) { status(e.message, true); });
  });

  request("GET").then(function (data) {
    config = data;
    config.calendars = config.calendars || [];
    renderAll();
  }, function (e) { status(e.message, true); });
})();
