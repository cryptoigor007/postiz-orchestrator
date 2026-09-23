#!/bin/bash
# Синхронизация публичного адреса quick-туннеля Postiz (ВМ 120).
#
# Зачем: `cloudflared-postiz` — quick tunnel, его адрес меняется при каждом перезапуске, а от адреса
# зависят MAIN_URL / NEXT_PUBLIC_BACKEND_URL / FRONTEND_URL контейнера `postiz` в ВМ и Redirect URI
# в кабинетах площадок (Meta, TikTok, Google/YouTube). Сменился адрес — публикация «в никуда».
#
# Скрипт ТОЛЬКО ЧИТАЕТ: ничего не правит, не пересоздаёт контейнеры и не перезапускает службы.
# При расхождении он печатает готовые команды, а решение и выполнение — за человеком.
#
# Использование:
#   scripts/postiz_tunnel_sync.sh          — полный отчёт: текущий адрес, что записано в ВМ, что менять
#   scripts/postiz_tunnel_sync.sh --check  — режим для systemd-таймера: молчит, когда всё синхронно,
#                                            и печатает предупреждение (в journald) при расхождении
# Коды возврата: 0 — синхронно, 1 — расхождение, 2 — не удалось определить адрес или прочитать ВМ.
set -uo pipefail

MODE="${1:-}"
TUNNEL_UNIT=cloudflared-postiz
STATE_FILE=/var/lib/cloudflared-postiz.url
VM_SSH=postiz@192.168.100.60
COMPOSE=/home/postiz/postiz/docker-compose.yml
SSH_OPTS=(-o ConnectTimeout=8 -o BatchMode=yes)

# say — только для полного режима; warn — всегда (это и есть предупреждение для журнала)
say() { [ "$MODE" = "--check" ] || printf '%s\n' "$*"; }
warn() { printf '%s\n' "$*"; }

case "$MODE" in
  ""|--check) ;;
  -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
  *) echo "usage: $0 [--check]" >&2; exit 2 ;;
esac

# --- 1. Текущий публичный адрес: журнал туннеля (свежее), затем state-файл ---
URL=$(journalctl -u "$TUNNEL_UNIT" --no-pager 2>/dev/null \
      | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)
SRC="journalctl -u $TUNNEL_UNIT"
if [ -z "$URL" ] && [ -r "$STATE_FILE" ]; then
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$STATE_FILE" | tail -1)
  SRC="$STATE_FILE"
fi
if [ -z "$URL" ]; then
  warn "postiz-tunnel-sync: НЕ найден публичный адрес туннеля (нет ни журнала $TUNNEL_UNIT, ни $STATE_FILE)"
  exit 2
fi
CUR_HOST=$(printf '%s' "$URL" | sed -E 's#^(https://[^/]+).*#\1#')

# --- 2. Что записано в ВМ ---
VM_HOSTS=$(ssh "${SSH_OPTS[@]}" "$VM_SSH" \
  "grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' '$COMPOSE' 2>/dev/null | sort -u" 2>/dev/null)
if [ -z "$VM_HOSTS" ]; then
  warn "postiz-tunnel-sync: не удалось прочитать $COMPOSE в ВМ ($VM_SSH, ssh недоступен или адреса нет)"
  exit 2
fi

DRIFT=$(printf '%s\n' "$VM_HOSTS" | grep -v -F -x "$CUR_HOST" || true)
if [ -z "$DRIFT" ]; then
  say "postiz-tunnel-sync: OK — адрес в ВМ совпадает с туннелем ($CUR_HOST, источник: $SRC)"
  # Дополнительно: state-файл никто не обновляет автоматически, покажем, если он отстал
  if [ -r "$STATE_FILE" ]; then
    ST=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$STATE_FILE" | tail -1)
    [ -n "$ST" ] && [ "$ST" != "$CUR_HOST" ] && say "  примечание: $STATE_FILE устарел ($ST) — обновите вручную"
  fi
  exit 0
fi

# --- 3. Расхождение: печатаем, что именно поменять ---
NEW="$CUR_HOST"
OLD=$(printf '%s\n' "$DRIFT" | head -1)
warn "postiz-tunnel-sync: АДРЕС ТУННЕЛЯ РАСХОДИТСЯ"
warn "  туннель сейчас ($SRC): $NEW"
warn "  в ВМ ($VM_SSH:$COMPOSE):"
printf '%s\n' "$VM_HOSTS" | while read -r h; do
  [ "$h" = "$NEW" ] && warn "    $h  (уже верно)" || warn "    $h  ← устарел"
done
warn "  ЧТО СДЕЛАТЬ (вручную, осознанно — скрипт ничего не меняет):"
warn "    1) в ВМ поправить compose и пересоздать контейнер postiz:"
warn "       ssh $VM_SSH \"cd /home/postiz/postiz && cp docker-compose.yml docker-compose.yml.bak-\$(date +%Y%m%d-%H%M%S) && sed -i 's#$OLD#$NEW#g' docker-compose.yml && docker compose up -d\""
warn "    2) обновить Redirect URI в кабинетах площадок (подробно: docs/PLATFORM_SETUP.md):"
warn "       Meta (Facebook/Instagram): $NEW/integrations/social/facebook , $NEW/integrations/social/instagram"
warn "       TikTok:                    $NEW/integrations/social/tiktok"
warn "       Google/YouTube:            $NEW/integrations/social/youtube"
warn "    3) после проверки публикации обновить $STATE_FILE (его никто не пишет автоматически)"
exit 1
