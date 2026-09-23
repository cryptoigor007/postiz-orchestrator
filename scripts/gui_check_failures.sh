#!/bin/bash
# Проверка отказоустойчивости панели (все API 500 -> восстановление).
set -euo pipefail
cd "$(dirname "$0")/.."
GUI_DIR=tests/gui
[ -d "$GUI_DIR/node_modules" ] || npm --prefix "$GUI_DIR" install --silent
if [ -z "${GUI_URL:-}" ]; then
  KEY="${WEBAPP_ACCESS_KEY:-$(ssh -o BatchMode=yes -o ConnectTimeout=5 root@192.168.100.40 \
        'grep -m1 ^WEBAPP_ACCESS_KEY= /opt/orchestrator/.env | cut -d= -f2-' 2>/dev/null || true)}"
  HOST="${GUI_HOST:-192.168.100.40:8080}"
  BUILD="$(grep -m1 'WEBAPP_BUILD = ' src/orchestrator/webapp_api.py | grep -oE '[0-9]+' || true)"
  GUI_URL="http://$HOST/webapp/b/${BUILD:-dev}/?view=queue"
fi
export WEBAPP_ACCESS_KEY="${KEY:-${WEBAPP_ACCESS_KEY:-}}"
if [ -n "${WEBAPP_ACCESS_KEY:-}" ] && [ "${GUI_URL#*key=}" = "$GUI_URL" ]; then
  case "$GUI_URL" in
    *\?*) GUI_URL="$GUI_URL&key=$WEBAPP_ACCESS_KEY" ;;
    *)    GUI_URL="$GUI_URL?key=$WEBAPP_ACCESS_KEY" ;;
  esac
fi
echo ">> проверяю отказоустойчивость: $GUI_URL"
node "$GUI_DIR/check_failures.mjs" "$GUI_URL"
