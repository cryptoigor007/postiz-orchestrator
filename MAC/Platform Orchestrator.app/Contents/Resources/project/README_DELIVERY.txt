AGENT HANDOFF — platform-orchestrator (HARD_CUT / module path)
=============================================================
STATUS=HARD_CUT · SCHEMA_VERSION=19 · gate: scripts/gate_platform_zero.sh

Bootstrap:
  START.md
  docs/PLATFORM_SETUP.md
  deploy/README.md
  REPORT-HARD-CUT.txt

Install:
  python3 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  cp config.example.yaml config.yaml
  # engines: module:youtube / module:telegram / …

Anti-regression (module path, no Postiz transport):
  export PYTHONPATH=src:scripts
  bash scripts/gate_platform_zero.sh
  python3 -m pytest tests/ -q
  # or: ./scripts/check.sh

Rules:
  - No Postiz client in src/ (only db.py RENAME pair)
  - No dual-write legacy_*
  - Secrets not in git; tokens in tokens/*.json
  - Do not enable deploy postiz-* units (DEPRECATED)

Known external limits: Meta/TikTok App Review, quotas, B2, DNS/tunnel;
browser experimental; TikTok inbox process-local (EPS = SoT).
