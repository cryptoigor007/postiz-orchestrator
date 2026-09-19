#!/bin/bash
# Залить проект на GitHub. Создаёт репозиторий (если дан токен) и пушит.
#
# Использование:
#   scripts/push_github.sh <github_user>                 # через SSH-ключ
#   scripts/push_github.sh <github_user> <token>         # создать репо по API + HTTPS
#   REPO=my-name scripts/push_github.sh <github_user> [token]
set -euo pipefail
GH_USER="${1:?usage: push_github.sh <github_user> [token]}"
TOKEN="${2:-}"
REPO="${REPO:-postiz-orchestrator}"
cd "$(dirname "$0")/.."

git branch -M master

if [ -n "$TOKEN" ]; then
  echo ">> создаю репозиторий $GH_USER/$REPO (private) через API"
  curl -s -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" \
    https://api.github.com/user/repos \
    -d "{\"name\":\"$REPO\",\"private\":true,\"description\":\"Publishing orchestrator: VideoMaker/ShortsMaker -> Postiz, WebApp, MCP\"}" >/dev/null || true
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://$GH_USER:$TOKEN@github.com/$GH_USER/$REPO.git"
  git push -u origin master
  git remote set-url origin "https://github.com/$GH_USER/$REPO.git"   # убрать токен из remote
else
  git remote remove origin 2>/dev/null || true
  git remote add origin "git@github.com:$GH_USER/$REPO.git"
  git push -u origin master
fi
echo "Готово: https://github.com/$GH_USER/$REPO"
