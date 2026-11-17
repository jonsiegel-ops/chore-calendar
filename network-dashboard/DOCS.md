# Network Dashboard

A live dashboard built entirely from your **UniFi controller** (tested design target: Cloud Gateway Fiber).
Nothing is scanned or pinged from the Pi, and the app only reads from the controller.

Open the web page on port **8081** (for example `http://192.168.1.50:8081`).

## What it shows
- **Internet:** WAN status and IP, download and upload as measured by the gateway (with history), internet latency, drops and your last speed test.
- **Gateway:** model, firmware, uptime, CPU, memory, temperature and port link speeds.
- **UniFi devices:** gateway, access points and switches with status, client counts, CPU/memory, uptime and firmware updates.
- **Clients:** everyone online with their Wi-Fi network, access point, channel and signal, or switch and port if wired, plus live and total traffic. Switch to *Online + offline* to see recent devices that have left. Clients first seen in the last 7 days get a **NEW** badge (tap it to dismiss).
- **Busiest clients, Wi-Fi networks, Networks (VLANs) and recent controller events.**

To rename a device, rename it in UniFi; the dashboard picks it up.

## Setup
1. In UniFi, create a **local** user: **Settings → Admins & Users → Add admin**. Choose *Restrict to local access only*
   and give it **View Only** access to Network. Don't use your Ubiquiti account (2FA blocks it).
2. On this app's **Configuration** tab set:
   - **unifi_url:** for example `https://192.168.1.1`
   - **unifi_username** / **unifi_password:** the local user from step 1
   - **unifi_site:** `default` unless you renamed your site
   - **unifi_os:** leave on for a Cloud Gateway, UDM or UDR; turn **off** only for a self-hosted controller (usually `https://host:8443`)
   - **unifi_verify_ssl:** leave off, since UniFi uses a self-signed certificate
3. Restart the app. If it can't connect or log in, the page says exactly why.

Standalone, set `UNIFI_URL`, `UNIFI_USERNAME`, `UNIFI_PASSWORD` (and optionally `UNIFI_SITE`, `UNIFI_OS`, `UNIFI_VERIFY_SSL`).
There is no login on the dashboard itself, so only expose it on your home network.
