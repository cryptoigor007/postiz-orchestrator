#!/usr/bin/env bash
# ШАГ 3. Восстановление нашего оркестратора (запускать на хосте после шагов 1-2).
#
# Запуск:  bash restore/app.sh <каталог_распакованного_архива> [куда_ставить]
# По умолчанию ставится в /opt/orchestrator.
#
# Что делает: разворачивает код, настройки, секреты, базу и сертификаты, создаёт окружение
# по списку зависимостей, ставит systemd-юниты и запускает сервис, затем проверяет, что он живой.

set -euo pipefail

SRC="${1:?укажи каталог распакованного архива}"
DEST="${2:-/opt/orchestrator}"
PY="${PYTHON:-python3}"

[ -d "$SRC/orchestrator" ] || { echo "нет $SRC/orchestrator — не тот каталог?"; exit 2; }

echo "1/6 каталог $DEST"
mkdir -p "$DEST"

echo "2/6 код"
tar -xzf "$SRC/orchestrator/source.tar.gz" -C "$DEST"

echo "3/6 настройки, секреты, база, сертификаты"
for f in config.yaml .env; do
  [ -f "$SRC/orchestrator/$f" ] && cp -a "$SRC/orchestrator/$f" "$DEST/"
done
[ -d "$SRC/orchestrator/data" ] && mkdir -p "$DEST/data" && cp -a "$SRC/orchestrator/data/." "$DEST/data/"
[ -d "$SRC/orchestrator/certs" ] && mkdir -p "$DEST/certs" && cp -a "$SRC/orchestrator/certs/." "$DEST/certs/"

echo "4/6 окружение python"
if [ ! -x "$DEST/venv/bin/python" ]; then
  "$PY" -m venv "$DEST/venv"
fi
if [ -f "$SRC/orchestrator/_pip_freeze.txt" ]; then
  "$DEST/venv/bin/pip" install -q --upgrade pip
  "$DEST/venv/bin/pip" install -q -r "$SRC/orchestrator/_pip_freeze.txt"
else
  "$DEST/venv/bin/pip" install -q -r "$DEST/requirements.txt"
fi
PYTHONPATH="$DEST/src" "$DEST/venv/bin/python" -c \
  "import orchestrator; print('  версия:', orchestrator.__version__)"

echo "4б/6 пользователь orchestrator (сервис работает не от root)"
if ! id orchestrator >/dev/null 2>&1; then
  useradd --system --home-dir "$DEST" --shell /usr/sbin/nologin orchestrator
fi
mkdir -p "$DEST/data" "$DEST/logs"
chown -R orchestrator:orchestrator "$DEST" 2>/dev/null || true

echo "5/6 systemd"
for u in "$SRC"/systemd/*.service "$SRC"/systemd/*.timer; do
  [ -e "$u" ] || continue
  cp -a "$u" /etc/systemd/system/
done
systemctl daemon-reload
systemctl enable --now orchestrator
systemctl enable --now cloudflared-webapp 2>/dev/null || true

echo "6/6 проверка"
systemctl --no-pager --full status orchestrator | head -12 || true
KEY="$(grep -oP '^WEBAPP_ACCESS_KEY=\K.*' "$DEST/.env" 2>/dev/null | tr -d '\"'"'"' ' | head -1)"
if [ -n "$KEY" ]; then
  for _ in $(seq 1 20); do
    if curl -fsS "http://127.0.0.1:8080/webapp/api/status?key=$KEY" >/dev/null 2>&1; then
      echo "  ок   панель отвечает на 127.0.0.1:8080"
      break
    fi
    sleep 1
  done
fi
if [ -f "$SRC/systemd/cloudflared-url-sync.timer" ]; then
  systemctl enable --now cloudflared-url-sync.timer 2>/dev/null || true
  echo "  ок   таймер обновления ссылки включён"
fi
echo
echo "ГОТОВО (оркестратор). Проверка: bash restore/checks.sh $SRC"
