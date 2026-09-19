#!/bin/bash
# Project checks: lint, syntax, tests. Run before committing.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=./venv/bin/python
[ -x "$PY" ] || PY=python3
echo "[1/4] ruff"
if [ -x ./venv/bin/ruff ]; then ./venv/bin/ruff check src scripts tests; else echo "  (ruff not installed, skip)"; fi
echo "[2/4] python compile"
PYTHONPATH=src "$PY" -m compileall -q src scripts
echo "[3/4] node --check"
node --check webapp/app.js
echo "[4/4] pytest"
PYTHONPATH=src "$PY" -m pytest tests/ -q
echo "ALL CHECKS PASSED"
