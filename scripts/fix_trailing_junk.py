#!/usr/bin/env python3
"""Убирает невидимые мусорные символы (U+E000..U+F8FF) и пробелы по краям
из имён файлов/папок под указанными корнями и правит пути в базе оркестратора.

Запуск (на сервере, оркестратор лучше остановить):
    python3 fix_trailing_junk.py /mnt/video [--db /opt/orchestrator/data/data.sqlite]
"""
from __future__ import annotations

import os
import sqlite3
import sys
import unicodedata


def clean(name: str) -> str:
    s = "".join(ch for ch in name if unicodedata.category(ch) != "Co")
    s = s.strip()
    return s or name


def clean_path(p: str | None) -> str | None:
    if not p or not isinstance(p, str):
        return p
    return "/".join(clean(x) if x else x for x in p.split("/"))


def rename_all(root: str) -> tuple[int, int]:
    renamed = 0
    collisions = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        for name in filenames:
            if name.startswith("._"):
                continue
            new = clean(name)
            if new == name:
                continue
            src, dst = os.path.join(dirpath, name), os.path.join(dirpath, new)
            if os.path.exists(dst):
                base, ext = os.path.splitext(new)
                i = 2
                while os.path.exists(dst):
                    dst = os.path.join(dirpath, f"{base} ({i}){ext}")
                    i += 1
                collisions += 1
            os.rename(src, dst)
            renamed += 1
        for name in dirnames:
            new = clean(name)
            if new == name:
                continue
            src, dst = os.path.join(dirpath, name), os.path.join(dirpath, new)
            if os.path.exists(dst):
                i = 2
                while os.path.exists(dst):
                    dst = os.path.join(dirpath, f"{new} ({i})")
                    i += 1
                collisions += 1
            os.rename(src, dst)
            renamed += 1
    return renamed, collisions


TABLES = {
    "long_videos": ["folder_path", "wide_path", "vertical_path", "platform_paths"],
    "shorts": ["folder_path", "video_path", "cover_path", "platform_paths"],
    "platform_uploads": ["folder_path", "video_path", "cover_path"],
}


def fix_db(db_path: str) -> int:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    updates = 0
    for table, cols in TABLES.items():
        try:
            rows = db.execute("SELECT id, " + ", ".join(cols) + " FROM " + table).fetchall()
        except sqlite3.Error:
            continue
        for r in rows:
            newvals = {c: clean_path(r[c]) for c in cols}
            if any(newvals[c] != r[c] for c in cols):
                sets = ", ".join(c + "=?" for c in cols)
                db.execute(
                    "UPDATE " + table + " SET " + sets + " WHERE id=?",
                    [newvals[c] for c in cols] + [r["id"]],
                )
                updates += 1
    db.commit()
    return updates


def count_junk(root: str) -> int:
    bad = 0
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            if name.startswith("._"):
                continue
            if name != name.rstrip() or any(unicodedata.category(ch) == "Co" for ch in name):
                bad += 1
    return bad


def main() -> int:
    roots = [a for a in sys.argv[1:] if not a.startswith("--")]
    db_path = "/opt/orchestrator/data/data.sqlite"
    if "--db" in sys.argv:
        db_path = sys.argv[sys.argv.index("--db") + 1]
    if not roots:
        print("usage: fix_trailing_junk.py <root> [root...] [--db path]")
        return 2
    for root in roots:
        before = count_junk(root)
        renamed, collisions = rename_all(root)
        after = count_junk(root)
        print(f"{root}: было мусорных имён {before}, переименовано {renamed} "
              f"(коллизий {collisions}), осталось {after}")
    updates = fix_db(db_path)
    print("обновлено записей в базе:", updates)
    return 0


if __name__ == "__main__":
    sys.exit(main())
