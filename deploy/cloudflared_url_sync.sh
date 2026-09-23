#!/bin/bash
set -uo pipefail
ENV=/opt/orchestrator/.env
STATE=/var/lib/cloudflared-webapp.url
LOG=/var/log/cloudflared-url-sync.log
TOKEN=$(grep -m1 "^TELEGRAM_BOT_TOKEN=" "$ENV" 2>/dev/null | cut -d= -f2-)
KEY=$(grep -m1 "^WEBAPP_ACCESS_KEY=" "$ENV" 2>/dev/null | cut -d= -f2-)
URL=$(journalctl -u cloudflared-webapp --no-pager 2>/dev/null | grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" | tail -1)
if [ -z "$URL" ]; then
  # журнал мог быть очищен (SystemMaxUse) — берём базовый URL из файла состояния
  URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" "$STATE" 2>/dev/null | tail -1)
fi
BUILD=$(/opt/orchestrator/venv/bin/python -c "import sys; sys.path.insert(0,\"/opt/orchestrator/src\"); from orchestrator.webapp_api import WEBAPP_BUILD; print(WEBAPP_BUILD)" 2>/dev/null)
if [ -z "$URL" ]; then echo "$(date -Is) no url yet" >> "$LOG"; exit 0; fi
# 10.2: do NOT put access key in URL (query or path). Panel uses header/cookie after open.
# Optional legacy: ORCH_WEBAPP_URL_WITH_KEY=1 restores ?key= for old Telegram clients.
PUB="$URL/webapp/b/$BUILD/"
if [ "${ORCH_WEBAPP_URL_WITH_KEY:-0}" = "1" ] && [ -n "$KEY" ]; then
  PUB="$URL/webapp/b/$BUILD/?key=$KEY"
fi
CUR=$(cat "$STATE" 2>/dev/null || true)
if [ "$CUR" != "$PUB" ]; then
  MD="{\"menu_button\":{\"type\":\"web_app\",\"text\":\"Панель\",\"web_app\":{\"url\":\"$PUB\"}}}"
  curl -s --max-time 20 -X POST "https://api.telegram.org/bot$TOKEN/setChatMenuButton" -H "Content-Type: application/json" -d "$MD" >/dev/null
  IDS=$(/opt/orchestrator/venv/bin/python - <<PY 2>/dev/null
import yaml
c=yaml.safe_load(open("/opt/orchestrator/config.yaml"))
print(" ".join(str(x) for x in (c.get("telegram") or {}).get("allowed_chat_ids") or []))
PY
)
  for cid in $IDS; do
    curl -s --max-time 20 -X POST "https://api.telegram.org/bot$TOKEN/setChatMenuButton" -H "Content-Type: application/json" \
      -d "{\"chat_id\":$cid,\"menu_button\":{\"type\":\"web_app\",\"text\":\"Панель\",\"web_app\":{\"url\":\"$PUB\"}}}" >/dev/null
  done
  sed -i "s|^WEBAPP_PUBLIC_URL=.*|WEBAPP_PUBLIC_URL=$PUB|" "$ENV"
  echo "$PUB" > "$STATE"
  systemctl restart orchestrator.service
  echo "$(date -Is) updated -> $PUB" >> "$LOG"
  tail -n 200 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null || true
fi
