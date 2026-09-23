#!/usr/bin/env bash
# Проверка бэкапа по чек-листу: «точно ли в архиве всё, что нужно для подъёма машины с нуля».
#
# Запуск с Mac:  bash scripts/backup_verify.sh [путь к архиву]
# Без аргумента берётся самый свежий архив из ~/backups.
# Выход: 0 — все пункты на месте, 1 — что-то отсутствует (печатается, что именно).

set -euo pipefail

DEST="${BACKUP_DIR:-$HOME/backups}"
ARCHIVE="${1:-}"
if [ -z "$ARCHIVE" ]; then
  ARCHIVE="$(ls -1t "$DEST"/orch-server-*.tar.gz 2>/dev/null | head -1 || true)"
fi
if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
  echo "архив не найден (искал в $DEST)"; exit 2
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
tar -xzf "$ARCHIVE" -C "$WORK"
ROOT="$(find "$WORK" -maxdepth 1 -mindepth 1 -type d | head -1)"
echo ">> проверяю архив: $(basename "$ARCHIVE") ($(du -h "$ARCHIVE" | cut -f1))"

FAIL=0
need_file() {  # need_file <путь относительно корня> <что это>
  if [ -f "$ROOT/$1" ] && [ -s "$ROOT/$1" ]; then
    printf '  ок   %-46s %s\n' "$1" "$2"
  else
    printf '  НЕТ  %-46s %s\n' "$1" "$2"; FAIL=$((FAIL + 1))
  fi
}
# ВАЖНО: не использовать `cmd | grep -q` — при pipefail grep выходит раньше,
# источник получает SIGPIPE, и проверка ложно падает. Поэтому считаем совпадения.
hits() {  # hits <подстрока> — сколько раз подстрока встретилась во входе
  local n
  n="$(grep -c -F -e "$1" || true)"
  printf '%s' "${n:-0}"
}
tar_has_name() {  # tar_has_name <архив> <имя> — есть ли файл в архиве
  tar -tzf "$ROOT/$1" 2>/dev/null | hits "$2"
}
tar_has_text() {  # tar_has_text <архив> <строка> — есть ли строка в содержимом архива
  tar -xzOf "$ROOT/$1" 2>/dev/null | hits "$2"
}
gz_has_text() {  # gz_has_text <gz-файл> <строка>
  gunzip -c "$ROOT/$1" 2>/dev/null | hits "$2"
}
file_has_text() {  # file_has_text <файл> <строка>
  cat "$ROOT/$1" 2>/dev/null | hits "$2"
}
report() {  # report <имя> <сколько нашлось> <что это>
  if [ "${2:-0}" -gt 0 ]; then
    printf '  ок   %-46s %s\n' "$1" "$3"
  else
    printf '  НЕТ  %-46s %s\n' "$1" "$3"; FAIL=$((FAIL + 1))
  fi
}
need_in()     { report "$1: $2" "$(tar_has_name "$1" "$2")" "$3"; }
need_inner()  { report "$1 содержит «$2»" "$(tar_has_text "$1" "$2")" "$3"; }
need_gz()     { report "$1: $2" "$(gz_has_text "$1" "$2")" "$3"; }
need_text()   { report "$1: $2" "$(file_has_text "$1" "$2")" "$3"; }

need_text() {  # need_text <файл> <строка> <что это>
  if grep -q -- "$2" "$ROOT/$1" 2>/dev/null; then
    printf '  ок   %-46s %s\n' "$1: $2" "$3"
  else
    printf '  НЕТ  %-46s %s\n' "$1: $2" "$3"; FAIL=$((FAIL + 1))
  fi
}

echo "-- Proxmox-хост"
need_file proxmox/_pveversion.txt "версия Proxmox"
need_file proxmox/host-etc.tar.gz "/etc целиком"
need_in   proxmox/host-etc.tar.gz "etc/ssh/ssh_host" "ключи хоста ssh"
need_in   proxmox/host-etc.tar.gz "etc/network/interfaces" "сеть"
need_in   proxmox/pve-etc.tar.gz  "qemu-server/120.conf" "конфиг VM Postiz"
need_file proxmox/_vm-120-config.txt "конфиг VM Postiz текстом"
need_file proxmox/_packages.txt "пакеты с версиями"
need_text proxmox/_packages.txt "=" "версии пакетов, а не одни имена"
need_file proxmox/_storage_layout.txt "разметка дисков (LVM/ZFS)"
need_file proxmox/_block_devices.txt "lsblk/blkid/findmnt"
need_file proxmox/_network.txt "IP и маршруты"
need_file proxmox/_firewall.txt "правила firewall"
need_file proxmox/_sysctl.txt "параметры ядра"
need_file proxmox/root-ssh.tar.gz "ключи root"
need_in   proxmox/usr-local.tar.gz "cloudflared_url_sync.sh" "наш скрипт синхронизации ссылки"
need_in   proxmox/usr-local.tar.gz "bin/cloudflared" "бинарник cloudflared (ставится заново)"

echo "-- systemd"
need_file systemd/orchestrator.service "юнит оркестратора"
need_text systemd/orchestrator.service "ExecStart" "команда запуска"
need_file systemd/cloudflared-webapp.service "юнит туннеля панели"
need_file systemd/cloudflared-url-sync.service "юнит синхронизации ссылки"
need_file systemd/cloudflared-url-sync.timer "таймер синхронизации"
need_file systemd/_enabled.txt "включённые сервисы хоста"

echo "-- Оркестратор"
need_file orchestrator/config.yaml "конфиг (проекты, платформы)"
need_file orchestrator/.env "секреты и токены"
need_file orchestrator/data/data.sqlite "база очереди"
need_file orchestrator/_pip_freeze.txt "зависимости python"
need_inner orchestrator/source.tar.gz "scheduler.py" "код оркестратора"
need_inner orchestrator/source.tar.gz "app.js" "код панели"
need_inner orchestrator/source.tar.gz "deploy.sh" "скрипты деплоя"
need_inner orchestrator/source.tar.gz "config.yaml" "конфиг внутри снимка кода"

echo "-- Postiz (VM 120)"
need_file postiz/docker-compose.yml "compose"
need_inner postiz/home-postiz.tgz "Dockerfile" "патч для сборки образа"
need_inner postiz/home-postiz.tgz "docker-compose.yml" "compose в каталоге"
need_in   postiz/vm-etc.tar.gz "etc/ssh/sshd_config" "конфиг ssh гостя"
need_in   postiz/vm-etc.tar.gz "etc/shadow" "пользователи и пароли гостя"
need_file postiz/_docker_daemon.txt "настройки docker (или отметка, что их нет)"
need_file postiz/vm-root-ssh.tar.gz "ключи root на VM"
need_file postiz/_compose_config.txt "итоговый разбор compose"
need_file postiz/_packages.txt "пакеты VM с версиями"
need_file postiz/_containers.txt "список контейнеров"
need_file postiz/_images.txt "список образов"
need_file postiz/_volumes.txt "список томов"
need_file postiz/_media_excluded.txt "что исключено (медиа) и сколько весит"
need_gz   postiz/postiz-all-databases.sql.gz "CREATE DATABASE postiz" "дамп базы Postiz"
need_gz   postiz/postiz-all-databases.sql.gz "CREATE DATABASE temporal" "дамп базы Temporal"

echo "-- Инструкция"
need_file RESTORE.md "как восстанавливать"
need_text RESTORE.md "postiz-all-databases" "шаг восстановления баз"
need_text RESTORE.md "postiz-fixed" "шаг пересборки образа"

echo
if [ "$FAIL" -eq 0 ]; then
  echo "ИТОГ: чек-лист пройден полностью — по архиву машина поднимается с нуля."
  exit 0
fi
echo "ИТОГ: не хватает пунктов: $FAIL — см. строки «НЕТ» выше."
exit 1
