#!/usr/bin/env python3
"""A3: статический линтер webapp-фронтенда.

Проверяет:
  1. нет сырых вставок данных API/ФС в HTML без esc() (path/parent/url/last_error/warning);
  2. нет инлайн-стилей (style="...") — CSP style-src без 'unsafe-inline';
  3. в CSP-коде нет 'unsafe-inline';
  4. во всех тестах build id не захардкожен.

Выход 1 с описанием при нарушении. Запускается в check.sh и CI.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "webapp" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "webapp" / "index.html").read_text(encoding="utf-8")
HTTP_SERVER = (ROOT / "src" / "orchestrator" / "http_server.py").read_text(encoding="utf-8")

RAW_DATA = re.compile(r"\$\{(?:it|d|x|b|r|c)\.(?:path|parent|url|last_error|warning)\}")
STYLE_ATTR = re.compile(r'\bstyle="')
problems: list[str] = []

for m in RAW_DATA.finditer(JS):
    line = JS[:m.start()].count("\n") + 1
    problems.append(f"app.js:{line}: сырая вставка без esc(): {m.group(0)}")

for name, text in (("app.js", JS), ("index.html", HTML)):
    if STYLE_ATTR.search(text):
        line = text[:STYLE_ATTR.search(text).start()].count("\n") + 1
        problems.append(f"{name}:{line}: инлайн-стиль (запрещён строгим CSP)")

code = "\n".join(ln for ln in HTTP_SERVER.splitlines() if not ln.strip().startswith("#"))
if "unsafe-inline" in code:
    problems.append("http_server.py: CSP содержит 'unsafe-inline'")

for f in sorted((ROOT / "tests").glob("test_*.py")):
    if "/webapp/b/" + "8" in f.read_text(encoding="utf-8"):
        problems.append(f"{f.name}: захардкожен build id (использовать WEBAPP_BUILD)")

if problems:
    print("XSS/CSP-ЛИНТЕР: найдены проблемы:")
    for p in problems:
        print("  -", p)
    sys.exit(1)

print("XSS/CSP-ЛИНТЕР: OK (esc-инварианты, без инлайн-стилей, строгий CSP, build-id)")
