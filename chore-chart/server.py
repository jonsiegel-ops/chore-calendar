#!/usr/bin/env python3
"""Chore chart server.

Serves the fridge display (static/) and a small JSON API. Uses only the
Python standard library so it runs on a stock Raspberry Pi OS install.

Data lives in data/config.json (kids + chores) and data/state.json (what has
been checked off, keyed by date).
"""
import argparse
import datetime
import json
import os
import re
import shutil
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(ROOT, "static")
DATA_DIR = os.environ.get("CHORE_DATA_DIR", os.path.join(ROOT, "data"))
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
EXAMPLE_CONFIG = os.path.join(ROOT, "config.example.json")

KEEP_DAYS = 90  # how much check-off history to keep
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

lock = threading.Lock()


# ---------------------------------------------------------------- storage

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)  # atomic, so a power cut can't leave half a file


def load_config():
    return load_json(CONFIG_PATH, {"title": "Chore Chart", "kids": [], "chores": []})


def load_state():
    return load_json(STATE_PATH, {"done": {}})


def prune(state, today):
    cutoff = (today - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    state["done"] = {d: v for d, v in state["done"].items() if d >= cutoff}


# ---------------------------------------------------------------- board

def chores_for(config, kid_id, day):
    return [
        c for c in config["chores"]
        if kid_id in c.get("kids", []) and day.weekday() in c.get("days", range(7))
    ]


def build_board(config, state, day):
    week_start = day - datetime.timedelta(days=day.weekday())
    points = {c["id"]: c.get("stars", 1) for c in config["chores"]}
    done_today = state["done"].get(day.isoformat(), {})

    kids = []
    for kid in config["kids"]:
        done_ids = set(done_today.get(kid["id"], []))
        stars_week = 0
        for date, by_kid in state["done"].items():
            if week_start.isoformat() <= date <= day.isoformat():
                stars_week += sum(points.get(cid, 1) for cid in by_kid.get(kid["id"], []))
        kids.append({
            "id": kid["id"],
            "name": kid["name"],
            "emoji": kid.get("emoji", ""),
            "color": kid.get("color", "#4f7cff"),
            "stars_week": stars_week,
            "chores": [
                {
                    "id": c["id"],
                    "title": c["title"],
                    "emoji": c.get("emoji", ""),
                    "stars": c.get("stars", 1),
                    "done": c["id"] in done_ids,
                }
                for c in chores_for(config, kid["id"], day)
            ],
        })
    return {
        "title": config.get("title", "Chore Chart"),
        "date": day.isoformat(),
        "weekday": WEEKDAYS[day.weekday()],
        "kids": kids,
    }


def build_stats(config, state, any_day, today):
    """Chores done per kid per day for the Monday-Sunday week containing any_day."""
    week_start = any_day - datetime.timedelta(days=any_day.weekday())
    days = [week_start + datetime.timedelta(days=i) for i in range(7)]
    points = {c["id"]: c.get("stars", 1) for c in config["chores"]}
    oldest = today - datetime.timedelta(days=KEEP_DAYS)

    kids = []
    for kid in config["kids"]:
        per_day = []
        for d in days:
            done = state["done"].get(d.isoformat(), {}).get(kid["id"], [])
            per_day.append({
                "done": len(done),
                "stars": sum(points.get(cid, 1) for cid in done),
                # Uses today's chore list, so edits to chores also change past weeks' totals.
                "assigned": len(chores_for(config, kid["id"], d)) if d <= today else None,
            })
        kids.append({
            "id": kid["id"],
            "name": kid["name"],
            "emoji": kid.get("emoji", ""),
            "color": kid.get("color", "#4f7cff"),
            "done": sum(p["done"] for p in per_day),
            "assigned": sum(p["assigned"] or 0 for p in per_day),
            "stars": sum(p["stars"] for p in per_day),
            "days": per_day,
        })

    return {
        "title": config.get("title", "Chore Chart"),
        "week_start": week_start.isoformat(),
        "is_current": week_start <= today <= days[-1],
        "has_prev": week_start - datetime.timedelta(days=1) >= oldest,
        "has_next": days[-1] < today,
        "days": [
            {"date": d.isoformat(), "label": WEEKDAYS[d.weekday()][:3], "today": d == today, "future": d > today}
            for d in days
        ],
        "kids": kids,
    }


def toggle(kid_id, chore_id):
    with lock:
        config, state = load_config(), load_state()
        day = datetime.date.today()
        if chore_id not in {c["id"] for c in chores_for(config, kid_id, day)}:
            raise ValueError("That chore isn't assigned to that kid today")
        by_kid = state["done"].setdefault(day.isoformat(), {})
        done = by_kid.setdefault(kid_id, [])
        if chore_id in done:
            done.remove(chore_id)
        else:
            done.append(chore_id)
        prune(state, day)
        save_json(STATE_PATH, state)
        return build_board(config, state, day)


# ---------------------------------------------------------------- config validation

def slugify(text, taken):
    base = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-") or "item"
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    taken.add(slug)
    return slug


def pick_id(given, label, taken):
    """Keep an existing id if it's valid and unique, otherwise make one from the label."""
    if isinstance(given, str) and re.fullmatch(r"[a-z0-9-]+", given) and given not in taken:
        taken.add(given)
        return given
    return slugify(label, taken)


def clean_config(raw):
    """Validate an edited config from the settings page, filling in ids."""
    if not isinstance(raw, dict):
        raise ValueError("Config must be an object")

    kids, kid_ids = [], set()
    for k in raw.get("kids", []):
        name = str(k.get("name", "")).strip()
        if not name:
            raise ValueError("Every kid needs a name")
        kid_id = pick_id(k.get("id"), name, kid_ids)
        color = str(k.get("color", "#4f7cff"))
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            color = "#4f7cff"
        kids.append({"id": kid_id, "name": name[:40], "emoji": str(k.get("emoji", ""))[:8], "color": color})

    chores, chore_ids = [], set()
    for c in raw.get("chores", []):
        title = str(c.get("title", "")).strip()
        if not title:
            raise ValueError("Every chore needs a name")
        chore_id = pick_id(c.get("id"), title, chore_ids)
        days = sorted({int(d) for d in c.get("days", range(7)) if 0 <= int(d) <= 6})
        try:
            stars = max(1, min(10, int(c.get("stars", 1))))
        except (TypeError, ValueError):
            stars = 1
        chores.append({
            "id": chore_id,
            "title": title[:60],
            "emoji": str(c.get("emoji", ""))[:8],
            "stars": stars,
            "kids": [k for k in c.get("kids", []) if k in kid_ids],
            "days": days,
        })

    return {
        "title": str(raw.get("title", "Chore Chart")).strip()[:60] or "Chore Chart",
        "admin_pin": str(raw.get("admin_pin", "")).strip()[:20],
        "kids": kids,
        "chores": chores,
    }


# ---------------------------------------------------------------- http

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def end_headers(self):
        # The fridge browser should always pick up new versions of the page.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # keep the systemd journal quiet

    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > 256 * 1024:
            raise ValueError("Request too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def admin_ok(self, config):
        pin = config.get("admin_pin", "")
        return not pin or self.headers.get("X-Admin-Pin", "") == pin

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/board":
            with lock:
                self.send_json(build_board(load_config(), load_state(), datetime.date.today()))
        elif path == "/api/stats":
            today = datetime.date.today()
            week = parse_qs(urlparse(self.path).query).get("week", [""])[0]
            try:
                day = datetime.date.fromisoformat(week) if week else today
            except ValueError:
                return self.send_json({"error": "Bad week date"}, 400)
            with lock:
                self.send_json(build_stats(load_config(), load_state(), day, today))
        elif path == "/api/config":
            config = load_config()
            if not self.admin_ok(config):
                return self.send_json({"error": "PIN required"}, 401)
            self.send_json(config)
        elif path in ("/admin", "/settings"):
            self.path = "/admin.html"
            super().do_GET()
        elif path == "/stats":
            self.path = "/stats.html"
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/toggle":
                body = self.read_json()
                self.send_json(toggle(str(body.get("kid")), str(body.get("chore"))))
            else:
                self.send_json({"error": "Not found"}, 404)
        except ValueError as e:
            self.send_json({"error": str(e)}, 400)

    def do_PUT(self):
        path = urlparse(self.path).path
        if path != "/api/config":
            return self.send_json({"error": "Not found"}, 404)
        try:
            with lock:
                if not self.admin_ok(load_config()):
                    return self.send_json({"error": "PIN required"}, 401)
                config = clean_config(self.read_json())
                save_json(CONFIG_PATH, config)
            self.send_json(config)
        except (ValueError, TypeError) as e:
            self.send_json({"error": str(e)}, 400)


def main():
    parser = argparse.ArgumentParser(description="Kids chore chart server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        shutil.copy(EXAMPLE_CONFIG, CONFIG_PATH)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Chore chart running on http://{args.host}:{args.port}  (settings at /admin)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
