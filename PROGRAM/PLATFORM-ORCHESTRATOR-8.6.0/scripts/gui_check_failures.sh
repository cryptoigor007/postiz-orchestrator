#!/bin/bash
# Проверка отказоустойчивости панели (все API 500 -> восстановление).
set -euo pipefail
cd "$(dirname "$0")/.."
GUI_DIR=tests/gui
[ -d "$GUI_DIR/node_modules" ] || npm --prefix "$GUI_DIR" install --silent
if [ -z "${GUI_URL:-}" ]; then
  : "${GUI_HOST:?Set GUI_URL or GUI_HOST}"
  KEY="${WEBAPP_ACCESS_KEY:-}"
  HOST="$GUI_HOST"
  BUILD="$(grep -m1 'WEBAPP_BUILD = ' src/orchestrator/webapp_api.py | grep -oE '[0-9]+' || true)"
  GUI_URL="http://$HOST/webapp/b/${BUILD:-dev}/?view=queue"
fi
export WEBAPP_ACCESS_KEY="${KEY:-${WEBAPP_ACCESS_KEY:-}}"
echo ">> проверяю отказоустойчивость: $GUI_URL"
node "$GUI_DIR/check_failures.mjs" "$GUI_URL"
