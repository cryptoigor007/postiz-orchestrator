#!/bin/bash
# Выполнить команду в VM с Mac или pve.
# Требует: VM_SSH=platform@<vm-host>, опционально PVE_HOSTS="root@pve1 root@pve2".
set -euo pipefail
CMD="${1:-}"
[ -n "$CMD" ] || { echo "usage: $0 '<command>'" >&2; exit 2; }
: "${VM_SSH:?Set VM_SSH (for example platform@vm-host)}"
PVE_HOSTS="${PVE_HOSTS:-}"
if ssh -o ConnectTimeout=5 -o BatchMode=yes "$VM_SSH" true 2>/dev/null; then
  exec ssh -o ConnectTimeout=10 "$VM_SSH" "$CMD"
fi
for pve in $PVE_HOSTS; do
  if ssh -o ConnectTimeout=5 -o BatchMode=yes "$pve" "ssh -o ConnectTimeout=5 -o BatchMode=yes $VM_SSH true" 2>/dev/null; then
    exec ssh -o ConnectTimeout=10 "$pve" "ssh -o ConnectTimeout=10 $VM_SSH $(printf '%q' "$CMD")"
  fi
done
echo "ERROR: VM is unreachable; set VM_SSH and PVE_HOSTS" >&2
exit 1
