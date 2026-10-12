"""Fridge display extras: night mode and screensaver settings, countdowns,
screensaver photos and the weather."""
import datetime
import os
import re
import secrets
import threading
import time

import ha

DEFAULTS = {
    "night_mode": True,
    "night_start": "20:00",
    "night_end": "06:30",
    "fullscreen": True,
    "screensaver": True,
    "screensaver_minutes": 5,
    "photo_seconds": 15,
}

PHOTO_TYPES = {b"\xff\xd8\xff": ".jpg", b"\x89PNG": ".png", b"RIFF": ".webp", b"GIF8": ".gif"}
MAX_PHOTO_BYTES = 15 * 1024 * 1024
WEATHER_REFRESH_SECONDS = 10 * 60

_weather_cache = {}  # entity_id -> (fetched_at, result)
_weather_lock = threading.Lock()


# ---------------------------------------------------------------- settings

def _time(value, default):
    value = str(value or "")
    return value if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value) else default


def _int(value, default, lo, hi):
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def clean_display(raw):
    raw = raw if isinstance(raw, dict) else {}
    return {
        "night_mode": bool(raw.get("night_mode", DEFAULTS["night_mode"])),
        "night_start": _time(raw.get("night_start"), DEFAULTS["night_start"]),
        "night_end": _time(raw.get("night_end"), DEFAULTS["night_end"]),
        "fullscreen": bool(raw.get("fullscreen", DEFAULTS["fullscreen"])),
        "screensaver": bool(raw.get("screensaver", DEFAULTS["screensaver"])),
        "screensaver_minutes": _int(raw.get("screensaver_minutes"), DEFAULTS["screensaver_minutes"], 1, 120),
        "photo_seconds": _int(raw.get("photo_seconds"), DEFAULTS["photo_seconds"], 5, 600),
    }


def clean_countdowns(raw, pick_id):
    countdowns, ids = [], set()
    for c in raw if isinstance(raw, list) else []:
        title = str(c.get("title", "")).strip()
        if not title:
            raise ValueError("Every countdown needs a name")
        try:
            date = datetime.date.fromisoformat(str(c.get("date", "")))
        except ValueError:
            raise ValueError(f"Pick a date for the countdown “{title}”")
        countdowns.append({
            "id": pick_id(c.get("id"), title, ids),
            "title": title[:60],
            "emoji": str(c.get("emoji", ""))[:8],
            "date": date.isoformat(),
            "yearly": bool(c.get("yearly")),
        })
    return countdowns


def _next_date(countdown, today):
    date = datetime.date.fromisoformat(countdown["date"])
    if not countdown.get("yearly") or date >= today:
        return date
    for year in (today.year, today.year + 1):
        try:
            candidate = date.replace(year=year)
        except ValueError:  # 29 February in a non-leap year
            candidate = datetime.date(year, 2, 28)
        if candidate >= today:
            return candidate


def upcoming_countdowns(countdowns, today, limit=4):
    """The next few countdowns that haven't happened yet, soonest first."""
    upcoming = []
    for c in countdowns:
        date = _next_date(c, today)
        if date >= today:
            upcoming.append({"title": c["title"], "emoji": c["emoji"], "date": date.isoformat(),
                             "days": (date - today).days})
    return sorted(upcoming, key=lambda c: c["days"])[:limit]


# ---------------------------------------------------------------- photos

def list_photos(photo_dir):
    try:
        names = os.listdir(photo_dir)
    except FileNotFoundError:
        return []
    return sorted(n for n in names if os.path.splitext(n)[1].lower() in PHOTO_TYPES.values())


def photo_path(photo_dir, name):
    """Full path to a photo, or None if the name isn't one of ours (blocks ../ tricks)."""
    return os.path.join(photo_dir, name) if name in list_photos(photo_dir) else None


def save_photo(photo_dir, data):
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError("That photo is too large")
    ext = next((e for magic, e in PHOTO_TYPES.items() if data.startswith(magic)), None)
    if ext == ".webp" and data[8:12] != b"WEBP":
        ext = None
    if not ext:
        raise ValueError("Only JPEG, PNG, WebP and GIF photos are supported")
    os.makedirs(photo_dir, exist_ok=True)
    name = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3) + ext
    with open(os.path.join(photo_dir, name + ".tmp"), "wb") as f:
        f.write(data)
    os.replace(os.path.join(photo_dir, name + ".tmp"), os.path.join(photo_dir, name))
    return name


def delete_photo(photo_dir, name):
    path = photo_path(photo_dir, name)
    if path:
        os.remove(path)


# ---------------------------------------------------------------- weather

def weather(entity_id):
    """Current conditions and today's forecast from a Home Assistant weather entity."""
    if not entity_id or not ha.available():
        return None
    now = time.time()
    with _weather_lock:
        cached = _weather_cache.get(entity_id)
    if cached and now - cached[0] < WEATHER_REFRESH_SECONDS:
        return cached[1]

    try:
        state = ha.get("/states/" + entity_id)
    except Exception as e:
        print(f"Weather: couldn't read {entity_id} from Home Assistant: {e}", flush=True)
        return cached[1] if cached else None  # keep showing the last reading

    attrs = state.get("attributes", {})
    result = {
        "condition": state.get("state"),
        "temperature": attrs.get("temperature"),
        "unit": attrs.get("temperature_unit", ""),
        "high": None,
        "low": None,
    }
    try:
        # Forecasts come from a service call that returns data (Home Assistant 2023.9+).
        res = ha.post("/services/weather/get_forecasts?return_response", {"entity_id": entity_id, "type": "daily"})
        forecast = (res.get("service_response") or {}).get(entity_id, {}).get("forecast") or []
        if forecast:
            result["high"] = forecast[0].get("temperature")
            result["low"] = forecast[0].get("templow")
    except Exception as e:
        print(f"Weather: no daily forecast for {entity_id}: {e}", flush=True)

    with _weather_lock:
        _weather_cache[entity_id] = (now, result)
    return result
