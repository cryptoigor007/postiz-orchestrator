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
  GUI_URL="http://$HOST/webapp/k/$KEY/b/dev/?view=queue"
fi
echo ">> проверяю: $GUI_URL"
node "$GUI_DIR/check.mjs" "$GUI_URL"
