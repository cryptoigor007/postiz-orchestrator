#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/Platform Orchestrator.app"
RES="$APP/Contents/Resources/project"

command -v rsync >/dev/null 2>&1 || { echo "ERROR: rsync is required" >&2; exit 1; }

# The embedded project is immutable payload only; user state belongs in App Support.
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/project"

/usr/bin/rsync -a --delete \
  --exclude='.git/' \
  --exclude='.github/' \
  --exclude='.githooks/' \
  --exclude='.pytest_cache/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.venv/' \
  --exclude='tests/' \
  --exclude='data/' \
  --exclude='tokens/' \
  --exclude='backups/' \
  --exclude='logs/' \
  --exclude='checkpoints/' \
  --exclude='archive/' \
  --exclude='config.yaml' \
  --exclude='.env' \
  --exclude='*.bak*' \
  --exclude='Platform Orchestrator.app/' \
  --exclude='*.zip' \
  --exclude='*.tar.gz' \
  --exclude='RELEASE-BUILD-ID.txt' \
  "$ROOT/" "$RES/"

# Build fingerprint covers executable/runtime inputs but ignores user state and test caches.
BUILD_ID="$(cd "$RES" && find . -type f ! -name 'RELEASE-BUILD-ID.txt' ! -name 'RELEASE-REPORT-*.md' ! -name 'RELEASE-MANIFEST-*.txt' ! -name 'RELEASE-CONTENTS-*.txt' -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256 | awk '{print $1}')"
printf '%s\n' "$BUILD_ID" > "$RES/RELEASE-BUILD-ID.txt"

cp "$ROOT/scripts/macos_app_Info.plist" "$APP/Contents/Info.plist"
cp "$ROOT/scripts/macos_app_launcher.sh" "$APP/Contents/MacOS/Platform Orchestrator"
chmod +x "$APP/Contents/MacOS/Platform Orchestrator" "$RES/START.command" "$RES/start.sh" "$RES/install.sh"

echo "Built $APP"
echo "Build ID: $BUILD_ID"
