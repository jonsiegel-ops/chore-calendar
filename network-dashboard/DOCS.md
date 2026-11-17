# Network Dashboard

Open the web page on port **8081** (for example `http://192.168.1.50:8081`).

- **Devices:** a ping sweep of your /24 subnet every 5 minutes (tap **Scan now** for an immediate one).
  Tap a device's name to give it a friendly name. New devices are flagged so you can spot strangers.
- **Internet & latency:** ping to your router, Cloudflare and Google, plus any monitors you add
  (ping, TCP port, or HTTP).
- **Pi stats:** CPU, memory, disk, temperature, uptime and live network throughput.

The app uses host networking so it can see your real LAN. There is no login, so only expose it on your home network.
