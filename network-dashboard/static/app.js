const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmtB = n => { n = n || 0; for (const u of ["B","KB","MB","GB","TB"]) { if (n < 1024 || u == "TB") return n.toFixed(n < 10 && u != "B" ? 1 : 0) + " " + u; n /= 1024; } };
const fmtRate = n => { const b = (n || 0) * 8; return b >= 1e9 ? (b / 1e9).toFixed(2) + " Gbps" : b >= 1e6 ? (b / 1e6).toFixed(b < 1e7 ? 2 : 1) + " Mbps" : (b / 1e3).toFixed(0) + " kbps"; };
const ago = t => { if (!t) return "—"; const s = Date.now() / 1000 - t; return s < 90 ? "just now" : s < 3600 ? Math.floor(s / 60) + " min ago" : s < 86400 ? Math.floor(s / 3600) + " h ago" : Math.floor(s / 86400) + " d ago"; };
const dur = s => { s = s || 0; const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return (d ? d + "d " : "") + h + "h " + m + "m"; };
const bar = (pct, warn = 70, bad = 90) => `<div class="bar"><i class="${pct >= bad ? "bad" : pct >= warn ? "warn" : ""}" style="width:${Math.min(100, pct || 0)}%"></i></div>`;
const plural = n => n + (n == 1 ? " client" : " clients");
const kv = (l, v) => `<div class="kv"><span>${l}</span><span>${v}</span></div>`;
let data = null;

function spark(vals, cls = "") {
  const v = vals.map(x => x == null ? null : +x), nums = v.filter(x => x != null);
  if (nums.length < 2) return `<svg class="spark ${cls}"></svg>`;
  const max = Math.max(...nums, 1e-9), W = 300, H = 40; let d = "", pen = false;
  v.forEach((x, i) => { if (x == null) { pen = false; return; } d += (pen ? "L" : "M") + (i / (v.length - 1) * W).toFixed(1) + " " + (H - 2 - x / max * (H - 4)).toFixed(1); pen = true; });
  return `<svg class="spark ${cls}" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><path vector-effect="non-scaling-stroke" d="${d}"/></svg>`;
}

function render(s) {
  data = s;
  const setup = $("setup"), has = s.enabled;
  setup.hidden = has && s.ok;
  if (!has) setup.innerHTML = `<h2>Connect your UniFi controller</h2><p>Open this app's <b>Configuration</b> tab in Home Assistant and set <b>unifi_url</b> (for example <code>https://192.168.1.1</code>), <b>unifi_username</b> and <b>unifi_password</b>, then restart the app. Use a local-only, View Only admin created in UniFi. Details are on the app's Documentation tab.</p>`;
  else if (!s.ok) setup.innerHTML = `<h2>UniFi</h2><div class="${s.last ? "warn" : "muted"}">${esc(s.error)}</div>${s.last ? `<div class="muted">Showing data from ${ago(s.last)}.</div>` : ""}`;
  if (!s.devices) { $("tiles").innerHTML = ""; return; }

  const hl = s.health || {}, wan = hl.wan || {}, www = hl.www || {}, gw = s.devices.find(d => d.wan);
  const online = s.clients_online || [], wifi = online.filter(c => !c.is_wired).length;
  const devUp = s.devices.filter(d => d.up).length, updates = s.devices.filter(d => d.upgradable).length;
  const rx = gw?.wan?.rx, tx = gw?.wan?.tx, st = gw?.speedtest || {};
  const wanOk = wan.status ? wan.status == "ok" : gw?.wan?.up;
  $("tiles").innerHTML = [
    ["Internet", wan.status || gw ? (wanOk ? "Online" : "Down") : "—", wanOk ? "ok" : "bad", [www.latency != null && www.latency + " ms", wan.wan_ip || gw?.wan?.ip].filter(Boolean).join(" · ")],
    ["WAN ↓ / ↑", rx != null ? fmtRate(rx) : "—", "", tx != null ? "↑ " + fmtRate(tx) : ""],
    ["Clients", online.length, "", `${wifi} Wi-Fi · ${online.length - wifi} wired`],
    ["UniFi devices", `${devUp} / ${s.devices.length}`, devUp < s.devices.length ? "warn" : "", updates ? `<span class="warn">${updates} update${updates > 1 ? "s" : ""}</span>` : "all up to date"],
    ["Gateway", gw ? (gw.cpu != null ? gw.cpu + "% CPU" : gw.name) : "—", gw?.cpu > 85 ? "warn" : "", gw ? [gw.temp != null && gw.temp + " °C", gw.uptime && dur(gw.uptime)].filter(Boolean).join(" · ") : ""],
  ].map(([l, b, c, sub]) => `<div class="tile"><div class="lbl">${l}</div><div class="big ${c}">${b}</div><div class="muted">${sub || "&nbsp;"}</div></div>`).join("");

  const h = s.hist || {};
  $("wan").innerHTML = `<div class="lg"><span>↓ Download</span><b>${rx != null ? fmtRate(rx) : "—"}</b></div>${spark(h.rx || [], "big")}
    <div class="lg"><span>↑ Upload</span><b>${tx != null ? fmtRate(tx) : "—"}</b></div>${spark(h.tx || [], "big")}
    <div class="lg"><span>Latency</span><b>${www.latency != null ? www.latency + " ms" : "—"}</b></div>${spark(h.lat || [], "big")}
    <div class="muted">Last ${Math.round((h.rx || []).length * 10 / 60)} min, measured by the gateway${gw?.wan?.speed ? " · link " + gw.wan.speed + " Mbps" : ""}</div>
    ${st.xput_download ? kv("Last speed test", `↓ ${(+st.xput_download).toFixed(0)} / ↑ ${(+st.xput_upload).toFixed(0)} Mbps · ${st.latency ?? "?"} ms`) + `<div class="muted">${st.rundate ? ago(st.rundate) : ""}</div>` : ""}
    ${wan.isp_name ? kv("ISP", esc(wan.isp_name)) : ""}${www.drops != null ? kv("Internet drops", www.drops) : ""}`;

  $("gw").innerHTML = gw ? kv("Model", esc(gw.model) + " · " + esc(gw.version)) + kv("WAN IP", esc(gw.wan?.ip || wan.wan_ip || "—")) + kv("Uptime", dur(gw.uptime)) +
    (gw.cpu != null ? kv("CPU", gw.cpu + "%") + bar(gw.cpu) : "") + (gw.mem != null ? kv("Memory", gw.mem + "%") + bar(gw.mem) : "") +
    (gw.temp != null ? kv("Temperature", gw.temp + " °C") + bar(gw.temp, 70, 85) : "") +
    (gw.ports ? `<div class="muted">Ports: ` + gw.ports.map(p => `<span class="pill ${p.up ? "" : "off"}" title="${esc(p.name)}">${p.port_idx}${p.up ? " · " + (p.speed >= 1000 ? p.speed / 1000 + "G" : p.speed + "M") : ""}</span>`).join("") + "</div>" : "")
    : '<div class="muted">No gateway found.</div>';

  const top = [...online].sort((a, b) => (b.rx + b.tx) - (a.rx + a.tx)).slice(0, 6);
  $("top").innerHTML = top.map(c => kv(esc(nameOf(c)), `↓ ${fmtRate(c.rx)} · ↑ ${fmtRate(c.tx)}`)).join("") || '<div class="muted">No clients.</div>';

  $("devices").innerHTML = s.devices.map(d => `<tr class="${d.up ? "" : "off"}"><td><span class="dot ${d.up ? "up" : ""}"></span></td><td>${esc(d.name)}</td><td>${esc(d.model)}</td><td>${esc(d.ip)}</td>
    <td>${d.num_sta ?? "—"}</td><td>${d.cpu != null ? d.cpu + "% / " + (d.mem ?? "?") + "%" : "—"}</td><td>${d.up ? dur(d.uptime) : "offline"}</td>
    <td>${esc(d.version)}${d.upgradable ? ' <span class="badge">update</span>' : ""}</td></tr>`).join("");

  const per = k => online.reduce((m, c) => (m[c[k]] = (m[c[k]] || 0) + 1, m), {});
  const bySsid = per("essid"), byNet = per("network");
  $("wlans").innerHTML = (s.wlans || []).map(w => kv(esc(w.name) + (w.is_guest ? '<span class="pill">guest</span>' : "") + (w.enabled === false ? '<span class="pill off">off</span>' : ""), plural(bySsid[w.name] || 0))).join("") || '<div class="muted">No data.</div>';
  $("nets").innerHTML = (s.networks || []).map(n => kv(esc(n.name) + (n.vlan ? `<span class="pill">VLAN ${esc(n.vlan)}</span>` : ""), `${plural(byNet[n.name] || 0)}${n.ip_subnet ? " · " + esc(n.ip_subnet) : ""}`)).join("") || '<div class="muted">No data.</div>';
  $("events").innerHTML = (s.events || []).slice(0, 12).map(e => `<div class="ev">${esc(String(e.msg || e.key).replace(/\{|\}/g, ""))}<div class="muted">${ago(e.time / 1000)}</div></div>`).join("") || '<div class="muted">No recent events.</div>';
  $("updated").textContent = s.last ? "Updated " + ago(s.last) : "";
  renderClients();
}

const nameOf = c => c.name || c.host || "Unnamed device";
const isNew = c => c.first_seen && !data.acked.includes(c.mac) && Date.now() / 1000 - c.first_seen < data.new_days * 86400;
const link = c => c.is_wired ? "" : (c.signal ? c.signal + " dBm" : "") + (c.rx_rate ? ` · ${(c.rx_rate / 1000).toFixed(0)} Mbps` : "");
function renderClients() {
  const q = $("filter").value.toLowerCase(), all = $("show").value == "all";
  const list = [...(data.clients_online || []), ...(all ? data.clients_known || [] : [])].filter(c => !q || JSON.stringify(c).toLowerCase().includes(q))
    .sort((a, b) => (b.online - a.online) || String(a.ip || "").localeCompare(String(b.ip || ""), undefined, { numeric: true }));
  $("clientCount").textContent = `(${(data.clients_online || []).length} online)`;
  $("clients").innerHTML = list.map(c => `<tr class="${c.online ? "" : "off"}"><td><span class="dot ${c.online ? "up" : ""}"></span></td>
    <td>${esc(nameOf(c))}${c.is_guest ? '<span class="pill">guest</span>' : ""}${isNew(c) ? `<span class="badge" data-ack="${esc(c.mac)}" title="Dismiss">NEW</span>` : ""}</td>
    <td>${esc(c.ip)}</td><td class="muted">${esc(c.mac)} ${esc(c.oui)}</td>
    <td>${c.online ? (c.is_wired ? `🔌 ${esc(c.via || "Wired")}${c.sw_port ? " · port " + c.sw_port : ""}` : `📶 ${esc(c.essid || "Wi-Fi")}<div class="muted">${esc(c.via)}${c.channel ? " · ch " + c.channel : ""}</div>`) : ""}</td>
    <td class="muted">${link(c)}</td><td>${c.online ? fmtRate(c.rx) + " / " + fmtRate(c.tx) : "—"}</td>
    <td class="muted">${fmtB(c.rx_total)} / ${fmtB(c.tx_total)}</td><td class="muted">${c.online ? "now" : ago(c.last_seen)}</td></tr>`).join("")
    || '<tr><td colspan="9" class="muted">No clients.</td></tr>';
}

document.addEventListener("click", async e => {
  if (e.target.dataset.ack) { await fetch("/api/ack", { method: "POST", body: JSON.stringify({ mac: e.target.dataset.ack }) }); load(); }
});
$("filter").oninput = $("show").onchange = () => data && renderClients();
async function load() {
  try { const s = await (await fetch("/api/status")).json(); render(s); }
  catch { $("updated").textContent = "Disconnected – retrying…"; }
}
load(); setInterval(load, 5000);
