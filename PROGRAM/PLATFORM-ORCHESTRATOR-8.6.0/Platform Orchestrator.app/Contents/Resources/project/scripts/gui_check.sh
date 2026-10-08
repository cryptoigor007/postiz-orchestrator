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
  # Раньше здесь был жёстко прописан старый хост (<GUI_HOST>:<PORT>) — он больше не существует,
  # и проверка падала с EHOSTUNREACH, хотя в CI тот же прогон зелёный. Теперь по умолчанию
  # поднимается тот же локальный стенд, что и в CI: одна команда — один результат и дома, и в CI.
  echo ">> GUI_URL не задан — поднимаю локальный стенд (scripts/ci_gui_smoke.sh)…"
  exec bash scripts/ci_gui_smoke.sh
fi
export WEBAPP_ACCESS_KEY="${KEY:-${WEBAPP_ACCESS_KEY:-}}"
echo ">> проверяю: $GUI_URL (X-Webapp-Key header; query-key disabled)"
node "$GUI_DIR/check.mjs" "$GUI_URL"
