#!/bin/bash
# Диагностика сети сервера (pve): двойные интерфейсы в одной подсети, proxy_arp,
# мосты, левые DHCP, конфликты IP. Запуск на сервере:  bash scripts/network_doctor.sh [--fix]
set -u
FIX=0
[ "${1:-}" = "--fix" ] && FIX=1

echo "== интерфейсы =="
ip -br a | grep -vE "lo |docker|veth|tap|fwbr|fwln|fwpr"
echo
echo "== IPv4-адреса подсети 192.168.100.x =="
ip -4 -o a | awk '{print $2, $4}' | grep "192.168.100." || true
echo
echo "== маршруты =="
ip route
echo
echo "== мост vmbr0 (участники) =="
bridge link show 2>/dev/null || echo "нет bridge"
echo
echo "== proxy_arp (должно быть 0 везде!) =="
FOUND=0
for i in /proc/sys/net/ipv4/conf/*/proxy_arp; do
  v=$(cat "$i")
  if [ "$v" != "0" ]; then
    iface=$(basename "$(dirname "$i")")
    echo "  $iface = $v"
    FOUND=1
    if [ "$FIX" = "1" ]; then
      sysctl -w "net.ipv4.conf.$iface.proxy_arp=0" >/dev/null
      echo "    → выключено"
    fi
  fi
done
[ "$FOUND" = "0" ] && echo "  всё 0 — ок"
echo
echo "== ip_forward =="
sysctl -n net.ipv4.ip_forward
echo
echo "== DHCP-сервер на хосте? =="
ss -ulpn 2>/dev/null | grep ":67 " || echo "  нет"
echo
echo "== проверка конфликтов адресов =="
if command -v arping >/dev/null; then
  for ip in 192.168.100.50 192.168.100.60; do
    echo "-- $ip:"
    timeout 4 arping -D -c 2 -I vmbr0 "$ip" 2>&1 | tail -2 || true
  done
else
  echo "  arping не установлен (apt-get install -y iputils-arping)"
fi
echo
echo "== активные соединения =="
nmcli -t -f NAME,DEVICE,STATE con show --active 2>/dev/null || true
echo
echo "== /etc/network/interfaces =="
cat /etc/network/interfaces 2>/dev/null || true
echo
echo "ИТОГ: если видишь ДВА адреса 192.168.100.x на разных интерфейсах — это причина"
echo "сетевых сбоев у соседей (ARP-флукс). Оставь один аплинк (Ethernet), Wi-Fi выключи."
