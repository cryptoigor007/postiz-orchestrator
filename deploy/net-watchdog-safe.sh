#!/bin/bash
# Безопасный сетевой watchdog (после инцидента 2026-09-20):
# НЕ трогает маршруты и НЕ перезапускает подключения — только power_save и tailscaled.
LOG=/var/log/net-watchdog.log
log(){ echo "$(date '+%F %T') $*" >> "$LOG"; }
iw dev wlp2s0 set power_save off 2>/dev/null || true
systemctl is-active --quiet tailscaled || { log "tailscaled упал — рестарт"; systemctl restart tailscaled; }
