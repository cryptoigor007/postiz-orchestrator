#!/bin/bash
# NAT и форвардинг для виртуалки (Postiz) через ЛЮБОЙ активный аплинк.
set -u
sysctl -q -w net.ipv4.ip_forward=1
for OUT in vmbr0 wlp2s0; do
  iptables -t nat -C POSTROUTING -s 192.168.100.0/24 -o $OUT -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 192.168.100.0/24 -o $OUT -j MASQUERADE
  iptables -C FORWARD -s 192.168.100.0/24 -o $OUT -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -s 192.168.100.0/24 -o $OUT -j ACCEPT
  iptables -C FORWARD -i $OUT -d 192.168.100.0/24 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i $OUT -d 192.168.100.0/24 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
done
