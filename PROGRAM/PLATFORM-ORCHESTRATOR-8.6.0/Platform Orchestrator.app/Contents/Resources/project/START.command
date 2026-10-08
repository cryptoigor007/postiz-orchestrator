#!/bin/bash
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1
# Keep Finder-launched sessions visible so bootstrap/runtime errors are not lost.
bash ./start.sh
rc=$?
if [ "$rc" -ne 0 ]; then
  echo ""
  echo "Platform Orchestrator завершился с ошибкой (код $rc)."
  echo "Каталог: $ROOT"
  echo ""
  read -r -p "Нажмите Enter, чтобы закрыть окно..." _
fi
exit "$rc"
