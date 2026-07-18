#!/usr/bin/env bash
# start_server.sh
# Lance après chaque reboot Oracle Cloud si le service systemd n'est pas encore actif.
# Usage : bash ~/linkedin_automation/start_server.sh

set -e

echo "── Swap ──────────────────────────────"
if ! swapon --show | grep -q swapfile; then
    sudo swapon /swapfile && echo "Swap activé" || echo "Swap déjà actif ou absent"
else
    echo "Swap déjà actif"
fi
free -h | grep -E "Mem|Swap"

echo ""
echo "── Service systemd ───────────────────"
sudo systemctl daemon-reload
sudo systemctl enable linkedin_bot
sudo systemctl start linkedin_bot
sleep 2
sudo systemctl status linkedin_bot --no-pager -l

echo ""
echo "── Logs (10 dernières lignes) ────────"
journalctl -u linkedin_bot -n 10 --no-pager
