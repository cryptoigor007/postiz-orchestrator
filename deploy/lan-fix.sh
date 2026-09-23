#!/bin/bash
# LAN workaround: Wi-Fi primary + .50 alias on Wi-Fi + VM route via bridge
for i in $(seq 1 30); do ip route show | grep -q '192.168.100.0/24 dev vmbr0' && break; sleep 2; done
ip route del 192.168.100.0/24 dev vmbr0 2>/dev/null || true
ip route replace 192.168.100.60/32 dev vmbr0 src 192.168.100.50
ip addr add 192.168.100.50/32 dev wlp2s0 2>/dev/null || true
sysctl -q net.ipv4.conf.wlp2s0.proxy_arp=1
