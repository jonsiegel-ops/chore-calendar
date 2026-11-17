const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmtB = n => { for (const u of ["B","KB","MB","GB","TB"]) { if (n < 1024 || u == "TB") return n.toFixed(n < 10 && u != "B" ? 1 : 0) + " " + u; n /= 1024; } };
const fmtRate = n => (n * 8 / 1e6).toFixed(n * 8 < 1e7 ? 2 : 1) + " Mbps";
const ago = t => { const s = Date.now() / 1000 - t; return s < 60 ? "just now" : s < 3600 ? Math.floor(s / 60) + " min ago" : s < 86400 ? Math.floor(s / 3600) + " h ago" : Math.floor(s / 86400) + " d ago"; };
const dur = s => { const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return (d ? d + "d " : "") + h + "h " + m + "m"; };
const api = (p, b) => fetch(p, { method: "POST", body: JSON.stringify(b || {}) }).then(r => r.json());

function spark(vals, key) {
  const v = vals.map(x => x == null ? null : +x), nums = v.filter(x => x != null);
  if (nums.length < 2) return '<svg class="spark"></svg>';
  const max = Math.max(...nums, 1), W = 90, H = 24; let d = "", pen = false;
  v.forEach((x, i) => { if (x == null) { pen = false; return; }
    d += (pen ? "L" : "M") + (i / (v.length - 1) * W).toFixed(1) + " " + (H - 2 - x / max * (H - 4)).toFixed(1); pen = true; });
  return `<svg class="spark" viewBox="0 0 ${W} ${H}"><path d="${d}"/></svg>`;
}
const bar = (pct, warn = 70, bad = 90) => `<div class="bar"><i class="${pct >= bad ? "bad" : pct >= warn ? "warn" : ""}" style="width:${Math.min(100, pct)}%"></i></div>`;
let data = null, editing = false;

function render(s) {
  data = s;
  const mons = Object.entries(s.monitors), devs = Object.entries(s.devices);
  const online = Object.values(mergedDevices()).filter(d => d.online).length, fresh = devs.filter(([, d]) => d.new).length;
  const inet = mons.filter(([k]) => k.startsWith("internet-")), inetUp = inet.some(([, m]) => m.up);
  const gw = s.monitors.gateway;
  $("tiles").innerHTML = [
    ["Internet", inet.length ? (inetUp ? "Online" : "Down") : "—", inet.length ? (inetUp ? "ok" : "bad") : "", inet.filter(([, m]) => m.up).map(([, m]) => m.ms.toFixed(0) + " ms").join(" · ")],
    ["Router", gw ? (gw.up ? gw.ms.toFixed(1) + " ms" : "Down") : "—", gw ? (gw.up ? "ok" : "bad") : "", s.gateway],
    ["Devices online", online, "", Object.keys(mergedDevices()).length + " known" + (fresh ? ` · <span class="warn">${fresh} new</span>` : "")],
    ["Down / Up", s.net.rx != null ? "↓ " + fmtRate(s.net.rx) : "—", "", s.net.tx != null ? "↑ " + fmtRate(s.net.tx) : ""],
    ["Pi uptime", s.system.uptime ? dur(s.system.uptime) : "—", "", s.local_ip],
  ].map(([l, b, c, sub]) => `<div class="tile"><div class="lbl">${l}</div><div class="big ${c}">${b}</div><div class="muted">${sub || "&nbsp;"}</div></div>`).join("");

  $("monitors").innerHTML = mons.map(([id, m]) => `<div class="mon"><span class="dot ${m.up ? "up" : ""}"></span>
    <div>${esc(m.name)}<div class="muted">${esc(m.type)} ${esc(m.host)}${m.port ? ":" + m.port : ""}</div></div>
    ${spark(m.hist)}<span class="${m.up ? "" : "bad"}">${m.up ? m.ms.toFixed(0) + " ms" : "down"}</span>
    ${m.builtin ? "" : `<button class="ghost" data-del="${id}" title="Remove">✕</button>`}</div>`).join("") || '<div class="muted">Collecting…</div>';

  const nh = s.net_hist || [];
  $("net").innerHTML = `<div class="kv"><span>↓ Download</span><b>${s.net.rx != null ? fmtRate(s.net.rx) : "—"}</b></div>${spark(nh.map(x => x[0]))}
    <div class="kv"><span>↑ Upload</span><b>${s.net.tx != null ? fmtRate(s.net.tx) : "—"}</b></div>${spark(nh.map(x => x[1]))}
    <div class="muted">Combined across the Pi's network interfaces</div>`;

  const y = s.system, row = (l, v, pct, extra) => `<div class="kv"><span>${l}</span><span>${v}</span></div>${pct != null ? bar(pct, ...(extra || [])) : ""}`;
  $("sys").innerHTML =
    (y.cpu != null ? row("CPU", y.cpu + "%", y.cpu) : "") +
    (y.mem_total ? row("Memory", fmtB(y.mem_used) + " / " + fmtB(y.mem_total), 100 * y.mem_used / y.mem_total) : "") +
    (y.disk_total ? row("Disk", fmtB(y.disk_used) + " / " + fmtB(y.disk_total), 100 * y.disk_used / y.disk_total, [80, 92]) : "") +
    (y.temp != null ? row("Temperature", y.temp + " °C", y.temp, [60, 75]) : "") +
    (y.load ? `<div class="kv"><span>Load (1/5/15 min)</span><span>${y.load.map(x => x.toFixed(2)).join(" · ")}</span></div>` : "");

  const sc = s.scan;
  $("scanInfo").textContent = sc.running ? "Scanning…" : sc.last ? `Last sweep ${ago(sc.last)} of ${sc.subnet} (${sc.duration}s)` : "First sweep starting…";
  renderUnifi(s.unifi || {});
  $("devCount").textContent = `(${online} online)`;
  if (!editing) renderDevices();
}

function renderUnifi(u) {
  $("unifiCard").hidden = !u.enabled;
  if (!u.enabled) return;
  if (!u.ok) { $("unifiInfo").textContent = ""; $("unifi").innerHTML = `<div class="${u.last ? "warn" : "muted"}">${esc(u.error || "Connecting…")}</div>`; return; }
  $("unifiInfo").textContent = "· updated " + ago(u.last);
  const hl = u.health || {}, wan = hl.wan || {}, www = hl.www || {};
  const stat = (l, v, c) => `<span class="chip ${c || ""}">${l}: <b>${v}</b></span>`;
  const chips = [
    wan.status && stat("WAN", wan.status, wan.status == "ok" ? "ok" : "bad"), wan.wan_ip && stat("WAN IP", esc(wan.wan_ip)),
    www.latency != null && stat("Internet latency", www.latency + " ms"),
    www.xput_down ? stat("Last speed test", "↓ " + www.xput_down.toFixed(0) + " / ↑ " + (www.xput_up || 0).toFixed(0) + " Mbps") : "",
    hl.wlan && stat("Wi-Fi clients", hl.wlan.num_user ?? 0), hl.lan && stat("Wired clients", hl.lan.num_user ?? 0),
  ].filter(Boolean).join("");
  $("unifi").innerHTML = `<div class="row">${chips}</div><div class="tablewrap"><table><thead><tr><th></th><th>Device</th><th>Model</th><th>IP</th><th>Clients</th><th>Uptime</th><th>Firmware</th></tr></thead><tbody>` +
    u.devices.map(d => `<tr class="${d.up ? "" : "off"}"><td><span class="dot ${d.up ? "up" : ""}"></span></td><td>${esc(d.name)}</td><td>${esc(d.model)}</td><td>${esc(d.ip)}</td>
      <td>${d.num_sta ?? "—"}</td><td>${d.up && d.uptime ? dur(d.uptime) : "offline"}</td><td>${esc(d.version)}${d.upgradable ? ' <span class="badge">update</span>' : ""}</td></tr>`).join("") + "</tbody></table></div>";
}

function mergedDevices() {
  const out = {}, u = data.unifi || {}, uc = {};
  (u.clients || []).forEach(c => uc[c.mac] = c);
  for (const [k, d] of Object.entries(data.devices)) { const c = uc[d.mac]; out[k] = { ...d, u: c, online: c ? true : d.online, last_seen: c ? Date.now() / 1000 : d.last_seen, ip: c?.ip || d.ip, host: d.host || c?.name || c?.host }; delete uc[d.mac]; }
  for (const c of Object.values(uc)) out["unifi:" + c.mac] = { mac: c.mac, ip: c.ip || "", name: "", host: c.name || c.host, vendor: c.oui || "", online: true, last_seen: Date.now() / 1000, rtt: null, u: c, unifiOnly: true };
  return out;
}
const conn = c => !c ? "" : c.is_wired ? `🔌 ${esc(c.via || "Wired")}${c.sw_port ? " · port " + c.sw_port : ""}` : `📶 ${esc(c.essid || "Wi-Fi")}${c.signal ? " · " + c.signal + " dBm" : ""}<div class="muted">${esc(c.via)}</div>`;

function renderDevices() {
  const q = $("filter").value.toLowerCase(), all = mergedDevices();
  const rows = Object.entries(all).filter(([, d]) => !q || JSON.stringify(d).toLowerCase().includes(q))
    .sort(([, a], [, b]) => (b.online - a.online) || a.ip.localeCompare(b.ip, undefined, { numeric: true }));
  $("devs").innerHTML = rows.map(([k, d]) => `<tr class="${d.online ? "" : "off"}"><td><span class="dot ${d.online ? "up" : ""}"></span></td>
    <td><span class="name" data-name="${esc(k)}">${esc(d.name || d.host || "Unnamed device")}</span>${d.new ? `<span class="badge" data-ack="${esc(k)}" title="Dismiss">NEW</span>` : ""}</td>
    <td>${esc(d.ip)}</td><td class="muted">${esc(d.mac)} ${esc(d.vendor)}</td><td>${conn(d.u)}</td><td>${d.online && d.rtt != null ? d.rtt.toFixed(0) + " ms" : "—"}</td>
    <td class="muted">${d.online ? "now" : ago(d.last_seen)}</td><td>${d.online || d.unifiOnly ? "" : `<button class="ghost" data-forget="${esc(k)}" title="Forget">✕</button>`}</td></tr>`).join("")
    || '<tr><td colspan="8" class="muted">No devices yet.</td></tr>';
}

document.addEventListener("click", async e => {
  const t = e.target;
  if (t.dataset.del) { await api("/api/monitor/delete", { id: t.dataset.del }); load(); }
  if (t.dataset.ack) { await api("/api/device", { key: t.dataset.ack, new: false }); load(); }
  if (t.dataset.forget && confirm("Forget this device?")) { await api("/api/device", { key: t.dataset.forget, forget: true }); load(); }
  if (t.dataset.name) {
    const d = mergedDevices()[t.dataset.name], n = prompt("Name this device:", d.name || d.host || "");
    if (n !== null) { await api("/api/device", { key: t.dataset.name, name: n, new: false, mac: d.mac, ip: d.ip }); load(); }
  }
});
$("scan").onclick = async () => { await api("/api/scan"); setTimeout(load, 500); };
$("filter").oninput = () => data && renderDevices();
$("filter").onfocus = () => editing = true; $("filter").onblur = () => editing = false;
$("addMon").querySelector("[name=type]").onchange = e => $("addMon").querySelector("[name=port]").style.display = e.target.value == "tcp" ? "block" : "none";
$("addMon").onsubmit = async e => { e.preventDefault(); const f = Object.fromEntries(new FormData(e.target));
  const r = await api("/api/monitor", f); if (r.error) return alert(r.error); e.target.reset(); load(); };

async function load() {
  try { const s = await (await fetch("/api/status")).json(); render(s); $("updated").textContent = "Updated " + new Date().toLocaleTimeString(); }
  catch { $("updated").textContent = "Disconnected – retrying…"; }
}
load(); setInterval(load, 5000);
