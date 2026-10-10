# Chore Chart

A touch-friendly chore chart for kids, shown on a Samsung Family Hub fridge
screen and hosted on a Raspberry Pi.

- **Fridge view** (`/`): one column per kid with today's chores. Kids tap a chore to check it off
  (tap again to undo). It shows weekly stars and a progress bar, and plays confetti when a kid finishes everything.
- **Settings** (`/admin`): add or remove kids and chores, choose which days each chore
  happens, set star values, and set an optional PIN. This page is easiest to use from your phone.
- Chores reset every day on their own. Stars count from Monday to Sunday.
- The server is plain Python 3 with no packages to install. It runs as a Home Assistant add-on or as a regular service on Raspberry Pi OS.

## 1. Install on the Raspberry Pi

### Home Assistant OS (add-on)

The chart runs as a Home Assistant add-on. Your kids, chores and check-offs are stored in the
add-on's own storage, so they survive restarts, updates and Home Assistant backups.

**Option A: local add-on (works while this repo is private)**

1. Install the **Samba share** add-on (or **Studio Code Server** / **Advanced SSH & Web Terminal**)
   so you can reach the `addons` folder on Home Assistant.
2. Copy this repo's `chore-chart/` folder into it, so you have `addons/chore-chart/config.yaml`.
3. Go to **Settings → Add-ons → Add-on Store**, open the **⋮** menu and choose **Check for updates**.
4. **Chore Chart** shows up under **Local add-ons**. Install it, then click **Start**.
   (The first install builds the image on the Pi, which takes a minute or two.)

**Option B: add-on repository (needs the repo to be public)**

1. **Settings → Add-ons → Add-on Store → ⋮ → Repositories**, and add
   `https://github.com/jonsiegel-ops/chore-calendar`
2. Install **Chore Chart** and click **Start**. Updates then appear in Home Assistant whenever
   `version` in `chore-chart/config.yaml` is bumped.

Either way, the chart is served at `http://<home-assistant-ip>:8080` (for example
`http://homeassistant.local:8080` from a phone). Use the IP address on the fridge.

### Raspberry Pi OS (no Home Assistant)

```bash
git clone https://github.com/jonsiegel-ops/chore-calendar.git
cd chore-calendar
./deploy/install.sh          # optional: ./deploy/install.sh 8080
```

This installs a systemd service, so the chart starts at boot and restarts if it crashes.

**Either way, give the Pi a fixed IP.** In your router's settings, add a DHCP reservation for it
so the fridge's bookmark keeps working. Not every built-in browser can resolve `.local` names.

## 2. Show it on the fridge

1. On the Family Hub screen, open the **Internet** (browser) app.
2. Go to `http://<pi-ip>:8080`.
3. Bookmark it, or add it to the home screen if your model offers that, so the kids can get back to it with one tap.

The page refreshes itself every 20 seconds and reloads overnight, so you can leave it open.
Changes made from a phone show up on the fridge automatically.

## 3. Customize

On your phone, open `http://<pi-ip>:8080/admin` and replace the placeholder kids
("Kid 1", "Kid 2") and chores with your own. Set a **Settings PIN** if you don't want
the kids editing chores from the fridge.

Chores reset at midnight in your Home Assistant time zone (on Raspberry Pi OS, the Pi's time zone).

## Running locally

```bash
python3 chore-chart/server.py --port 8080   # data goes in chore-chart/data/
```
