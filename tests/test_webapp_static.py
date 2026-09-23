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
    "window", "document", "getComputedStyle", "matchMedia", "navigator", "location",
    "MutationObserver",  # P5: маска у края скроллера чипов пересчитывается на перерисовку
}


def _strip_strings(src: str) -> str:
    """Убирает строковые литералы, СОХРАНЯЯ выражения внутри ${...} шаблонов."""
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in "\"'":
            q = c
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == q:
                    i += 1
                    break
                i += 1
            out.append(" ")
        elif c == "`":
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == "$" and i + 1 < n and src[i + 1] == "{":
                    j, depth, expr = i + 2, 1, []
                    while j < n and depth:
                        if src[j] == "{":
                            depth += 1
                        elif src[j] == "}":
                            depth -= 1
                        if depth:
                            expr.append(src[j])
                        j += 1
                    out.append(" (" + _strip_strings("".join(expr)) + ") ")
                    i = j
                    continue
                if src[i] == "`":
                    i += 1
                    break
                i += 1
            out.append(" ")
        else:
            out.append(c)
            i += 1
    return "".join(out)


def test_all_called_functions_defined():
    src = _strip_strings(APP_JS.read_text(encoding="utf-8"))
    defined = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)\s*\(", src))
    defined |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\()", src))
    defined |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?[A-Za-z_$][\w$]*\s*=>", src))
    calls = set(re.findall(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(", src))
    unknown = sorted(c for c in calls - defined - ALLOWED)
    assert not unknown, f"Вызовы без определения (панель упадёт): {unknown}"
