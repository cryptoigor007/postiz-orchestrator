#!/bin/bash
# GUI-проверка панели (jsdom): все экраны, выбор обложки, удаление, папки.
# Требует: node/npm. URL берётся из GUI_URL, иначе — локальный сервер.
set -euo pipefail
cd "$(dirname "$0")/.."
GUI_DIR=tests/gui
if [ ! -d "$GUI_DIR/node_modules" ]; then
  echo ">> установка jsdom (один раз)…"
  npm --prefix "$GUI_DIR" install --silent
fi
if [ -z "${GUI_URL:-}" ]; then
  KEY="${WEBAPP_ACCESS_KEY:-$(ssh -o BatchMode=yes -o ConnectTimeout=5 root@192.168.100.40 \
        'grep -m1 ^WEBAPP_ACCESS_KEY= /opt/orchestrator/.env | cut -d= -f2-' 2>/dev/null || true)}"
  HOST="${GUI_HOST:-192.168.100.40:8080}"
  BUILD="$(grep -m1 'WEBAPP_BUILD = ' src/orchestrator/webapp_api.py | grep -oE '[0-9]+' || true)"
  if [ -n "$BUILD" ]; then
    GUI_URL="http://$HOST/webapp/b/$BUILD/?view=queue"
  else
    GUI_URL="http://$HOST/webapp/?view=queue"
  fi
fi
export WEBAPP_ACCESS_KEY="${KEY:-${WEBAPP_ACCESS_KEY:-}}"
# ключ нужен и САМОЙ странице (иначе показывается экран авторизации): ?key=...
if [ -n "${WEBAPP_ACCESS_KEY:-}" ] && [ "${GUI_URL#*key=}" = "$GUI_URL" ]; then
  case "$GUI_URL" in
    *\?*) GUI_URL="$GUI_URL&key=$WEBAPP_ACCESS_KEY" ;;
    *)    GUI_URL="$GUI_URL?key=$WEBAPP_ACCESS_KEY" ;;
  esac
fi
echo ">> проверяю: $GUI_URL (key в URL + заголовок; путь /webapp/k/ отключён по умолчанию)"
node "$GUI_DIR/check.mjs" "$GUI_URL"
