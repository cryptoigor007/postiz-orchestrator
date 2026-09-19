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
docker restart postiz-nginx-https-1 >/dev/null
sleep 5
echo "postiz=$(docker inspect -f '{{.State.Status}}' postiz)"
