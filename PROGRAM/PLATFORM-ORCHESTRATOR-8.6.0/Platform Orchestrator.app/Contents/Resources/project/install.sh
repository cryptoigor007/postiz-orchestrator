#!/usr/bin/env bash
# =============================================================================
# Platform Orchestrator — ONE-CLICK INSTALL (HARD_CUT / module path)
# Usage:
#   curl -fsSL ... | bash   # if published
#   ./install.sh            # from repo root
#   ./install.sh --systemd  # also install user/system systemd unit
#   ./install.sh --prod     # no dry-run, prepare for real tokens
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

WITH_SYSTEMD=0
PROD=0
SKIP_SMOKE=0
NO_START=0
for arg in "$@"; do
  case "$arg" in
    --systemd) WITH_SYSTEMD=1 ;;
    --prod) PROD=1 ;;
    --skip-smoke) SKIP_SMOKE=1 ;;
    --no-start|--prepare-only) NO_START=1 ;;
    -h|--help)
      echo "Usage: ./install.sh [--systemd] [--prod] [--skip-smoke] [--no-start|--prepare-only]"
      exit 0
      ;;
  esac
done

log() { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
ok()  { printf '\033[1;32mOK\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR\033[0m %s\n' "$*" >&2; exit 1; }

log "Platform Orchestrator one-click install (HARD_CUT)"

# --- Python ---
if ! command -v python3 >/dev/null 2>&1; then
  die "python3 not found. Install Python 3.11+ (apt install python3 python3-venv python3-pip)"
fi
PY=python3
PV="$($PY -c 'import sys; print("%d.%d"%sys.version_info[:2])')"
ok "Python $PV"
$PY -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' \
  || die "Need Python >= 3.11 (found $PV)"

# ensure venv module
if ! $PY -c 'import venv' 2>/dev/null; then
  if command -v apt-get >/dev/null 2>&1 && [ "$(id -u)" -eq 0 ]; then
    log "Installing python3-venv via apt"
    apt-get update -qq && apt-get install -y -qq python3-venv python3-pip
  else
    die "python3 venv module missing. Debian/Ubuntu: sudo apt install python3-venv"
  fi
fi

# --- venv ---
log "Virtualenv"
if [ ! -d .venv ]; then
  if $PY -m venv .venv 2>/tmp/orch-venv.err; then
    ok "created .venv"
  elif $PY -m venv --copies .venv 2>/tmp/orch-venv.err; then
    ok "created .venv (--copies)"
  else
    msg="$(head -1 /tmp/orch-venv.err 2>/dev/null || true)"
    die "Unable to create .venv. Install the Python venv module (Debian/Ubuntu: sudo apt install python3-venv) and retry. $msg"
  fi
else
  ok ".venv exists"
fi
# shellcheck disable=SC1091
source .venv/bin/activate
PIP="python -m pip"
$PIP install -q --upgrade pip wheel

# --- deps ---
log "Dependencies"
DEPS_FILE="requirements.txt"
[ -f requirements.lock ] && DEPS_FILE="requirements.lock"
log "Installing dependencies from $DEPS_FILE"
$PIP install -q -r "$DEPS_FILE" || die "Dependency installation failed from $DEPS_FILE"
DEPS_HASH="$($PY -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$DEPS_FILE")"
printf '%s\n' "$DEPS_HASH" > .venv/.deps_hash
ok "dependencies installed and stamped"

# --- dirs / config ---
log "Config and directories"
mkdir -p data tokens backups logs
chmod 700 tokens 2>/dev/null || true
if [ ! -f config.yaml ]; then
  cp config.example.yaml config.yaml
  ok "config.yaml from example"
else
  ok "config.yaml kept"
fi
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  ok ".env from example"
fi

export PYTHONPATH="${ROOT}/src:${ROOT}/scripts${PYTHONPATH:+:$PYTHONPATH}"

# --- smoke ---
if [ "$SKIP_SMOKE" -eq 0 ]; then
  log "Smoke checks"
  python -m orchestrator.main --version || die "version smoke failed"
  if [ "$PROD" -eq 0 ]; then
    python -m orchestrator.main --config config.yaml --db data/orch.sqlite --dry-run --once \
      || die "dry-run smoke failed"
  fi
  python -c "from orchestrator.publisher import Publisher; from orchestrator.config import load_config; print('import ok')"
  ok "imports"
fi

# --- optional systemd ---
if [ "$WITH_SYSTEMD" -eq 1 ]; then
  log "Systemd unit"
  UNIT_DIR=""
  if [ "$(id -u)" -eq 0 ]; then
    UNIT_DIR=/etc/systemd/system
    USER_LINE="User=orchestrator"
    # create user if missing
    if ! id orchestrator >/dev/null 2>&1; then
      useradd --system --home "$ROOT" --shell /usr/sbin/nologin orchestrator || true
      chown -R orchestrator:orchestrator "$ROOT" || true
    fi
  else
    mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
    UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
    USER_LINE=""
  fi
  VENV_PY="$ROOT/.venv/bin/python"
  [ -x "$VENV_PY" ] || VENV_PY="$(command -v python3)"
  cat > "$UNIT_DIR/orchestrator.service" << UNIT
[Unit]
Description=Platform Orchestrator (HARD_CUT module path)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
${USER_LINE}
WorkingDirectory=$ROOT
Environment=PYTHONPATH=$ROOT/src:$ROOT/scripts
EnvironmentFile=-$ROOT/.env
ExecStart=$VENV_PY -m orchestrator.main --config $ROOT/config.yaml --db $ROOT/data/orch.sqlite --daemon --health-port 8080
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal
# Optional limits (drop-in also in deploy/orchestrator-cpu.conf)
Nice=10

[Install]
WantedBy=multi-user.target
UNIT
  if [ "$(id -u)" -eq 0 ]; then
    # merge CPU limits if present
    if [ -f deploy/orchestrator-cpu.conf ]; then
      mkdir -p /etc/systemd/system/orchestrator.service.d
      cp deploy/orchestrator-cpu.conf /etc/systemd/system/orchestrator.service.d/limits.conf
    fi
    systemctl daemon-reload
    if [ "$NO_START" -eq 0 ]; then
      systemctl enable orchestrator.service
      systemctl restart orchestrator.service || systemctl start orchestrator.service
      sleep 2
      systemctl is-active --quiet orchestrator.service && ok "systemd orchestrator.service active" \
        || echo "WARN: service not active yet — check: journalctl -u orchestrator -n 50"
    else
      ok "systemd unit written; not enabled/started (--no-start)"
    fi
  else
    systemctl --user daemon-reload 2>/dev/null || true
    if [ "$NO_START" -eq 0 ]; then
      systemctl --user enable --now orchestrator.service 2>/dev/null \
        && ok "user systemd unit enabled" \
        || ok "unit written to $UNIT_DIR (enable manually if needed)"
    else
      ok "user systemd unit written; not enabled/started (--no-start)"
    fi
  fi
fi

# --- final message ---
cat << MSG

==========================================
 INSTALL COMPLETE — HARD_CUT
==========================================
 Root:    $ROOT
 Config:  $ROOT/config.yaml
 Env:     $ROOT/.env
 Data:    $ROOT/data/orch.sqlite
 Tokens:  $ROOT/tokens/   (chmod 600 *.json)

 One-click run (foreground):
   ./start.sh

 Panel:   http://127.0.0.1:8080/webapp/
 Health:  http://127.0.0.1:8080/health

 Production tokens (after install):
   docs/PLATFORM_SETUP.md
   tokens/youtube.json · telegram bot in .env / config

 Gate:
   export PYTHONPATH=src:scripts
   bash scripts/gate_platform_zero.sh

 Systemd reinstall:
   sudo ./install.sh --systemd --prod
==========================================
MSG

if [ "$WITH_SYSTEMD" -eq 0 ] && [ "$NO_START" -eq 0 ]; then
  log "Starting local daemon (Ctrl+C to stop)…"
  exec python -m orchestrator.main --config config.yaml --db data/orch.sqlite --daemon --health-port 8080
fi

if [ "$NO_START" -eq 1 ]; then
  log "Install/prepare complete; daemon start skipped (--no-start)."
fi
