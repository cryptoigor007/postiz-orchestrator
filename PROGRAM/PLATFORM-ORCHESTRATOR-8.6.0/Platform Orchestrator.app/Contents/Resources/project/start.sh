#!/usr/bin/env bash
# One-click start — ensures install then runs daemon
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
export PYTHONPATH=src:scripts
export ORCH_READ_ONLY="${ORCH_READ_ONLY:-0}"

echo "=========================================="
echo " Platform Orchestrator — HARD_CUT start"
echo "=========================================="

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.11+ and retry."
  exit 1
fi

if [ ! -d .venv ] || [ ! -f .venv/bin/activate ]; then
  echo "[bootstrap] running install.sh --skip-smoke …"
  bash ./install.sh --skip-smoke --no-start
fi

if [ ! -x .venv/bin/python ]; then
  echo "ERROR: .venv was not created by install.sh" >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# deps if requirements newer than venv stamp
DEPS_FILE="requirements.lock"
[ -f "$DEPS_FILE" ] || DEPS_FILE="requirements.txt"
DEPS_HASH="$(python - <<PY
import hashlib, pathlib
p=pathlib.Path("$DEPS_FILE")
print(hashlib.sha256(p.read_bytes()).hexdigest())
PY
)"
if [ ! -f .venv/.deps_hash ] || [ "$(cat .venv/.deps_hash 2>/dev/null)" != "$DEPS_HASH" ]; then
  echo "[deps] pip install -r $DEPS_FILE …"
  python -m pip install -q -r "$DEPS_FILE"
  printf "%s\n" "$DEPS_HASH" > .venv/.deps_hash
fi

[ -f config.yaml ] || cp config.example.yaml config.yaml
[ -f .env ] || { [ -f .env.example ] && cp .env.example .env || true; }
mkdir -p data tokens backups logs
chmod 700 tokens 2>/dev/null || true

echo "[smoke] version"
python -m orchestrator.main --version
python -m orchestrator.main --config config.yaml --db data/orch.sqlite --dry-run --once

echo "[run] http://127.0.0.1:8080/webapp/  health: /health  (Ctrl+C stop)"
echo "=========================================="
exec python -m orchestrator.main --config config.yaml --db data/orch.sqlite --daemon --health-port 8080
