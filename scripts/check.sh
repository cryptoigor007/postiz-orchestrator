#!/bin/bash
# Project checks: lint, syntax, tests. Run before committing.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=./venv/bin/python
[ -x "$PY" ] || PY=python3
echo "[1/5] ruff"
if [ -x ./venv/bin/ruff ]; then ./venv/bin/ruff check src scripts tests; else echo "  (ruff not installed, skip)"; fi
echo "[2/5] python compile"
PYTHONPATH=src "$PY" -m compileall -q src scripts
echo "[3/5] xss/csp linter"
"$PY" scripts/check_xss.py
echo "[4/5] node --check"
node --check webapp/app.js
echo "[5/5] pytest"
PYTHONPATH=src "$PY" -m pytest tests/ -q
(./venv/bin/vulture src/orchestrator scripts --min-confidence 100 || { echo "VULTURE: dead code found"; exit 1; }) 2>/dev/null
echo "ALL CHECKS PASSED"
