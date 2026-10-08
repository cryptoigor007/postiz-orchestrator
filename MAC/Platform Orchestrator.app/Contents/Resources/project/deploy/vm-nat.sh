#!/bin/bash
# DEPRECATED (HARD_CUT): not required for module-path runtime
# NAT и форвардинг для виртуалки (Postiz) через ЛЮБОЙ активный аплинк.
set -u
: "${VM_NET_CIDR:?Set VM_NET_CIDR in the environment}"
sysctl -q -w net.ipv4.ip_forward=1
for OUT in vmbr0 wlp2s0; do
  iptables -t nat -C POSTROUTING -s "${VM_NET_CIDR}" -o $OUT -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s "${VM_NET_CIDR}" -o $OUT -j MASQUERADE
  iptables -C FORWARD -s "${VM_NET_CIDR}" -o $OUT -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -s "${VM_NET_CIDR}" -o $OUT -j ACCEPT
  iptables -C FORWARD -i $OUT -d "${VM_NET_CIDR}" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i $OUT -d "${VM_NET_CIDR}" -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
done
