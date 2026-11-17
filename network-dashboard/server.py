#!/usr/bin/env python3
"""UniFi network dashboard. Every number comes from the UniFi controller's local API (read-only).
Standard library only. Runs as a Home Assistant app or standalone."""
import argparse, json, os, ssl, threading, time, urllib.error, urllib.request
from http import cookiejar
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DATA_DIR = os.environ.get("DASH_DATA_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
HISTORY, FAST, SLOW = 180, 10, 60      # history points kept; seconds between fast / slow polls
NEW_DAYS = 7                           # a client first seen within this many days is flagged NEW
LOCK = threading.Lock()
state = {"started": time.time(), "enabled": False, "ok": False, "error": "", "last": 0, "hist": {"rx": [], "tx": [], "lat": []}}


def load_json(name, default):
    try:
        with open(os.path.join(DATA_DIR, name)) as f: return json.load(f)
    except (OSError, ValueError): return default

def save_json(name, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = os.path.join(DATA_DIR, name + ".tmp")
    with open(tmp, "w") as f: json.dump(obj, f)
    os.replace(tmp, os.path.join(DATA_DIR, name))


def options():
    """Settings from the Home Assistant app options, or UNIFI_* environment variables when standalone."""
    o = load_json("options.json", {}) if DATA_DIR.startswith("/data") else {}
    def g(k, env, d=""): return o.get(k) if o.get(k) not in (None, "") else os.environ.get(env, d)
    return {"url": str(g("unifi_url", "UNIFI_URL")).rstrip("/"), "user": g("unifi_username", "UNIFI_USERNAME"),
            "password": g("unifi_password", "UNIFI_PASSWORD"), "site": g("unifi_site", "UNIFI_SITE", "default") or "default",
            "verify": str(g("unifi_verify_ssl", "UNIFI_VERIFY_SSL", "false")).lower() == "true",
            "os": str(g("unifi_os", "UNIFI_OS", "true")).lower() != "false"}


class UniFi:
    def __init__(self, o):
        self.o, self.csrf, self.jar = o, None, cookiejar.CookieJar()
        ctx = ssl.create_default_context()
        if not o["verify"]: ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), urllib.request.HTTPSHandler(context=ctx))

    def _open(self, url, body=None):
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", **({"X-CSRF-Token": self.csrf} if self.csrf else {})})
        with self.opener.open(req, timeout=12) as r:
            self.csrf = r.headers.get("X-Updated-CSRF-Token") or r.headers.get("X-CSRF-Token") or self.csrf
            return json.loads(r.read() or b"{}")

    def login(self):
        self.csrf = None; self.jar.clear()
        self._open(self.o["url"] + ("/api/auth/login" if self.o["os"] else "/api/login"),
                   {"username": self.o["user"], "password": self.o["password"], "remember": True})

    def get(self, what, retry=True):
        if not len(self.jar): self.login()
        base = self.o["url"] + ("/proxy/network" if self.o["os"] else "")
        try: return self._open("%s/api/s/%s/%s" % (base, self.o["site"], what)).get("data", [])
        except urllib.error.HTTPError as e:
            if e.code == 401 and retry: self.login(); return self.get(what, False)
            raise

    def try_get(self, what):
        """Optional data: a missing permission or endpoint must not take the whole dashboard down."""
        try: return self.get(what)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404): return []
            raise


def pick(d, *keys): return {k: d.get(k) for k in keys if d.get(k) is not None}

def shape_device(d):
    s = d.get("system-stats") or {}
    temps = d.get("temperatures") or []
    out = pick(d, "mac", "ip", "model", "type", "version", "num_sta", "adopted", "uptime", "general_temperature", "satisfaction")
    out.update(name=d.get("name") or d.get("model") or d.get("mac"), up=d.get("state") == 1, upgradable=bool(d.get("upgradable")),
               cpu=_num(s.get("cpu")), mem=_num(s.get("mem")),
               temp=d.get("general_temperature") if d.get("general_temperature") is not None else (temps[0].get("value") if temps else None),
               rx=d.get("rx_bytes-r"), tx=d.get("tx_bytes-r"))
    if d.get("type") in ("udm", "ugw", "uxg", "ucg"):
        w = d.get("wan1") or {}
        out["wan"] = dict(pick(w, "ip", "name", "speed", "up", "full_duplex"), rx=w.get("rx_bytes-r"), tx=w.get("tx_bytes-r"),
                          type=(d.get("uplink") or {}).get("type"))
        st = d.get("speedtest-status") or {}
        out["speedtest"] = dict(pick(st, "latency", "xput_download", "xput_upload", "rundate"))
    ports = d.get("port_table") or []
    if ports:
        out["ports"] = [dict(pick(p, "port_idx", "name", "up", "speed", "poe_enable", "poe_power", "is_uplink"),
                             rx=p.get("rx_bytes-r"), tx=p.get("tx_bytes-r")) for p in ports]
    return out

def _num(v):
    try: return float(v)
    except (TypeError, ValueError): return None

def shape_client(c, names, online):
    out = pick(c, "mac", "ip", "is_wired", "is_guest", "essid", "signal", "channel", "radio", "network", "uptime", "oui",
               "last_seen", "first_seen", "tx_rate", "rx_rate", "satisfaction", "sw_port", "use_fixedip")
    wired = c.get("is_wired")
    out.update(name=c.get("name") or "", host=c.get("hostname") or "", online=online,
               via=names.get(c.get("sw_mac") if wired else c.get("ap_mac"), ""),
               rx=c.get("rx_bytes-r", 0), tx=c.get("tx_bytes-r", 0),
               rx_total=c.get("rx_bytes", 0), tx_total=c.get("tx_bytes", 0))
    return out

def poll_fast(api):
    clients, devices, health = api.get("stat/sta"), api.get("stat/device"), api.get("stat/health")
    names = {d.get("mac"): d.get("name") or d.get("model") for d in devices}
    devs = [shape_device(d) for d in devices]
    gw = next((d for d in devs if "wan" in d), None)
    hl = {h.get("subsystem"): h for h in health}
    wan, www = hl.get("wan", {}), hl.get("www", {})
    rx = (gw or {}).get("wan", {}).get("rx") if gw else None
    tx = (gw or {}).get("wan", {}).get("tx") if gw else None
    if rx is None: rx, tx = wan.get("rx_bytes-r"), wan.get("tx_bytes-r")
    with LOCK:
        state["devices"] = devs
        state["clients_online"] = [shape_client(c, names, True) for c in clients]
        state["health"] = {k: dict(pick(h, "status", "num_user", "num_adopted", "num_disconnected", "num_pending", "num_ap", "num_sw",
                                        "num_gw", "wan_ip", "gw_mac", "latency", "uptime", "drops", "xput_up", "xput_down",
                                        "speedtest_lastrun", "isp_name", "isp_organization")) for k, h in hl.items()}
        state["names"] = names
        for k, v in (("rx", rx), ("tx", tx), ("lat", www.get("latency"))):
            state["hist"][k] = (state["hist"][k] + [v])[-HISTORY:]

def poll_slow(api):
    allusers = api.try_get("stat/alluser")
    events = api.try_get("stat/event?_limit=40")
    wlans, nets = api.try_get("rest/wlanconf"), api.try_get("rest/networkconf")
    with LOCK:
        names, online = state.get("names", {}), {c["mac"] for c in state.get("clients_online", [])}
        state["clients_known"] = [shape_client(c, names, False) for c in sorted(allusers, key=lambda c: -(c.get("last_seen") or 0))[:300]
                                  if c.get("mac") not in online]
        state["events"] = [dict(pick(e, "key", "time", "datetime", "msg", "subsystem", "ap", "user", "ssid", "hostname", "sw", "gw"))
                           for e in sorted(events, key=lambda e: -(e.get("time") or 0))]
        state["wlans"] = [pick(w, "name", "enabled", "security", "is_guest", "vlan", "usergroup_id") for w in wlans]
        state["networks"] = [pick(n, "name", "purpose", "vlan", "ip_subnet", "enabled") for n in nets]


def poller():
    o = options()
    if not (o["url"] and o["user"] and o["password"]):
        with LOCK: state.update(enabled=False, error="UniFi isn't configured yet.")
        return
    with LOCK: state.update(enabled=True, ok=False, error="Connecting…", site=o["site"])
    api, slow_at = UniFi(o), 0
    while True:
        try:
            poll_fast(api)
            if time.time() - slow_at >= SLOW: poll_slow(api); slow_at = time.time()
            with LOCK: state.update(ok=True, error="", last=time.time())
        except Exception as e:
            code = getattr(e, "code", 0)
            msg = ("Login rejected: check the username and password (use a local-only admin, not your Ubiquiti account)." if code in (400, 401, 403)
                   else "Can't reach the controller: %s" % (getattr(e, "reason", None) or e))
            api.jar.clear()
            with LOCK: state.update(ok=False, error=msg)
            print("UniFi:", msg, flush=True)
        time.sleep(FAST)


# ---------- HTTP ----------
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype="application/json"):
        if not isinstance(body, bytes): body = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/api/status":
            with LOCK:
                acked = set(load_json("acked.json", []))
                s = {k: v for k, v in state.items() if k != "names"}
                s["now"] = time.time(); s["acked"] = sorted(acked); s["new_days"] = NEW_DAYS
                return self.send(200, s)
        if p == "/": p = "/index.html"
        f = os.path.normpath(os.path.join(STATIC, p.lstrip("/")))
        if f.startswith(STATIC + os.sep) and os.path.isfile(f):
            with open(f, "rb") as fh: self.send(200, fh.read(), TYPES.get(os.path.splitext(f)[1], "application/octet-stream"))
        else: self.send(404, {"error": "not found"})

    def do_POST(self):  # the only write is dismissing a NEW badge, stored here; nothing is ever sent to the controller
        if self.path == "/api/ack":
            try: mac = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))["mac"]
            except (ValueError, KeyError, TypeError): return self.send(400, {"error": "bad request"})
            acked = set(load_json("acked.json", [])); acked.add(str(mac)[:32]); save_json("acked.json", sorted(acked))
            return self.send(200, {"ok": True})
        self.send(404, {"error": "not found"})


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8081)
    port = ap.parse_args().port
    threading.Thread(target=poller, daemon=True).start()
    print("Network dashboard running on http://0.0.0.0:%d" % port, flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()

if __name__ == "__main__":
    main()
