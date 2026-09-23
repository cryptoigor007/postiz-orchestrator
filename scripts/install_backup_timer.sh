#!/usr/bin/env bash
# Ставит на pve ежедневный таймер бэкапа (orch-backup) — работает без Mac.
#
# Идемпотентно: можно запускать повторно. Делает на сервере:
#   /usr/local/lib/orch-backup/backup.sh        — серверная часть бэкапа (scripts/backup_pve.sh)
#   /usr/local/lib/orch-backup/restore_kit/     — набор скриптов восстановления
#   /etc/systemd/system/orch-backup.{service,timer}
#   systemctl enable --now orch-backup.timer
#
# Запуск с Mac (из корня репозитория): bash scripts/install_backup_timer.sh

set -euo pipefail

PVE_HOST="${PVE_HOST:-root@100.95.225.71}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="/usr/local/lib/orch-backup"

echo ">> копирую серверную часть бэкапа на $PVE_HOST"
ssh -o BatchMode=yes "$PVE_HOST" "install -d -m 755 $LIB $LIB/restore_kit"
scp -q "$HERE/backup_pve.sh" "$PVE_HOST:$LIB/backup.sh"
ssh -o BatchMode=yes "$PVE_HOST" "chmod 755 $LIB/backup.sh"
scp -q -r "$HERE/restore_kit/." "$PVE_HOST:$LIB/restore_kit/"
scp -q "$HERE/../deploy/orch-backup.service" "$HERE/../deploy/orch-backup.timer" "$PVE_HOST:/etc/systemd/system/"

echo ">> включаю таймер"
ssh -o BatchMode=yes "$PVE_HOST" "systemctl daemon-reload && systemctl enable --now orch-backup.timer >/dev/null && \
  systemctl list-timers orch-backup.timer --no-pager | head -3 && \
  systemctl is-enabled orch-backup.timer"
echo ">> готово: бэкап будет собираться каждую ночь в 04:00, хранится 7 последних + 12 месячных"
