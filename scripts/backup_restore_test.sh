#!/usr/bin/env bash
# Проверка, что из бэкапа реально ВОССТАНАВЛИВАЕТСЯ, а не только «файлы на месте».
#
# Что делает:
#   1) распаковывает архив;
#   2) читает config.yaml настоящим загрузчиком оркестратора (конфиг должен разобраться);
#   3) открывает базу очереди и считает таблицы/строки (база должна быть живой);
#   4) разворачивает дамп Postiz в ЧИСТЫЙ временный Postgres на VM (прод не трогает)
#      и проверяет, что базы и таблицы появились; контейнер после проверки удаляется.
#
# Запуск с Mac:  bash scripts/backup_restore_test.sh [путь к архиву]
# Выход: 0 — восстановление подтверждено, 1 — что-то не восстановилось.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${BACKUP_DIR:-$HOME/backups}"
PVE_HOST="${PVE_HOST:-root@100.95.225.71}"
VM_IP="192.168.100.60"
ARCHIVE="${1:-}"
if [ -z "$ARCHIVE" ]; then
  ARCHIVE="$(ls -1t "$DEST"/orch-server-*.tar.gz 2>/dev/null | head -1 || true)"
fi
[ -n "$ARCHIVE" ] && [ -f "$ARCHIVE" ] || { echo "архив не найден (искал в $DEST)"; exit 2; }

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
tar -xzf "$ARCHIVE" -C "$WORK"
ROOT="$(find "$WORK" -maxdepth 1 -mindepth 1 -type d | head -1)"
echo ">> проверяю восстановление из $(basename "$ARCHIVE")"

# ── 1. Оркестратор: конфиг и база ───────────────────────────────────────────────
echo "-- оркестратор: конфиг, база, секреты"
"$REPO/venv/bin/python" - "$ROOT" "$REPO" <<'PY'
import sqlite3
import sys
from pathlib import Path

root, repo = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(repo / "src"))
from orchestrator.config import load_config  # noqa: E402

cfg = load_config(root / "orchestrator" / "config.yaml")
projects = list(getattr(cfg, "projects", {}) or {})
print(f"  ок   конфиг разобран его же загрузчиком: проектов {len(projects)} {projects}, "
      f"платформ {len(cfg.platforms)}, по умолчанию {getattr(cfg, 'default_project', '')!r}")

db = sqlite3.connect(f"file:{root / 'orchestrator' / 'data' / 'data.sqlite'}?mode=ro", uri=True)
tables = [r[0] for r in db.execute("select name from sqlite_master where type='table'")]
total = sum(db.execute(f'select count(*) from "{n}"').fetchone()[0]
            for n in tables if n != "sqlite_sequence")
print(f"  ок   база очереди открыта: таблиц {len(tables)}, строк {total}")
assert total > 0, "база пустая"
for need in ("long_videos", "shorts", "entity_platform_status"):
    assert need in tables, f"в базе нет таблицы {need}"
print("  ок   ключевые таблицы на месте: длинные видео, шортсы, статусы платформ")

env = (root / "orchestrator" / ".env").read_text(encoding="utf-8", errors="replace")
for key in ("TELEGRAM_BOT_TOKEN", "WEBAPP_ACCESS_KEY"):
    assert key in env, f"в .env нет {key}"
print("  ок   .env содержит токен бота и ключ панели")
PY

# ── 2. Postiz: дамп разворачивается в чистый Postgres ──────────────────────────
echo "-- Postiz: дамп в чистый временный Postgres (прод не трогаем)"
DUMP="$ROOT/postiz/postiz-all-databases.sql.gz"
[ -f "$DUMP" ] || { echo "  НЕТ  дампа Postiz в архиве"; exit 1; }

# копируем дамп на VM (тут вложенный ssh НЕ с -n: он должен принять поток на stdin)
gzip -dc "$DUMP" | ssh -o BatchMode=yes "$PVE_HOST" "ssh -o BatchMode=yes root@$VM_IP 'cat > /tmp/restore-check.sql'"
echo "  ок   дамп ($(du -h "$DUMP" | cut -f1)) передан на VM"

# ВАЖНО: без -n — блок передаётся на VM через stdin
OUT="$(ssh -o BatchMode=yes "$PVE_HOST" "ssh -o BatchMode=yes root@$VM_IP 'bash -s'" <<'REMOTE'
set -euo pipefail
C=restore-check
docker rm -f $C >/dev/null 2>&1 || true
docker run -d --name $C -e POSTGRES_PASSWORD=tmp -e POSTGRES_USER=postiz postgres:15-alpine >/dev/null
cleanup() { docker rm -f $C >/dev/null 2>&1 || true; rm -f /tmp/restore-check.sql; }
trap cleanup EXIT
for _ in $(seq 1 40); do docker exec $C pg_isready -U postiz >/dev/null 2>&1 && break; sleep 1; done
docker exec $C pg_isready -U postiz >/dev/null 2>&1 || { echo "  НЕТ  временный Postgres не поднялся"; exit 1; }
echo "  ок   временный Postgres поднят (postgres:15-alpine)"
docker exec -i $C psql -U postiz -q < /tmp/restore-check.sql >/dev/null
echo "  ок   дамп развёрнут"
BASES="$(docker exec $C psql -U postiz -tAc "select datname from pg_database where datname not like 'template%' and datname <> 'postgres' order by 1" | tr '\n' ' ')"
echo "  ок   базы после восстановления: $BASES"
T="$(docker exec $C psql -U postiz -d postiz -tAc "select count(*) from information_schema.tables where table_schema='public'")"
echo "  ок   таблиц в базе postiz: $T"
[ "${T:-0}" -gt 10 ] || { echo "  НЕТ  в базе postiz подозрительно мало таблиц"; exit 1; }
echo "RESTORE-CHECK-OK"
REMOTE
)"

printf '%s\n' "$OUT"
case "$OUT" in
  *RESTORE-CHECK-OK*) : ;;
  *) echo "  НЕТ  проверка на VM не выполнилась (нет подтверждения RESTORE-CHECK-OK)"; exit 1 ;;
esac

echo
echo "ИТОГ: восстановление подтверждено — конфиг читается, база оркестратора живая, базы Postiz разворачиваются с нуля."
