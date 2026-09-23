#!/bin/bash
# Безопасный сетевой watchdog: только наблюдение и идемпотентная сверка LAN-маршрута.
# Ставится в /usr/local/sbin/net-watchdog.sh (таймер net-watchdog.timer, каждые 60с).
LOG=/var/log/net-watchdog.log
log(){ echo "$(date '+%F %T') $*" >> "$LOG"; }
iw dev wlp2s0 set power_save off 2>/dev/null || true
systemctl is-active --quiet tailscaled || { log "tailscaled упал — рестарт"; systemctl restart tailscaled; }
/usr/local/sbin/lan-default.sh
