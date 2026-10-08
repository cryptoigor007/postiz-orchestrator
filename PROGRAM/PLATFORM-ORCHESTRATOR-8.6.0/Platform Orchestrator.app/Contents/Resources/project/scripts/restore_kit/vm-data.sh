#!/usr/bin/env bash
# ШАГ 2. Восстановление содержимого VM platform (запускать на хосте, VM уже существует и доступна по ssh).
#
# Запуск:  bash restore/vm-data.sh <каталог_распакованного_архива> [IP_VM]
# IP VM должен быть передан вторым аргументом.
#
# Что делает: ставит docker, если его нет, возвращает /etc гостя, ключи, /usr/local, каталог
# /home/platform (compose + патч образа), поднимает compose, восстанавливает ВСЕ базы из дампа
# и при необходимости пересобирает образ platform-fixed из патча.

set -euo pipefail

SRC="${1:?укажи каталог распакованного архива}"
: "${2:?VM address is required as the second argument}"
VM="$2"
SSH="ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$VM"

echo "-- проверяю доступ к VM $VM"
$SSH true || { echo "VM недоступна: настрой ssh-ключи (шаг 3 архива)"; exit 2; }

echo "1/7 docker"
if ! $SSH 'command -v docker' >/dev/null 2>&1; then
  echo "  ставлю docker"
  $SSH 'curl -fsSL https://get.docker.com | sh' || { echo "  не удалось поставить docker"; exit 1; }
fi
$SSH 'docker --version'

echo "2/7 /etc гостя, ключи, /usr/local"
[ -f "$SRC/platform/vm-etc.tar.gz" ] && gzip -dc "$SRC/platform/vm-etc.tar.gz" | $SSH 'tar -xzf - -C /'
[ -f "$SRC/platform/vm-root-ssh.tar.gz" ] && gzip -dc "$SRC/platform/vm-root-ssh.tar.gz" | $SSH 'tar -xzf - -C /root'
[ -f "$SRC/platform/vm-usr-local.tar.gz" ] && gzip -dc "$SRC/platform/vm-usr-local.tar.gz" | $SSH 'tar -xzf - -C /usr/local'
echo "  ок"

echo "3/7 каталог platform (/home/platform)"
$SSH 'mkdir -p /home'
gzip -dc "$SRC/platform/home-platform.tgz" | $SSH 'tar -xzf - -C /home'
$SSH 'chown -R platform:platform /home/platform 2>/dev/null || true'

echo "4/7 поднимаю compose"
$SSH 'mkdir -p /var/lib/docker/volumes/platform_platform_uploads/_data' || true
$SSH 'cd /home/platform/platform && docker compose up -d' || { echo "  compose не поднялся"; exit 1; }
sleep 15
$SSH 'docker ps --format "{{.Names}} | {{.Status}}" | sort'

echo "5/7 жду базу и восстанавливаю все базы из дампа"
for _ in $(seq 1 40); do
  $SSH 'docker exec platform-db pg_isready -U platform' >/dev/null 2>&1 && break
  sleep 2
done
$SSH 'docker exec platform-db pg_isready -U platform' >/dev/null 2>&1 || { echo "  база не поднялась"; exit 1; }
if [ -f "$SRC/platform/platform-all-databases.sql.gz" ]; then
  gzip -dc "$SRC/platform/platform-all-databases.sql.gz" | $SSH 'docker exec -i platform-db psql -U platform -q' >/dev/null
  $SSH 'docker exec platform-db psql -U platform -tAc "select datname from pg_database where datname not like '"'"'template%'"'"' and datname <> '"'"'postgres'"'"' order by 1"' | sed 's/^/  база: /'
else
  echo "  дампа нет — пропускаю"; exit 1
fi

echo "6/7 образ platform-fixed"
if ! $SSH 'docker image inspect platform-fixed:v1.47.2' >/dev/null 2>&1; then
  echo "  образа нет — собираю из патча (нужен интернет)"
  $SSH 'cd /home/platform/patch && docker build -t platform-fixed:v1.47.2 .' || \
    echo "  сборка не прошла — проверь /home/platform/patch/Dockerfile"
fi
$SSH 'docker images --format "{{.Repository}}:{{.Tag}}" | grep -i platform | sed "s/^/  образ: /"' || true
$SSH 'cd /home/platform/platform && docker compose up -d' >/dev/null

echo "7/7 состояние"
$SSH 'docker ps --format "{{.Names}} | {{.Status}}" | sort'
if [ -f "$SRC/platform/_media_excluded.txt" ]; then
  echo "  медиа в бэкапе нет ($(head -1 "$SRC/platform/_media_excluded.txt" | tr -d '\t')) — оно пересоздаётся публикациями"
fi
echo
echo "ГОТОВО (platform). Дальше: bash restore/app.sh $SRC"
