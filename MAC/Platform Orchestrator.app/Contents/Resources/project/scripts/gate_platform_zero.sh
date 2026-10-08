#!/bin/bash
# Platform orchestrator HARD CUT acceptance gate (no legacy transport client)
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src:scripts
PY=python3
echo "[gate] config.ci"
[ -f config.ci.yaml ] || { echo "missing config.ci.yaml"; exit 1; }
echo "[gate] pytest platform_zero"
$PY -m pytest tests/test_platform_zero_c*.py tests/test_platform_zero_f*.py \
  tests/test_platform_zero_hardcut.py -q --tb=line
echo "[gate] no legacy_post_id non-null writes in runtime"
set +e
HITS=$(grep -RnE 'legacy_post_id=\?|legacy_scheduled_for=\?' src/orchestrator \
  2>/dev/null | grep -vE 'db\.py|#' | grep -vE '=NULL' || true)
set -e
if [ -n "$HITS" ]; then
  echo "$HITS"
  echo "WRITE GATE FAIL"
  exit 1
fi
echo "[gate] no bare ORDER BY legacy_scheduled_for without COALESCE"
set +e
HITS2=$(grep -RnE 'ORDER BY eps\.legacy_scheduled_for[^,]|legacy_scheduled_for IS NOT NULL' src/orchestrator \
  2>/dev/null | grep -vE 'db\.py|COALESCE|#' || true)
set -e
if [ -n "$HITS2" ]; then
  echo "$HITS2"
  echo "ORDER BY GATE FAIL"
  exit 1
fi
echo "[gate] no active legacy transport/field reads in runtime"
if grep -RniE 'n8n_source|from \.engines\.(base|registry|direct_youtube|browser_engine|n8n_engine)|legacy_post_id|legacy_scheduled_for|COALESCE\([^)]*legacy' src/orchestrator --include='*.py' | grep -v 'src/orchestrator/db.py' | grep -v 'src/orchestrator/test_publish.py' >/tmp/orch_legacy_reads.$$; then
  cat /tmp/orch_legacy_reads.$$
  rm -f /tmp/orch_legacy_reads.$$
  exit 1
fi
rm -f /tmp/orch_legacy_reads.$$
echo "[gate] no postiz word in src runtime (except db migration pair)"
set +e
HITS3=$(grep -Rni 'postiz' src/ 2>/dev/null | grep -vE 'db\.py:.*postiz_post_id|db\.py:.*postiz_scheduled' || true)
set -e
if [ -n "$HITS3" ]; then
  echo "$HITS3"
  echo "POSTIZ WORD GATE FAIL"
  exit 1
fi
echo "[gate] core imports"
$PY -c "from orchestrator.media import make_media, maybe_compress"
$PY -c "from orchestrator.publisher import Publisher"
$PY -c "from orchestrator.config import load_config; load_config('config.ci.yaml')"
$PY -c "from orchestrator.status_sync import StatusSync"
$PY -c "from orchestrator.webapp_api import WebAppAPI"

echo "[gate] no postiz in webapp"
set +e
HITS_W=$(grep -Rni 'postiz' webapp/ 2>/dev/null || true)
set -e
if [ -n "$HITS_W" ]; then
  echo "$HITS_W"
  echo "WEBAPP POSTIZ FAIL"
  exit 1
fi

if [ "${FULL:-0}" = "1" ]; then
  echo "[gate] full pytest"
  $PY -m pytest tests/ -q --tb=line
fi

echo "[gate] OK"
