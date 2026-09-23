#!/usr/bin/env bash
# ШАГ 1. Восстановление хоста Proxmox (запускать на свежем Proxmox от root).
#
# Запуск:  bash restore/host.sh <каталог_распакованного_архива>
#
# Что делает: возвращает /etc хоста, конфиги Proxmox (все VM и CT), ключи root, свои программы
# из /usr/local, cloudflared, минимально нужные пакеты и systemd-юниты.
# Полный список пакетов с версиями лежит рядом — proxmox/_packages.txt (ставить по необходимости).

set -euo pipefail

SRC="${1:?укажи каталог распакованного архива}"
[ -f "$SRC/proxmox/host-etc.tar.gz" ] || { echo "нет $SRC/proxmox/host-etc.tar.gz"; exit 2; }

echo "1/7 /etc хоста (сеть, ssh, apt, systemd)"
tar -xzf "$SRC/proxmox/host-etc.tar.gz" -C /

echo "2/7 конфиги Proxmox (VM, CT, хранилища, пользователи)"
tar -xzf "$SRC/proxmox/pve-etc.tar.gz" -C /etc

echo "3/7 ключи root"
[ -f "$SRC/proxmox/root-ssh.tar.gz" ] && tar -xzf "$SRC/proxmox/root-ssh.tar.gz" -C /root

echo "4/7 свои программы (/usr/local: cloudflared_url_sync.sh и прочее)"
[ -f "$SRC/proxmox/usr-local.tar.gz" ] && tar -xzf "$SRC/proxmox/usr-local.tar.gz" -C /usr/local

echo "5/7 cloudflared"
if [ ! -x /usr/local/bin/cloudflared ]; then
  if [ -f "$SRC/proxmox/cloudflared-linux-amd64" ]; then
    install -m 0755 "$SRC/proxmox/cloudflared-linux-amd64" /usr/local/bin/cloudflared
    echo "  ок   поставлен из архива"
  else
    echo "  тяну из интернета"
    curl -fsSL -o /usr/local/bin/cloudflared \
      https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
    chmod 0755 /usr/local/bin/cloudflared
  fi
fi
/usr/local/bin/cloudflared --version || true

echo "6/7 пакеты"
if [ -f "$SRC/proxmox/_packages.txt" ]; then
  apt-get update -qq || true
  # ставим только то, чего нет: точная версия может быть уже недоступна в репозитории
  MISSING=""
  for p in python3 python3-venv python3-pip rsync curl sqlite3 git ca-certificates; do
    dpkg -s "$p" >/dev/null 2>&1 || MISSING="$MISSING $p"
  done
  if [ -n "${MISSING// /}" ]; then
    # shellcheck disable=SC2086
    apt-get install -y --no-install-recommends $MISSING || true
  fi
  echo "  сверь остальное с proxmox/_packages.txt (там 1028 пакетов с версиями)"
fi

echo "7/7 сервисы"
systemctl daemon-reload || true
for u in orchestrator cloudflared-webapp cloudflared-url-sync.timer; do
  systemctl enable --now "$u" 2>/dev/null || true
done
systemctl --no-pager --full status orchestrator 2>/dev/null | head -8 || true

echo
echo "ГОТОВО (хост). Дальше: восстановить VM Postiz — bash restore/vm-create.sh $SRC"
echo "Если VM уже есть — сразу: bash restore/vm-data.sh $SRC"
