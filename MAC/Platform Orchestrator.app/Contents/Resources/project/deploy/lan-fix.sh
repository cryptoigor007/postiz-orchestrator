#!/bin/bash
# DEPRECATED (HARD_CUT): not required for module-path runtime
# Optional legacy network workaround. Configure HOST_IP and VM_IP in the environment.
set -euo pipefail
: "${HOST_IP:?Set HOST_IP in the environment before running lan-fix.sh}"
: "${VM_IP:?Set VM_IP in the environment before running lan-fix.sh}"
: "${LAN_CIDR:?Set LAN_CIDR in the environment}"
: "${BR:?Set BR in the environment}"
: "${IFACE:?Set IFACE in the environment}"
for i in $(seq 1 30); do ip route show | grep -q "${LAN_CIDR} dev ${BR}" && break; sleep 2; done
ip route del "$LAN_CIDR" dev "$BR" 2>/dev/null || true
ip route replace "${VM_IP}/32" dev "$BR" src "${HOST_IP}"
ip addr add "${HOST_IP}/32" dev wlp2s0 2>/dev/null || true
sysctl -q net.ipv4.conf.wlp2s0.proxy_arp=1
