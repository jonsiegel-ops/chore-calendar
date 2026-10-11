"""Calendar feeds (e.g. an iCloud public calendar link) turned into a day-by-day agenda.

Feeds are fetched at most every REFRESH_SECONDS and saved to disk, so the fridge
keeps showing the last good copy if iCloud or the internet is unreachable.
"""
import datetime
import hashlib
import os
import threading
import time
import urllib.request

try:
    import icalendar
    import recurring_ical_events
except ImportError:  # running without requirements.txt installed
    icalendar = recurring_ical_events = None

REFRESH_SECONDS = 15 * 60
RETRY_SECONDS = 2 * 60
FETCH_TIMEOUT = 20
MAX_FEED_BYTES = 5 * 1024 * 1024
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

_cache = {}  # calendar id -> {"url", "text", "next_fetch", "error"}
_cache_lock = threading.Lock()


def normalize_url(url):
    """iCloud hands out webcal:// links; they're plain HTTPS underneath."""
    url = url.strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    return url


def _fetch(cal, cache_dir):
    url = normalize_url(cal["url"])
    cache_path = os.path.join(cache_dir, hashlib.sha1(url.encode()).hexdigest()[:16] + ".ics")
    now = time.time()
    with _cache_lock:
        entry = _cache.get(cal["id"])
    if entry and entry["url"] == url and now < entry["next_fetch"]:
        return entry

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "chore-chart"})
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as res:
            text = res.read(MAX_FEED_BYTES + 1)
        if len(text) > MAX_FEED_BYTES:
            raise ValueError("calendar is too large")
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path + ".tmp", "wb") as f:
            f.write(text)
        os.replace(cache_path + ".tmp", cache_path)
        entry = {"url": url, "text": text, "next_fetch": now + REFRESH_SECONDS, "error": None}
    except Exception as e:  # network errors, HTTP errors, bad URLs
        print(f"Calendar “{cal['name']}”: couldn't fetch feed: {e}", flush=True)
        text = entry["text"] if entry and entry["url"] == url else None
        if text is None and os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                text = f.read()
        entry = {"url": url, "text": text, "next_fetch": now + RETRY_SECONDS, "error": str(e)}

    with _cache_lock:
        _cache[cal["id"]] = entry
    return entry


def _local(dt):
    """Convert to the server's local time; floating (no time zone) times are already local."""
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt


def _event_bounds(ev):
    start = ev.get("DTSTART").dt
    end = ev.get("DTEND").dt if ev.get("DTEND") else None
    if end is None and ev.get("DURATION"):
        end = start + ev.get("DURATION").dt
    if isinstance(start, datetime.datetime):
        start = _local(start)
        end = _local(end) if isinstance(end, datetime.datetime) else start
        return start, max(end, start), False
    end = end if isinstance(end, datetime.date) and end > start else start + datetime.timedelta(days=1)
    return start, end, True


def agenda(calendars, cache_dir, days=14):
    today = datetime.date.today()
    span = [today + datetime.timedelta(days=i) for i in range(days)]
    by_day = {d: [] for d in span}
    warnings = []

    if calendars and icalendar is None:
        warnings.append("Calendar support isn't installed (missing Python packages).")
        calendars = []

    for cal in calendars:
        entry = _fetch(cal, cache_dir)
        if entry["error"]:
            warnings.append(f"Couldn't update “{cal['name']}”"
                            + (" — showing the last saved copy." if entry["text"] else "."))
        if not entry["text"]:
            continue
        try:
            parsed = icalendar.Calendar.from_ical(entry["text"])
            events = recurring_ical_events.of(parsed).between(span[0], span[-1] + datetime.timedelta(days=1))
        except Exception:
            warnings.append(f"Couldn't read “{cal['name']}”.")
            continue

        for ev in events:
            start, end, all_day = _event_bounds(ev)
            base = {
                "title": str(ev.get("SUMMARY") or "(No title)"),
                "location": str(ev.get("LOCATION") or ""),
                "calendar": cal["name"],
                "color": cal["color"],
            }
            if all_day:
                d = start
                while d < end:
                    if d in by_day:
                        by_day[d].append(dict(base, all_day=True, start=None, end=None))
                    d += datetime.timedelta(days=1)
                continue
            # Timed events that run past midnight show "until <time>" on their last day
            # and "all day" on any full days in between.
            last = (end - datetime.timedelta(microseconds=1)).date() if end > start else start.date()
            d = start.date()
            while d <= last:
                if d in by_day:
                    first, final = d == start.date(), d == last
                    by_day[d].append(dict(
                        base,
                        all_day=not first and not final,
                        start=start.strftime("%H:%M") if first else None,
                        end=end.strftime("%H:%M") if final and end > start else None,
                    ))
                d += datetime.timedelta(days=1)

    return {
        "configured": bool(calendars),
        "calendars": [{"name": c["name"], "color": c["color"]} for c in calendars],
        "warnings": warnings,
        "days": [
            {
                "date": d.isoformat(),
                "weekday": WEEKDAYS[d.weekday()],
                "events": sorted(by_day[d], key=lambda e: (not e["all_day"], e["start"] or "", e["title"].lower())),
            }
            for d in span
        ],
    }
