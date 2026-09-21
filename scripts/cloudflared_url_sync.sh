#!/bin/bash
# Синхронизация публичного URL панели (quick tunnel) с меню-кнопкой Telegram.
# URL ищется: (1) в журнале cloudflared, (2) fallback — из прошлого значения state-файла.
# Панель: /webapp/b/<BUILD>/ с ключом в query (?key=) — legacy-путь /webapp/k/ не используется.
set -uo pipefail
ENV=/opt/orchestrator/.env
STATE=/var/lib/cloudflared-webapp.url
LOG=/var/log/cloudflared-url-sync.log
TOKEN=$(grep -m1 "^TELEGRAM_BOT_TOKEN=" "$ENV" 2>/dev/null | cut -d= -f2-)
KEY=$(grep -m1 "^WEBAPP_ACCESS_KEY=" "$ENV" 2>/dev/null | cut -d= -f2-)

URL=$(journalctl -u cloudflared-webapp --no-pager -g trycloudflare 2>/dev/null \
  | grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" | tail -1)
if [ -z "$URL" ]; then
  URL=$(sed -nE 's#^(https://[a-z0-9-]+\.trycloudflare\.com).*#\1#p' "$STATE" 2>/dev/null | tail -1)
fi
BUILD=$(/opt/orchestrator/venv/bin/python -c "import sys; sys.path.insert(0,\"/opt/orchestrator/src\"); from orchestrator.webapp_api import WEBAPP_BUILD; print(WEBAPP_BUILD)" 2>/dev/null)

if [ -z "$URL" ] || [ -z "$BUILD" ]; then
  echo "$(date -Is) no url/build (url='${URL:-}' build='${BUILD:-}')" >> "$LOG"
  exit 0
fi

if [ -n "$KEY" ]; then PUB="$URL/webapp/b/$BUILD/?key=$KEY"; else PUB="$URL/webapp/b/$BUILD/"; fi
CUR=$(cat "$STATE" 2>/dev/null || true)

if [ "$CUR" != "$PUB" ]; then
  curl -s --max-time 20 -X POST "https://api.telegram.org/bot$TOKEN/setChatMenuButton" \
    -H "Content-Type: application/json" \
    -d "{\"menu_button\":{\"type\":\"web_app\",\"text\":\"Панель\",\"web_app\":{\"url\":\"$PUB\"}}}" >/dev/null
  IDS=$(/opt/orchestrator/venv/bin/python - <<PY 2>/dev/null
import yaml
c = yaml.safe_load(open("/opt/orchestrator/config.yaml"))
print(" ".join(str(x) for x in (c.get("telegram") or {}).get("allowed_chat_ids") or []))
PY
)
  for cid in $IDS; do
    curl -s --max-time 20 -X POST "https://api.telegram.org/bot$TOKEN/setChatMenuButton" \
      -H "Content-Type: application/json" \
      -d "{\"chat_id\":$cid,\"menu_button\":{\"type\":\"web_app\",\"text\":\"Панель\",\"web_app\":{\"url\":\"$PUB\"}}}" >/dev/null
  done
  sed -i "s|^WEBAPP_PUBLIC_URL=.*|WEBAPP_PUBLIC_URL=$PUB|" "$ENV"
  echo "$PUB" > "$STATE"
  systemctl restart orchestrator.service
  echo "$(date -Is) updated -> $PUB" >> "$LOG"
  tail -n 200 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null || true
fi
