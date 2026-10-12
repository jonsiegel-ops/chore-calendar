"""Calendar events from two kinds of source, turned into a day-by-day agenda.

- "ical": an iCal link, such as an iCloud public calendar. Fetched at most every
  REFRESH_SECONDS and saved to disk, so the fridge keeps showing the last good
  copy if iCloud or the internet is unreachable.
- "ha": a Home Assistant calendar entity, read through Home Assistant's API.
  This is how private iCloud calendars work: Home Assistant's CalDAV
  integration holds the Apple credentials, and this app never sees them.
"""
import datetime
import hashlib
import os
import threading
import time
import urllib.parse
import urllib.request

import ha

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
_ha_last = {}  # calendar id -> (entity_id, events) from the last successful read
_cache_lock = threading.Lock()


class SourceError(Exception):
    pass


def normalize_url(url):
    """iCloud hands out webcal:// links; they're plain HTTPS underneath."""
    url = url.strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    return url


def _local(dt):
    """Convert to the server's local time; floating (no time zone) times are already local."""
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt


# ---------------------------------------------------------------- iCal links

def _fetch_ical(cal, cache_dir):
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


def _ical_bounds(ev):
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


def _ical_events(cal, cache_dir, first, last, warnings):
    if icalendar is None:
        raise SourceError("Calendar support isn't installed (missing Python packages).")
    entry = _fetch_ical(cal, cache_dir)
    if entry["error"]:
        warnings.append(f"Couldn't update “{cal['name']}”"
                        + (" — showing the last saved copy." if entry["text"] else "."))
    if not entry["text"]:
        return []
    try:
        parsed = icalendar.Calendar.from_ical(entry["text"])
        found = recurring_ical_events.of(parsed).between(first, last + datetime.timedelta(days=1))
    except Exception:
        raise SourceError(f"Couldn't read “{cal['name']}”.")
    events = []
    for ev in found:
        start, end, all_day = _ical_bounds(ev)
        events.append((start, end, all_day, str(ev.get("SUMMARY") or ""), str(ev.get("LOCATION") or "")))
    return events


# ---------------------------------------------------------------- Home Assistant

def ha_calendars():
    """Calendar entities in Home Assistant, for the settings page."""
    if not ha.available():
        return []
    return [{"entity_id": c["entity_id"], "name": c.get("name") or c["entity_id"]} for c in ha.get("/calendars")]


def _ha_time(value):
    """Home Assistant gives {"dateTime": iso} for timed events and {"date": iso} for all-day ones."""
    if isinstance(value, dict) and value.get("dateTime"):
        return _local(datetime.datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))), False
    if isinstance(value, dict) and value.get("date"):
        return datetime.date.fromisoformat(value["date"]), True
    raise ValueError(f"unexpected time {value!r}")


def _ha_events(cal, first, last, warnings):
    if not ha.available():
        raise SourceError(f"“{cal['name']}” is a Home Assistant calendar, which only works when running as a Home Assistant app.")
    start = datetime.datetime.combine(first, datetime.time()).astimezone()
    end = datetime.datetime.combine(last + datetime.timedelta(days=1), datetime.time()).astimezone()
    try:
        found = ha.get("/calendars/" + urllib.parse.quote(cal["entity_id"]),
                        {"start": start.isoformat(), "end": end.isoformat()})
    except Exception as e:
        # Home Assistant restarts during updates; keep showing what we had.
        print(f"Calendar “{cal['name']}”: couldn't read from Home Assistant: {e}", flush=True)
        saved = _ha_last.get(cal["id"])
        if saved and saved[0] == cal["entity_id"]:
            warnings.append(f"Couldn't update “{cal['name']}” — showing the last saved copy.")
            return saved[1]
        raise SourceError(f"Couldn't get “{cal['name']}” from Home Assistant.")
    events = []
    for ev in found:
        try:
            s, all_day = _ha_time(ev.get("start"))
            e, _ = _ha_time(ev.get("end"))
        except (ValueError, TypeError):
            continue
        if all_day:
            e = e if e > s else s + datetime.timedelta(days=1)
        events.append((s, max(e, s), all_day, str(ev.get("summary") or ""), str(ev.get("location") or "")))
    _ha_last[cal["id"]] = (cal["entity_id"], events)
    return events


# ---------------------------------------------------------------- agenda

def agenda(calendars, cache_dir, days=14):
    today = datetime.date.today()
    span = [today + datetime.timedelta(days=i) for i in range(days)]
    by_day = {d: [] for d in span}
    warnings = []

    for cal in calendars:
        try:
            if cal.get("source") == "ha":
                events = _ha_events(cal, span[0], span[-1], warnings)
            else:
                events = _ical_events(cal, cache_dir, span[0], span[-1], warnings)
        except SourceError as e:
            warnings.append(str(e))
            continue

        for start, end, all_day, title, location in events:
            base = {"title": title or "(No title)", "location": location, "calendar": cal["name"], "color": cal["color"]}
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
