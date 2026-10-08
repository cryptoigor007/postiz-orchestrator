#!/bin/bash
set -u
APP_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SOURCE="$APP_ROOT/Contents/Resources/project"
STATE_ROOT="${HOME}/Library/Application Support/Platform Orchestrator"
RELEASES="$STATE_ROOT/releases"
CURRENT="$STATE_ROOT/current"
VERSION="8.6.0"

show_error() {
  /usr/bin/osascript -e "display alert \"Platform Orchestrator\" message \"$1\" as critical buttons {\"OK\"}" >/dev/null 2>&1 || true
}

if [ ! -d "$SOURCE" ]; then
  show_error "Внутри приложения не найден runtime проекта."
  exit 1
fi

BUILD_ID_FILE="$SOURCE/RELEASE-BUILD-ID.txt"
if [ ! -f "$BUILD_ID_FILE" ]; then
  show_error "Внутри приложения отсутствует fingerprint сборки."
  exit 1
fi
BUNDLE_BUILD_ID="$(tr -d '\r\n' < "$BUILD_ID_FILE")"
if [ -z "$BUNDLE_BUILD_ID" ]; then
  show_error "Fingerprint сборки пустой."
  exit 1
fi

mkdir -p "$RELEASES" || { show_error "Не удалось создать каталог: $STATE_ROOT"; exit 1; }
TARGET="$RELEASES/$VERSION-$BUNDLE_BUILD_ID"

NEED_INSTALL=1
if [ -f "$TARGET/.app_release" ]; then
  INSTALLED_BUILD_ID="$(tr -d '\r\n' < "$TARGET/.app_release")"
  [ "$INSTALLED_BUILD_ID" = "$BUNDLE_BUILD_ID" ] && NEED_INSTALL=0
fi

if [ "$NEED_INSTALL" -eq 1 ]; then
  TMP="$RELEASES/.${VERSION}-${BUNDLE_BUILD_ID}.tmp.$$"
  rm -rf "$TMP"
  mkdir -p "$TMP" || { show_error "Не удалось подготовить runtime."; exit 1; }
  /usr/bin/ditto "$SOURCE" "$TMP" || { rm -rf "$TMP"; show_error "Не удалось распаковать runtime приложения."; exit 1; }

  # Preserve user-owned state from the previously active runtime.
  if [ -e "$CURRENT" ]; then
    for item in config.yaml .env data tokens backups logs; do
      if [ -e "$CURRENT/$item" ]; then
        rm -rf "$TMP/$item"
        /usr/bin/ditto "$CURRENT/$item" "$TMP/$item"
      fi
    done
  fi

  printf '%s\n' "$BUNDLE_BUILD_ID" > "$TMP/.app_release"
  rm -rf "$TARGET"
  mv "$TMP" "$TARGET"
fi

ln -sfn "$TARGET" "$CURRENT" || { show_error "Не удалось активировать runtime."; exit 1; }

chmod +x "$CURRENT/START.command" "$CURRENT/start.sh" "$CURRENT/install.sh" 2>/dev/null || true
nohup /usr/bin/open -a "Terminal" "$CURRENT/START.command" >/dev/null 2>&1 &
exit 0
