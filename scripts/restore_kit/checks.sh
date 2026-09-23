#!/usr/bin/env bash
# ФИНАЛЬНАЯ ПРОВЕРКА после восстановления: всё ли живо.
#
# Запуск на хосте:  bash restore/checks.sh [каталог_архива]
# Выход: 0 — всё работает, 1 — есть проблемы (видно, где именно).

set -euo pipefail

VM="${VM:-192.168.100.60}"
OWNER_CHAT="${OWNER_CHAT:-7004751908}"
KEY="$(grep -oP '^WEBAPP_ACCESS_KEY=\K.*' /opt/orchestrator/.env 2>/dev/null | tr -d '"'"'"' ' | head -1)"
TOKEN="$(grep -oP '^TELEGRAM_BOT_TOKEN=\K.*' /opt/orchestrator/.env 2>/dev/null | tr -d '"'"'"' ' | head -1)"
FAIL=0
ok() { echo "  ок   $*"; }
bad() { echo "  НЕТ  $*"; FAIL=$((FAIL + 1)); }

echo "-- хост"
systemctl is-active --quiet orchestrator && ok "оркестратор запущен" || bad "оркестратор не запущен"
systemctl is-active --quiet cloudflared-webapp && ok "туннель панели запущен" || bad "туннель панели не запущен"

if [ -n "$KEY" ]; then
  curl -fsS --max-time 10 "http://127.0.0.1:8080/webapp/api/status?key=$KEY" >/dev/null 2>&1 \
    && ok "панель отвечает" || bad "панель не отвечает на 127.0.0.1:8080"
  curl -fsS --max-time 10 "http://127.0.0.1:8080/webapp/api/projects?key=$KEY" 2>/dev/null | grep -q tochka \
    && ok "API проектов отвечает (виден проект tochka)" || bad "API проектов не отвечает"
else
  bad "в /opt/orchestrator/.env нет WEBAPP_ACCESS_KEY"
fi

if journalctl -u orchestrator --since "-15 min" --no-pager 2>/dev/null | grep -q Traceback; then
  bad "в журнале оркестратора есть Traceback"
else
  ok "ошибок в журнале нет"
fi

if [ -n "$TOKEN" ]; then
  curl -fsS --max-time 10 "https://api.telegram.org/bot$TOKEN/getChatMenuButton?chat_id=$OWNER_CHAT" 2>/dev/null \
    | grep -q '"type":"web_app"' && ok "кнопка панели в Telegram на месте" || bad "кнопки панели в Telegram нет"
fi

echo "-- VM Postiz ($VM)"
if ssh -o BatchMode=yes -o ConnectTimeout=6 "root@$VM" true 2>/dev/null; then
  ok "VM доступна по ssh"
  RUNNING="$(ssh -o BatchMode=yes "root@$VM" 'docker ps -q 2>/dev/null | wc -l' | tr -d ' ')"
  [ "${RUNNING:-0}" -ge 5 ] && ok "контейнеры работают: $RUNNING" || bad "контейнеров меньше пяти: ${RUNNING:-0}"
  T="$(ssh -o BatchMode=yes "root@$VM" \
      'docker exec postiz-db psql -U postiz -tAc "select count(*) from information_schema.tables where table_schema='"'"'public'"'"'" 2>/dev/null' \
      | tr -d ' ')"
  [ "${T:-0}" -gt 10 ] && ok "база Postiz отвечает (таблиц: $T)" || bad "база Postiz не отвечает"
else
  bad "VM Postiz недоступна по ssh"
fi

echo
if [ "$FAIL" -eq 0 ]; then
  echo "ИТОГ: восстановление подтверждено — всё работает."
  exit 0
fi
echo "ИТОГ: проблем: $FAIL — см. строки «НЕТ»."
exit 1
