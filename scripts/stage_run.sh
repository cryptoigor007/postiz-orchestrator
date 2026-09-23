#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/src"
DB="${DB:-/tmp/orchestrator_stage.sqlite}"
CFG="${CFG:-$ROOT/config.stage.yaml}"
echo "=== version ==="
python3 -m orchestrator.main --version
echo "=== once dry-run ==="
python3 -m orchestrator.main --config "$CFG" --db "$DB" --dry-run --once
echo "=== done DB=$DB ==="
echo "Real Postiz: unset dry-run, set POSTIZ_API_TOKEN and POSTIZ_BASE_URL"
