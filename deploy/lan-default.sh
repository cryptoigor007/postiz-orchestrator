#!/bin/bash
# Единственный владелец LAN-маршрута по умолчанию (vmbr0, metric 100).
# Идемпотентно: есть кабель -> LAN приоритетнее Wi-Fi; нет кабеля -> маршрут убран.
# НЕ трогает Wi-Fi-маршруты, НЕ перезапускает подключения. Ставится в /usr/local/sbin/.
IFACE=enx00e04c36d874
BR=vmbr0
GW=192.168.100.1
METRIC=100
LOG=/var/log/lan-default.log
log(){ echo "$(date "+%F %T") $*" >> "$LOG"; }

carrier=$(cat /sys/class/net/$IFACE/carrier 2>/dev/null || echo 0)
flags=$(ip -br link show "$IFACE" 2>/dev/null | awk '{print $2}')
inbr=0; ip link show "$IFACE" 2>/dev/null | grep -q "master $BR" && inbr=1

if [ "$carrier" = "1" ] && [ "$flags" = "UP" ] && [ "$inbr" = "1" ]; then
  if ! ip route show default dev $BR 2>/dev/null | grep -q .; then
    ip route replace default via $GW dev $BR metric $METRIC && log "LAN default ADD"
  fi
else
  if ip route show default dev $BR 2>/dev/null | grep -q .; then
    ip route del default via $GW dev $BR metric $METRIC 2>/dev/null || ip route del default dev $BR 2>/dev/null
    log "LAN default DEL (carrier=$carrier flags=$flags in_bridge=$inbr)"
  fi
fi
