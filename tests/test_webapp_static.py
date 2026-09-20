"""Статические проверки webapp/app.js: все вызываемые функции должны быть определены.

Ловит класс ошибок «unbusy is not defined» (панель зависала после удаления).
"""
from __future__ import annotations

import re
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "webapp" / "app.js"

ALLOWED = {
    "if", "for", "while", "switch", "catch", "function", "return", "typeof", "new",
    "await", "else", "do", "try", "delete", "void", "in", "of", "instanceof", "yield",
    "async", "fetch", "setTimeout", "clearTimeout", "setInterval", "clearInterval",
    "parseInt", "parseFloat", "String", "Number", "Boolean", "Array", "Object", "JSON",
    "Math", "Date", "Promise", "Error", "Map", "Set", "RegExp", "encodeURIComponent",
    "decodeURIComponent", "isNaN", "console", "alert", "confirm", "prompt",
    "requestAnimationFrame", "AbortController", "FileReader", "URLSearchParams", "URL",
    "Symbol", "WeakMap", "WeakSet", "btoa", "atob", "structuredClone", "queueMicrotask",
    # ключи объектов/строки в шаблонах (ложные срабатывания эвристики)
    "backlog", "button", "date", "folder", "match", "platforms", "post", "posts",
    "queue", "respond", "series", "shorts", "slots", "up", "window", "document",
}


def test_all_called_functions_defined():
    src = APP_JS.read_text(encoding="utf-8")
    defined = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)\s*\(", src))
    defined |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\()", src))
    defined |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?[A-Za-z_$][\w$]*\s*=>", src))
    calls = set(re.findall(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(", src))
    unknown = sorted(c for c in calls - defined - ALLOWED)
    assert not unknown, f"Вызовы без определения (панель упадёт): {unknown}"
