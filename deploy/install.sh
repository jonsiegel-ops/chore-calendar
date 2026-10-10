#!/usr/bin/env bash
# Installs the chore chart as a systemd service on a Raspberry Pi running
# Raspberry Pi OS. (On Home Assistant OS, install it as an add-on instead.)
# Run from the repo:  ./deploy/install.sh [port]
set -euo pipefail

PORT="${1:-8080}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$REPO/chore-chart"
USER_NAME="$(id -un)"

sed -e "s|__USER__|$USER_NAME|g" -e "s|__DIR__|$DIR|g" -e "s|__PORT__|$PORT|g" \
  "$REPO/deploy/chore-chart.service" | sudo tee /etc/systemd/system/chore-chart.service >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now chore-chart
sudo systemctl restart chore-chart

IP="$(hostname -I | awk '{print $1}')"
echo
echo "Chore chart is running."
echo "  Fridge:   http://$IP:$PORT"
echo "  Settings: http://$IP:$PORT/admin"
