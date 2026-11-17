# Network Dashboard

Open the web page on port **8081** (for example `http://192.168.1.50:8081`).

- **Devices:** a ping sweep of your /24 subnet every 5 minutes (tap **Scan now** for an immediate one).
  Tap a device's name to give it a friendly name. New devices are flagged so you can spot strangers.
- **Internet & latency:** ping to your router, Cloudflare and Google, plus any monitors you add
  (ping, TCP port, or HTTP).
- **Pi stats:** CPU, memory, disk, temperature, uptime and live network throughput.

The app uses host networking so it can see your real LAN. There is no login, so only expose it on your home network.

## UniFi (optional)

Add your controller on the app's **Configuration** tab. The dashboard then shows your gateway, access points
and switches (status, clients, uptime, firmware updates), WAN health, and fills the Devices table with every
UniFi client, including whether it's on Wi-Fi (SSID, signal, which AP) or wired (which switch and port).

1. In UniFi, create a **local** user for this: **Settings → Admins & Users → Add admin**. Choose *Restrict to local access only*
   and give it **View Only** access to Network. Don't use your Ubiquiti account (2FA blocks it).
2. In the app configuration set:
   - **unifi_url**: for example `https://192.168.1.1` (UniFi OS consoles such as UDM, UDR, Cloud Gateway)
   - **unifi_username** / **unifi_password**: the local user from step 1
   - **unifi_site**: `default` unless you renamed your site
   - **unifi_os**: leave on for UDM/UDR/Cloud Gateway/Cloud Key Gen2+; turn **off** for a self-hosted controller (usually `https://host:8443`)
   - **unifi_verify_ssl**: leave off, since UniFi uses a self-signed certificate
3. Restart the app. The UniFi card shows the exact problem if it can't connect or log in.

Standalone, set `UNIFI_URL`, `UNIFI_USERNAME`, `UNIFI_PASSWORD` (and optionally `UNIFI_SITE`, `UNIFI_OS`, `UNIFI_VERIFY_SSL`).
