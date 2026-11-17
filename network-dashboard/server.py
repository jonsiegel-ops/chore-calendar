#!/usr/bin/env python3
"""Network dashboard: standard library only. Runs as a Home Assistant app or standalone."""
import argparse, json, os, re, shutil, socket, ssl, subprocess, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from http import cookiejar
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DATA_DIR = os.environ.get("DASH_DATA_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
HISTORY = 120          # latency samples kept per target
SAMPLE_EVERY = 15      # seconds between latency/system samples
SCAN_EVERY = 300       # seconds between LAN sweeps
LOCK = threading.Lock()

OUI = {  # tiny vendor hint table (first 3 MAC bytes)
    "b8:27:eb": "Raspberry Pi", "dc:a6:32": "Raspberry Pi", "e4:5f:01": "Raspberry Pi", "d8:3a:dd": "Raspberry Pi",
    "00:17:88": "Philips Hue", "f0:18:98": "Apple", "3c:22:fb": "Apple", "a4:83:e7": "Apple", "f4:f1:5a": "Apple",
    "00:16:32": "Samsung", "8c:77:12": "Samsung", "fc:a1:3e": "Samsung", "f4:f5:d8": "Google", "3c:5a:b4": "Google",
    "44:65:0d": "Amazon", "fc:65:de": "Amazon", "50:dc:e7": "Amazon", "b0:be:76": "TP-Link", "50:c7:bf": "TP-Link",
    "00:11:32": "Synology", "24:5e:be": "QNAP", "18:b4:30": "Nest", "64:16:66": "Nest", "d0:73:d5": "LIFX",
    "a0:20:a6": "Espressif", "24:6f:28": "Espressif", "30:ae:a4": "Espressif", "ac:67:b2": "Espressif",
    "00:04:20": "Slim Devices", "b8:e9:37": "Sonos", "5c:aa:fd": "Sonos", "00:0e:58": "Sonos",
}

DEFAULT_CONFIG = {"subnet": "", "monitors": [
    {"id": "internet-cf", "name": "Cloudflare", "type": "ping", "host": "1.1.1.1"},
    {"id": "internet-g", "name": "Google DNS", "type": "ping", "host": "8.8.8.8"},
]}

state = {
    "started": time.time(), "system": {}, "net": {}, "monitors": {}, "devices": {},
    "unifi": {"enabled": False}, "scan": {"running": False, "last": 0, "subnet": "", "duration": 0}, "gateway": "", "local_ip": "",
}
config = {}
_prev = {"cpu": None, "net": None}


# ---------- persistence ----------
def _path(name): return os.path.join(DATA_DIR, name)

def load_json(name, default):
    try:
        with open(_path(name)) as f: return json.load(f)
    except (OSError, ValueError): return default

def save_json(name, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = _path(name) + ".tmp"
    with open(tmp, "w") as f: json.dump(obj, f)
    os.replace(tmp, _path(name))


# ---------- probes ----------
def ping(host, timeout=2):
    try:
        out = subprocess.run(["ping", "-c", "1", "-W", str(timeout), host], capture_output=True, text=True, timeout=timeout + 2).stdout
        m = re.search(r"time[=<]([\d.]+)", out)
        return float(m.group(1)) if m else None
    except Exception: return None

def tcp(host, port, timeout=2):
    t = time.time()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout): return (time.time() - t) * 1000
    except Exception: return None

def http(url, timeout=4):
    t = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "network-dashboard"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return (time.time() - t) * 1000 if r.status < 500 else None
    except urllib.error.HTTPError as e: return (time.time() - t) * 1000 if e.code < 500 else None
    except Exception: return None

def run_monitor(m):
    t, h = m.get("type"), m.get("host", "")
    if t == "tcp": return tcp(h, m.get("port", 80))
    if t == "http": return http(h)
    return ping(h)

def default_gateway():
    try:
        with open("/proc/net/route") as f:
            for line in list(f)[1:]:
                p = line.split()
                if p[1] == "00000000":
                    g = int(p[2], 16)
                    return ".".join(str((g >> (8 * i)) & 255) for i in range(4))
    except OSError: pass
    return ""

def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("192.0.2.1", 9))
        ip = s.getsockname()[0]; s.close(); return ip
    except OSError: return ""

def system_stats():
    s = {}
    try:
        with open("/proc/stat") as f: v = [int(x) for x in f.readline().split()[1:]]
        idle, total = v[3] + v[4], sum(v)
        if _prev["cpu"]:
            di, dt = idle - _prev["cpu"][0], total - _prev["cpu"][1]
            s["cpu"] = round(100 * (1 - di / dt), 1) if dt else 0
        _prev["cpu"] = (idle, total)
    except (OSError, ValueError): pass
    try:
        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":"); mem[k] = int(v.split()[0]) * 1024
        s["mem_total"], s["mem_used"] = mem["MemTotal"], mem["MemTotal"] - mem["MemAvailable"]
    except (OSError, KeyError, ValueError): pass
    try:
        d = shutil.disk_usage(DATA_DIR if os.path.isdir(DATA_DIR) else "/")
        s["disk_total"], s["disk_used"] = d.total, d.used
    except OSError: pass
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f: s["temp"] = round(int(f.read()) / 1000, 1)
    except (OSError, ValueError): pass
    try:
        with open("/proc/uptime") as f: s["uptime"] = float(f.read().split()[0])
        s["load"] = os.getloadavg()
    except (OSError, ValueError): pass
    return s

def net_rates():
    """Bytes/sec in and out summed over real interfaces."""
    rx = tx = 0
    try:
        with open("/proc/net/dev") as f:
            for line in list(f)[2:]:
                name, data = line.split(":"); name = name.strip()
                if name == "lo" or name.startswith(("veth", "docker", "hassio", "br-")): continue
                c = data.split(); rx += int(c[0]); tx += int(c[8])
    except (OSError, ValueError, IndexError): return {}
    now, prev = time.time(), _prev["net"]
    _prev["net"] = (now, rx, tx)
    if not prev or now <= prev[0]: return {}
    dt = now - prev[0]
    return {"rx": max(0, (rx - prev[1]) / dt), "tx": max(0, (tx - prev[2]) / dt)}


# ---------- LAN scan ----------
def arp_table():
    out = {}
    try:
        with open("/proc/net/arp") as f:
            for line in list(f)[1:]:
                p = line.split()
                if len(p) >= 6 and p[2] != "0x0" and p[3] != "00:00:00:00:00:00": out[p[0]] = p[3].lower()
    except OSError: pass
    return out

def rdns(ip):
    try: return socket.gethostbyaddr(ip)[0].split(".")[0]
    except Exception: return ""

def scan():
    with LOCK:
        if state["scan"]["running"]: return
        state["scan"]["running"] = True
    t0 = time.time()
    try:
        ip = local_ip() or state["local_ip"]
        subnet = config.get("subnet") or (".".join(ip.split(".")[:3]) if ip else "")
        if not subnet: return
        hosts = ["%s.%d" % (subnet, i) for i in range(1, 255)]
        with ThreadPoolExecutor(64) as ex: rtt = dict(zip(hosts, ex.map(lambda h: ping(h, 1), hosts)))
        arp = arp_table()
        alive = {h: arp.get(h, "") for h in hosts if (rtt[h] is not None or h in arp) and h.startswith(subnet + ".")}
        with ThreadPoolExecutor(32) as ex: names = dict(zip(alive, ex.map(rdns, alive)))
        now = time.time()
        known = load_json("devices.json", {})
        first_run = not known
        for h, mac in alive.items():
            key = mac or "ip:" + h
            d = known.setdefault(key, {"first_seen": now, "name": "", "new": not first_run})
            d.update(mac=mac, ip=h, host=names.get(h, ""), last_seen=now, rtt=rtt[h],
                     vendor=OUI.get(mac[:8], d.get("vendor", "")) if mac else d.get("vendor", ""))
        for key, d in known.items():
            d["online"] = d.get("ip") in alive and now - d.get("last_seen", 0) < 5
        save_json("devices.json", known)
        with LOCK:
            state["devices"] = known
            state["scan"].update(last=now, subnet=subnet + ".0/24", duration=round(now - t0, 1))
    finally:
        with LOCK: state["scan"]["running"] = False


# ---------- background loops ----------
def sampler():
    while True:
        t0 = time.time()
        gw = default_gateway(); ip = local_ip()
        mons = [{"id": "gateway", "name": "Router", "type": "ping", "host": gw}] if gw else []
        mons += config.get("monitors", [])
        with ThreadPoolExecutor(16) as ex: results = list(ex.map(run_monitor, mons))
        sysd, net = system_stats(), net_rates()
        with LOCK:
            state.update(gateway=gw, local_ip=ip, system=sysd, net=net)
            seen = set()
            for m, r in zip(mons, results):
                seen.add(m["id"])
                e = state["monitors"].setdefault(m["id"], {"hist": []})
                e.update(name=m["name"], type=m.get("type", "ping"), host=m["host"], port=m.get("port"), ms=r, up=r is not None,
                         builtin=m["id"] == "gateway")
                e["hist"] = (e["hist"] + [r])[-HISTORY:]
            for k in list(state["monitors"]):
                if k not in seen: del state["monitors"][k]
            h = state.setdefault("net_hist", [])
            h.append([net.get("rx", 0), net.get("tx", 0)]); del h[:-HISTORY]
        time.sleep(max(1, SAMPLE_EVERY - (time.time() - t0)))

def scanner():
    time.sleep(3)
    while True:
        try: scan()
        except Exception as e: print("scan failed:", e, flush=True)
        time.sleep(SCAN_EVERY)


# ---------- UniFi (local controller API, read-only) ----------
def unifi_options():
    """Settings from the Home Assistant app options, or UNIFI_* environment variables when standalone."""
    o = load_json("options.json", {}) if DATA_DIR.startswith("/data") else {}
    def g(k, env, d=""): return o.get(k) if o.get(k) not in (None, "") else os.environ.get(env, d)
    return {"url": str(g("unifi_url", "UNIFI_URL")).rstrip("/"), "user": g("unifi_username", "UNIFI_USERNAME"),
            "password": g("unifi_password", "UNIFI_PASSWORD"), "site": g("unifi_site", "UNIFI_SITE", "default") or "default",
            "verify": str(g("unifi_verify_ssl", "UNIFI_VERIFY_SSL", "false")).lower() == "true",
            "os": str(g("unifi_os", "UNIFI_OS", "true")).lower() != "false"}

class UniFi:
    def __init__(self, o):
        self.o, self.csrf = o, None
        ctx = ssl.create_default_context()
        if not o["verify"]: ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        self.jar = cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar),
                                                  urllib.request.HTTPSHandler(context=ctx))

    def _open(self, url, body=None):
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", **({"X-CSRF-Token": self.csrf} if self.csrf else {})})
        with self.opener.open(req, timeout=10) as r:
            self.csrf = r.headers.get("X-Updated-CSRF-Token") or r.headers.get("X-CSRF-Token") or self.csrf
            return json.loads(r.read() or b"{}")

    def login(self):
        self.csrf = None
        self._open(self.o["url"] + ("/api/auth/login" if self.o["os"] else "/api/login"),
                   {"username": self.o["user"], "password": self.o["password"], "remember": True})

    def get(self, what, retry=True):
        base = self.o["url"] + ("/proxy/network" if self.o["os"] else "")
        try: return self._open("%s/api/s/%s/%s" % (base, self.o["site"], what)).get("data", [])
        except urllib.error.HTTPError as e:
            if e.code == 401 and retry: self.login(); return self.get(what, False)
            raise

    def snapshot(self):
        if not self.csrf and not self.jar: self.login()
        clients, devices, health = self.get("stat/sta"), self.get("stat/device"), self.get("stat/health")
        names = {d.get("mac"): d.get("name") or d.get("model") for d in devices}
        pick = lambda d, *k: {x: d.get(x) for x in k}
        return {
            "clients": [dict(pick(c, "mac", "ip", "is_wired", "essid", "signal", "rssi", "uptime", "oui", "last_seen", "sw_port"),
                             name=c.get("name") or "", host=c.get("hostname") or "",
                             via=names.get(c.get("ap_mac") if not c.get("is_wired") else c.get("sw_mac"), ""),
                             rx=c.get("rx_bytes-r", 0), tx=c.get("tx_bytes-r", 0)) for c in clients],
            "devices": [dict(pick(d, "mac", "ip", "model", "type", "version", "uptime", "num_sta", "adopted"),
                             name=d.get("name") or d.get("model") or d.get("mac"), up=d.get("state") == 1,
                             upgradable=bool(d.get("upgradable"))) for d in devices],
            "health": {h.get("subsystem"): pick(h, "status", "num_user", "num_adopted", "num_disconnected", "wan_ip", "latency",
                                                "xput_up", "xput_down", "speedtest_lastrun", "uptime") for h in health},
        }

def unifi_loop():
    o = unifi_options()
    if not (o["url"] and o["user"] and o["password"]): return
    api = UniFi(o)
    with LOCK: state["unifi"] = {"enabled": True, "ok": False, "error": "Connecting…", "last": 0}
    while True:
        try:
            snap = api.snapshot()
            with LOCK: state["unifi"] = dict(snap, enabled=True, ok=True, error="", last=time.time())
        except Exception as e:
            msg = "Login rejected: check the username and password" if getattr(e, "code", 0) in (400, 401, 403) else \
                  "Can't reach the controller: %s" % (getattr(e, "reason", None) or e)
            api.csrf = None; api.jar.clear()
            with LOCK: state["unifi"] = dict(state["unifi"], enabled=True, ok=False, error=msg)
            print("UniFi:", msg, flush=True)
        time.sleep(30)


# ---------- HTTP ----------
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype="application/json"):
        if not isinstance(body, bytes): body = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    def body(self):
        try: return json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError: return {}

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/api/status":
            with LOCK:
                self.send(200, dict(state, now=time.time(), uptime_app=time.time() - state["started"], config=config))
            return
        if p == "/": p = "/index.html"
        f = os.path.normpath(os.path.join(STATIC, p.lstrip("/")))
        if f.startswith(STATIC + os.sep) and os.path.isfile(f):
            with open(f, "rb") as fh: self.send(200, fh.read(), TYPES.get(os.path.splitext(f)[1], "application/octet-stream"))
        else: self.send(404, {"error": "not found"})

    def do_POST(self):
        p, b = self.path.split("?")[0], self.body()
        if p == "/api/scan":
            threading.Thread(target=scan, daemon=True).start(); return self.send(200, {"ok": True})
        if p == "/api/device":
            known = load_json("devices.json", {}); d = known.get(b.get("key"))
            if not d and str(b.get("key", "")).startswith("unifi:") and b.get("mac"):  # device only UniFi knows about
                d = known[b["key"][6:]] = {"first_seen": time.time(), "name": "", "new": False, "mac": b["mac"], "ip": b.get("ip", ""),
                                           "host": "", "last_seen": 0, "online": False}
                b["key"] = b["key"][6:]
            if not d: return self.send(404, {"error": "unknown device"})
            if "name" in b: d["name"] = str(b["name"])[:60]
            if "new" in b: d["new"] = bool(b["new"])
            if b.get("forget"): del known[b["key"]]
            save_json("devices.json", known)
            with LOCK: state["devices"] = known
            return self.send(200, {"ok": True})
        if p == "/api/monitor":
            host = str(b.get("host", "")).strip()
            typ = b.get("type") if b.get("type") in ("ping", "tcp", "http") else "ping"
            if not host: return self.send(400, {"error": "host required"})
            m = {"id": "m%d" % int(time.time() * 1000), "name": str(b.get("name") or host)[:40], "type": typ, "host": host}
            if typ == "tcp":
                try: m["port"] = int(b.get("port"))
                except (TypeError, ValueError): return self.send(400, {"error": "port required"})
            config.setdefault("monitors", []).append(m); save_json("config.json", config)
            return self.send(200, {"ok": True})
        if p == "/api/monitor/delete":
            config["monitors"] = [m for m in config.get("monitors", []) if m["id"] != b.get("id")]
            save_json("config.json", config); return self.send(200, {"ok": True})
        self.send(404, {"error": "not found"})


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8081)
    port = ap.parse_args().port
    config.update(load_json("config.json", DEFAULT_CONFIG))
    if not os.path.exists(_path("config.json")): save_json("config.json", config)
    state["devices"] = load_json("devices.json", {})
    for fn in (sampler, scanner, unifi_loop): threading.Thread(target=fn, daemon=True).start()
    print("Network dashboard running on http://0.0.0.0:%d" % port, flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()

if __name__ == "__main__":
    main()
