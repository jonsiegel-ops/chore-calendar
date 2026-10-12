# Chore Chart

A touch-friendly chore chart for kids, shown on a Samsung Family Hub fridge
screen and hosted on a Raspberry Pi.

- **Fridge view** (`/`): one column per kid with today's chores. Kids tap a chore to check it off
  (tap again to undo). It shows weekly stars and a progress bar, and plays confetti when a kid finishes everything.
  Once a calendar is set up, today's events appear in a panel above the chores (finished ones fade out);
  tap it to open the full calendar.
- **Weekly stats** (`/stats`, the **📊 This week** button): how many chores each kid has done this week,
  out of how many so far, with a day-by-day bar chart. Use the arrows to look back at earlier weeks
  (history is kept for about 90 days). The screen returns to the chart after 3 minutes untouched.
- **Calendar** (`/calendar`, the **📅 Calendar** button): the next two weeks from one or more
  calendars. Use private iCloud calendars through Home Assistant, or any public calendar link.
  See [Adding a private iCloud calendar](#adding-a-private-icloud-calendar).
- **Fridge extras** (all under **Fridge display**, **Countdowns** and **Weather** in Settings):
  - **Weather:** the current temperature and today's high and low in the Today card, from a Home Assistant weather entity.
  - **Countdowns:** chips like "🎂 Shai's birthday · 12 days". Mark birthdays and holidays **Every year**.
  - **Night mode:** dark colors between the times you choose (8 pm to 6:30 am by default).
  - **Photo screensaver:** after a few idle minutes, a slideshow of your photos with a big clock. Tap to go back.
    Add photos from your phone on the Settings page; they're shrunk before uploading.
  - **Full screen:** the first tap on each page hides the browser's address bar and toolbar
    (if the browser allows it; moving to another page leaves full screen until the next tap).
- **Settings** (`/admin`, the **⚙️** button): add or remove kids and chores, choose which days each chore
  happens, set star values, and set an optional PIN. This page is easiest to use from your phone.
- Chores reset every day on their own. Stars count from Monday to Sunday.
- The server is plain Python 3 (the calendar uses two small packages, installed for you). It runs as a Home Assistant add-on or as a regular service on Raspberry Pi OS.

## Install on Home Assistant OS

The chart runs as a Home Assistant app. Since Home Assistant 2026.2, add-ons are called
**Apps**; on older versions, read "Add-on" wherever these steps say "App".
Your kids, chores and check-offs are stored in the app's own storage, so they survive
restarts, updates and Home Assistant backups.

### Step 1: Add this repository to Home Assistant

1. On a computer or phone, open Home Assistant (usually `http://homeassistant.local:8123`).
2. Go to **Settings → Apps**, and open the app store (on older versions: **Settings → Add-ons → Add-on Store**).
3. Click the **⋮** menu in the top-right corner and choose **Repositories**.
4. Paste `https://github.com/jonsiegel-ops/chore-calendar`, click **Add**, then **Close**.

[![Add repository to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fjonsiegel-ops%2Fchore-calendar)

(Or use this button, which opens the same screen in your Home Assistant.)

### Step 2: Install and start the app

1. Refresh the store page. If **Chore Chart** doesn't appear, open **⋮ → Check for updates**.
2. Scroll down to the **Chore Chart add-ons** section and click **Chore Chart**.
3. Click **Install**. Home Assistant builds the app on the Pi, which takes a few minutes the first time.
4. On the app's **Info** tab, make sure **Start on boot** is on, and turn on **Watchdog**
   so Home Assistant restarts the app if it ever crashes.
5. Click **Start**.
6. Open the **Log** tab. You should see `Chore chart running on http://0.0.0.0:8080`.

### Step 3: Find (and lock in) the Pi's IP address

1. Go to **Settings → System → Network** and note the **IPv4** address, for example `192.168.1.50`.
2. Make sure that address never changes, or the fridge's bookmark will stop working. Either:
   - add a **DHCP reservation** for the Pi in your router's settings (recommended), or
   - set the IPv4 address to **Static** on that same Network page.

### Step 4: Set up your kids and chores (on your phone)

1. Connect your phone to your home Wi-Fi and open `http://192.168.1.50:8080/admin`, using your Pi's IP.
2. Rename "Kid 1" and "Kid 2", and pick an emoji and color for each kid.
3. Edit the sample chores. For each one, choose who does it, which days it happens, and how many stars it's worth.
4. Optionally, set a **Settings PIN** so the kids can't edit their own chores from the fridge.
5. Click **Save**.

### Step 5: Put it on the fridge

1. On the Family Hub screen, open the **Internet** app.
2. In the address bar, type the full address, including `http://`, for example `http://192.168.1.50:8080`.
3. Bookmark the page (and add it to the home screen if your model offers that) so the kids can open it with one tap.

The page refreshes itself every 20 seconds and reloads overnight, so you can leave it open.
Changes made on a phone show up on the fridge automatically.

### Adding a private iCloud calendar

Home Assistant connects to iCloud and the chart reads the calendars from Home Assistant,
so your Apple credentials stay in Home Assistant and the chart never sees them.

**1. Create an app-specific password for Home Assistant**

1. Sign in at [account.apple.com](https://account.apple.com) with your Apple ID.
2. Under **Sign-In and Security**, choose **App-Specific Passwords**, then **+**.
3. Name it `Home Assistant` and copy the password Apple shows you (it's only shown once).

This password only works for things like calendars and contacts, not for signing in to your Apple account.
You can revoke it on the same page at any time.

**2. Add iCloud to Home Assistant**

1. Go to **Settings → Devices & services → Add integration** and choose **CalDAV**.
2. Enter:
   - **URL:** `https://caldav.icloud.com`
   - **Username:** your Apple ID email address
   - **Password:** the app-specific password from step 1
3. Submit. Your iCloud calendars appear in Home Assistant as `calendar.…` entities.

**3. Show them on the fridge**

1. Open the chart's settings (`/admin`, or the ⚙️ button) and scroll to **Calendars**.
2. Tap **+ Home Assistant calendar**, pick a calendar, choose a color, and tap **Save**.
   Repeat for each calendar you want on the fridge.

New events can take up to about 15 minutes to appear, since Home Assistant checks iCloud periodically.

### Using a public calendar link instead

This works without Home Assistant, but anyone who has the link can see the calendar.

1. On your iPhone, open the **Calendar** app and tap **Calendars**.
2. Tap the **ⓘ** next to the calendar, turn on **Public Calendar**, tap **Share Link…**, then **Copy**.
3. In the chart's settings under **Calendars**, tap **+ Calendar link**, paste the link, name it and tap **Save**.

To stop sharing, turn **Public Calendar** off again.

### Updating

When the app changes, Home Assistant shows an update under **Settings → Updates** (and on the app's page).
Click **Update**. Your kids, chores and stars are kept.

### Troubleshooting

| Problem | Fix |
| --- | --- |
| The repository won't add | Check the URL exactly as written above, with no `.git` on the end. |
| Chore Chart isn't in the store | Refresh the page, or use **⋮ → Check for updates**. |
| Install fails | Check **Settings → System → Logs**, choosing **Supervisor** in the log picker. |
| The page doesn't load on the fridge | Type `http://` in full, and make sure the fridge is on the same Wi-Fi network as the Pi, not a guest network. |
| Port 8080 is already in use | Change the port on the app's **Configuration** tab under **Network**, then use the new port in the address. |
| The calendar says "Couldn't update" | For a Home Assistant calendar, check that the CalDAV integration is working under **Settings → Devices & services**. For a link, check that **Public Calendar** is still on. The app's **Log** tab shows the exact error. The fridge keeps showing the last copy it got. |
| **+ Home Assistant calendar** is missing in Settings | It only appears when the chart runs as a Home Assistant app. Update the app to 1.3.0 or later and restart it. |
| Chores reset at the wrong time | Set your time zone in **Settings → System → General**, then restart the app. |

## Install on Raspberry Pi OS (no Home Assistant)

```bash
git clone https://github.com/jonsiegel-ops/chore-calendar.git
cd chore-calendar
./deploy/install.sh          # optional: ./deploy/install.sh 8080
```

This installs a systemd service that starts at boot. Then follow steps 3–5 above,
using the address the script prints.

## Running locally

```bash
pip install -r chore-chart/requirements.txt  # for the calendar view
python3 chore-chart/server.py --port 8080   # data goes in chore-chart/data/
```
