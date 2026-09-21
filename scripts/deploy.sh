#!/bin/bash
# Деплой оркестратора на pve: безопасный rsync (НЕ меняет владельца) + рестарт + проверка.
# Использование: scripts/deploy.sh
set -euo pipefail
HOST="${PVE_HOST:-}"
DEST="${PVE_DEST:-/opt/orchestrator}"
cd "$(dirname "$0")/.."

if [ -z "$HOST" ]; then
  # Авто-выбор доступного адреса: Tailscale, затем LAN.
  for cand in root@100.95.225.71 root@192.168.100.50 root@192.168.100.40; do
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$cand" true 2>/dev/null; then
      HOST="$cand"; break
    fi
  done
fi
if [ -z "$HOST" ]; then
  echo "ERROR: pve недоступен ни по tailscale, ни по LAN (проверь сеть/Tailscale)" >&2
  exit 1
fi
echo ">> host: $HOST"

echo ">> rsync -> $HOST:$DEST"
rsync -az --delete --no-owner --no-group \
  --exclude venv --exclude .git --exclude __pycache__ --exclude '.pytest_cache' \
  --exclude data --exclude backups --exclude logs --exclude certs --exclude '.DS_Store' --exclude '.env' \
  ./ "$HOST:$DEST/"

echo ">> ownership + restart"
ssh "$HOST" "chown -R orchestrator:orchestrator '$DEST'; chmod 600 '$DEST/.env' 2>/dev/null || true; \
  systemctl restart orchestrator.service"
sleep 3
# P1-15: проверки отдельными ssh-вызовами — раньше цепочка заканчивалась `echo`/`curl | head`,
# поэтому ssh всегда возвращал 0 и деплой был «зелёным» даже при упавшем сервисе.
ssh "$HOST" 'systemctl is-active --quiet orchestrator.service' \
  || { echo "ERROR: orchestrator.service не active после рестарта" >&2; exit 1; }
ssh "$HOST" 'curl -sf --max-time 5 http://127.0.0.1:8080/health >/dev/null' \
  || { echo "ERROR: /health не отвечает после рестарта" >&2; exit 1; }
echo "service=active health=ok"

echo ">> sync menu button"
ssh "$HOST" "/usr/local/bin/cloudflared_url_sync.sh >/dev/null 2>&1 || true; cat /var/lib/cloudflared-webapp.url"
echo ">> done"
