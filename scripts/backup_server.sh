#!/usr/bin/env bash
# Полный «настроечный» бэкап сервера (без медиафайлов) + копия на Mac.
#
# Задача: по архиву можно поднять такую же машину с нуля — Proxmox, VM Postiz, наш оркестратор.
# Поэтому собирается ВСЯ конфигурация, которая для этого нужна, и ничего, что восстанавливается
# само (медиа, кеши, образы ПО, диски целиком).
#
# Запуск с Mac (из корня репозитория):  bash scripts/backup_server.sh
# Переменные: PVE_HOST (root@100.95.225.71), BACKUP_DIR (~/backups), KEEP (7 архивов на сервере)
# Ночью то же самое делает таймер на сервере: orch-backup.timer (см. scripts/install_backup_timer.sh)

set -euo pipefail

PVE_HOST="${PVE_HOST:-root@100.95.225.71}"
DEST="${BACKUP_DIR:-$HOME/backups}"
KEEP="${KEEP:-7}"
STAMP="$(date +%Y-%m-%d_%H%M)"
NAME="orch-server-$STAMP"
REMOTE_DIR="/root/backups"
VM_IP="192.168.100.60"

mkdir -p "$DEST"

# набор скриптов восстановления (лежит в репозитории) — кладём внутрь архива
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/restore_kit" && pwd)"

echo ">> собираю бэкап на сервере ($PVE_HOST)"
# BACKUP_PERSONAL=1 — дополнительно положить личные файлы владельца из /root (без кешей и логов)
# BACKUP_WITH_BINARY=0 — не класть cloudflared (39 МБ) внутрь архива
ssh -o BatchMode=yes "$PVE_HOST" "rm -rf /tmp/restore-kit && mkdir -p /tmp/restore-kit"
scp -q -r "$KIT"/. "$PVE_HOST:/tmp/restore-kit/"

# серверная часть лежит в scripts/backup_pve.sh — тот же файл ставится на pve таймером
ssh -o BatchMode=yes "$PVE_HOST" "NAME='$NAME' REMOTE_DIR='$REMOTE_DIR' KEEP='$KEEP' VM_IP='$VM_IP' BACKUP_PERSONAL='${BACKUP_PERSONAL:-0}' BACKUP_WITH_BINARY='${BACKUP_WITH_BINARY:-1}' KIT_SRC=/tmp/restore-kit bash -s" < "$(dirname "${BASH_SOURCE[0]}")/backup_pve.sh"

echo ">> копирую на Mac: $DEST"
scp -q "$PVE_HOST:$REMOTE_DIR/$NAME.tar.gz" "$DEST/"
scp -q "$PVE_HOST:$REMOTE_DIR/$NAME.tar.gz.sha256" "$DEST/"
( cd "$DEST" && shasum -a 256 -c "$NAME.tar.gz.sha256" >/dev/null && echo ">> контрольная сумма совпала" )
ls -lh "$DEST/$NAME.tar.gz" | awk '{print ">> размер копии:", $5}'
echo ">> готово: $DEST/$NAME.tar.gz"
