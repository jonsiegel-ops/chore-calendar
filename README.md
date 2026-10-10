# Chore Chart

A touch-friendly chore chart for kids, shown on a Samsung Family Hub fridge
screen and hosted on a Raspberry Pi.

- **Fridge view** (`/`): one column per kid with today's chores. Kids tap a chore to check it off
  (tap again to undo). It shows weekly stars and a progress bar, and plays confetti when a kid finishes everything.
- **Settings** (`/admin`): add or remove kids and chores, choose which days each chore
  happens, set star values, and set an optional PIN. This page is easiest to use from your phone.
- Chores reset every day on their own. Stars count from Monday to Sunday.
- Everything is stored in `data/` on the Pi. The server is plain Python 3 with no packages to install.

## 1. Set up the Raspberry Pi

Any Pi running Raspberry Pi OS works, since Python 3 is preinstalled.

```bash
git clone https://github.com/jonsiegel-ops/chore-calendar.git
cd chore-calendar
./deploy/install.sh          # optional: ./deploy/install.sh 8080
```

This installs a systemd service, so the chart starts at boot and restarts if it crashes.
At the end it prints the address, for example `http://192.168.1.50:8080`.

**Give the Pi a fixed IP.** In your router's settings, add a DHCP reservation for the Pi.
Otherwise the address the fridge uses can change after a reboot. You could use the
`raspberrypi.local` hostname instead, but not every built-in browser can resolve `.local` names.

Useful commands:

```bash
sudo systemctl status chore-chart                # is it running?
journalctl -u chore-chart -f                     # logs
git pull && sudo systemctl restart chore-chart   # update
```

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

You can also edit `data/config.json` on the Pi directly. Days are numbered 0 = Monday through 6 = Sunday.

## Running locally

```bash
python3 server.py --port 8080
```
