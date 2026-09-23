#!/bin/bash
# Сменить OAuth-клиент YouTube в Postiz и пересоздать контейнер.
# Использование: set_youtube_oauth.sh <CLIENT_ID> <CLIENT_SECRET>
set -euo pipefail
cd /home/postiz/postiz
CID="${1:?usage: set_youtube_oauth.sh <client_id> <client_secret>}"
CSEC="${2:?usage: set_youtube_oauth.sh <client_id> <client_secret>}"
cp docker-compose.yml "docker-compose.yml.bak.$(date +%s)"
sed -i -E "s#^([[:space:]]*-[[:space:]]*)YOUTUBE_CLIENT_ID=.*#\1YOUTUBE_CLIENT_ID=${CID}#" docker-compose.yml
sed -i -E "s#^([[:space:]]*-[[:space:]]*)YOUTUBE_CLIENT_SECRET=.*#\1YOUTUBE_CLIENT_SECRET=${CSEC}#" docker-compose.yml
grep -n "YOUTUBE_CLIENT_ID\|YOUTUBE_CLIENT_SECRET" docker-compose.yml
docker compose up -d --force-recreate postiz
# ждём, пока бэкенд поднимет :3000 (иначе nginx отдаёт 502 на старом IP)
for i in $(seq 1 18); do
  if docker exec postiz bash -c "ss -tulpn | grep -q :3000"; then
    echo "backend up after $((i*5))s"; break
  fi
  sleep 5
done
docker restart postiz-nginx-https-1 >/dev/null
sleep 4
echo "postiz=$(docker inspect -f '{{.State.Status}}' postiz)"
curl -sk -o /dev/null -w "api/login http=%{http_code}\n" -X POST https://192-168-100-60.sslip.io/api/auth/login -H "Content-Type: application/json" -d '{}' || true
