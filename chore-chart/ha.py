"""Talking to Home Assistant's API from inside the add-on.

The Supervisor gives every add-on with `homeassistant_api: true` a token and a
proxy to Home Assistant's REST API, so no long-lived access token is needed.
"""
import json
import os
import urllib.parse
import urllib.request

TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
API = os.environ.get("HA_API_URL", "http://supervisor/core/api")
TIMEOUT = 20


def available():
    return bool(TOKEN)


def get(path, params=None):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return json.load(res)


def post(path, body):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
        return json.load(res)


def entities(domain):
    """Entities in one domain (e.g. "weather"), for pickers on the settings page."""
    if not available():
        return []
    return [
        {"entity_id": s["entity_id"], "name": s.get("attributes", {}).get("friendly_name") or s["entity_id"]}
        for s in get("/states")
        if s.get("entity_id", "").startswith(domain + ".")
    ]
