#!/bin/bash
# E4: GUI-smoke панели в jsdom против локально поднятого сервера.
# Используется в CI и локально: bash scripts/ci_gui_smoke.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY=python3
[ -x ./venv/bin/python ] && PY=./venv/bin/python
export WEBAPP_DEV=1
export ORCH_HTTP_BIND=127.0.0.1
export WEBAPP_ACCESS_KEY="${WEBAPP_ACCESS_KEY:-ci-test-key}"
ROOT="$(pwd)"

"$PY" - <<'PY' &
import sys, time
sys.path.insert(0, "src")
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.clock import SystemClock
from orchestrator.safety import SafetyChecker
from orchestrator.postiz import MockPostizClient
from orchestrator.publisher import Publisher
from orchestrator.scheduler import Scheduler
from orchestrator.telegram_bot import TelegramNotifier
from orchestrator.link_updater import LinkUpdater
from orchestrator.webapp_api import WebAppAPI
from orchestrator.http_server import start_http_server

cfg = load_config("config.yaml")
db = Database("data/ci_smoke.sqlite")
db.ensure_platform_states(list(cfg.platforms.keys()))
clk = SystemClock(); pz = MockPostizClient(); sf = SafetyChecker(db, cfg, clk)
pub = Publisher(db, cfg, pz, sf, clk, dry_run=True)
sch = Scheduler(db, cfg, pub, sf, clk); tg = TelegramNotifier(cfg, db, clk)
lu = LinkUpdater(db, cfg, pz, clk, tg)
api = WebAppAPI({"cfg": cfg, "db": db, "clock": clk, "safety": sf, "scheduler": sch,
                 "link_upd": lu, "publisher": pub, "postiz": pz})
srv = start_http_server(8899, lambda: {"ok": True}, api.handle)
print("CI smoke server on 8899", flush=True)
time.sleep(int(sys.argv[1]) if len(sys.argv) > 1 else 180)
PY
SERVER_PID=$!
disown $SERVER_PID 2>/dev/null || true
trap 'kill $SERVER_PID 2>/dev/null || true; rm -f data/ci_smoke.sqlite*' EXIT

for i in $(seq 1 30); do
  curl -sf http://127.0.0.1:8899/health >/dev/null 2>&1 && break
  sleep 1
done

URL=$("$PY" - <<'PYURL'
import os, sys
sys.path.insert(0, "src")
from orchestrator.webapp_api import WEBAPP_BUILD
print(f"http://127.0.0.1:8899/webapp/b/{WEBAPP_BUILD}/?key={os.environ['WEBAPP_ACCESS_KEY']}")
PYURL
)

cd "$ROOT/tests/gui"
if [ ! -d node_modules ]; then
  npm ci --silent 2>/dev/null || npm install --silent
fi
node check.mjs "$URL"
