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
  # Раньше здесь был жёстко прописан старый хост (192.168.100.40:8080) — он больше не существует,
  # и проверка падала с EHOSTUNREACH, хотя в CI тот же прогон зелёный. Теперь по умолчанию
  # поднимается тот же локальный стенд, что и в CI: одна команда — один результат и дома, и в CI.
  echo ">> GUI_URL не задан — поднимаю локальный стенд (scripts/ci_gui_smoke.sh)…"
  exec bash scripts/ci_gui_smoke.sh
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
