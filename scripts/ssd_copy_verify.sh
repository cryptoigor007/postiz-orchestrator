#!/bin/bash
# Полная сверка копии SSD ↔ сервер: наличие + размеры всех файлов (с нормализацией Unicode/пробелов).
# Запуск:  bash scripts/ssd_copy_verify.sh "/Volumes/SSD" root@192.168.100.40:/mnt/video/ssd_backup
set -euo pipefail
SRC="${1:-/Volumes/SSD}"
DST_SSH="${2:-root@192.168.100.40}"
DST_DIR="${3:-/mnt/video/ssd_backup}"

python3 - "$SRC" "$DST_SSH" "$DST_DIR" <<'PY'
import os, subprocess, sys, unicodedata

src, dst_ssh, dst_dir = sys.argv[1], sys.argv[2], sys.argv[3]
EXCL = {"$RECYCLE.BIN", ".Spotlight-V100", ".Trashes", ".fseventsd", ".TemporaryItems",
        "System Volume Information"}

def norm(p):
    return unicodedata.normalize("NFC", "/".join(x.strip() for x in p.split("/")))

def walk(root):
    out = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCL]
        for f in files:
            if f.startswith("._") or f == ".DS_Store":
                continue
            fp = os.path.join(base, f)
            try:
                out[norm(os.path.relpath(fp, root))] = os.path.getsize(fp)
            except OSError:
                out[norm(os.path.relpath(fp, root))] = -1
    return out

local = walk(src)
remote_raw = subprocess.run(
    ["ssh", "-o", "BatchMode=yes", dst_ssh,
     f"cd '{dst_dir}' && find . -type f -printf '%s\\t%p\\n'"],
    capture_output=True, text=True, check=True).stdout
remote = {}
for line in remote_raw.splitlines():
    if not line.strip():
        continue
    size, rel = line.split("\t", 1)
    remote[norm(rel.lstrip("./"))] = int(size)

miss = [r for r in local if r not in remote]
diff = [r for r in local if r in remote and local[r] != remote[r] and local[r] > 0]
extra = [r for r in remote if r not in local]
print(f"SSD: {len(local)} | сервер: {len(remote)}")
print(f"НЕ ХВАТАЕТ: {len(miss)} | РАЗМЕРЫ ОТЛИЧАЮТСЯ: {len(diff)} | лишних: {len(extra)}")
for r in miss[:20]:
    print("  -", r)
for r in diff[:20]:
    print("  ~", r, local[r], remote[r])
sys.exit(1 if (miss or diff) else 0)
PY
