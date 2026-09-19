#!/bin/bash
# Выполнить команду в VM 120 (postiz) с Mac или pve.
#   ./scripts/runvm.sh 'docker ps'
# Сначала пробует прямой ssh postiz@192.168.100.60 (docker и sudo -n работают),
# иначе — через `qm guest exec` на pve.
CMD="$1"
if [ -z "$CMD" ]; then echo "usage: $0 '<command>'" >&2; exit 2; fi
if ssh -o ConnectTimeout=5 -o BatchMode=yes postiz@192.168.100.60 'true' 2>/dev/null; then
  exec ssh -o ConnectTimeout=10 postiz@192.168.100.60 "$CMD"
fi
b64=$(printf '%s' "$CMD" | base64)
ssh -o ConnectTimeout=10 root@100.95.225.71 "qm guest exec 120 --timeout 600 -- bash -c 'echo $b64 | base64 -d | bash'" 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
except Exception:
    sys.stdout.write(sys.stdin.read()); sys.exit()
if d.get("out-data"): sys.stdout.write(d["out-data"])
if d.get("err-data"): sys.stderr.write(d["err-data"])
'
