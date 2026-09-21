"""8.3.0 UI: статические проверки mobile-first/reflow (tabbar, токены кнопок, safe-area, XSS-инварианты)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "webapp" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "webapp" / "styles.css").read_text(encoding="utf-8")
JS = (ROOT / "webapp" / "app.js").read_text(encoding="utf-8")


def test_tabbar_structure():
    """§2: нижний tabbar — 4 основных + «Ещё», без hidden (иначе display:none!important)."""
    m = re.search(r'<nav class="tabbar" id="tabbar"[^>]*>(.*?)</nav>', HTML, re.S)
    assert m, "tabbar отсутствует"
    block = m.group(1)
    assert not re.search(r"\shidden(?=[\s>])", m.group(0)), \
        "tabbar не должен быть hidden (перекрывается media-query)"
    views = re.findall(r'data-view="(\w+)"', block)
    assert views == ["status", "folders", "queue", "calendar"]
    assert 'data-more="1"' in block


def test_button_tokens():
    """§3: единые токены высоты и плотные варианты 36px."""
    for token in ("--btn-h: 44px", "--btn-h-sm: 36px", "--btn-pad-x", "--btn-radius: 12px"):
        assert token in CSS, f"нет токена {token}"
    assert "height: var(--btn-h)" in CSS
    assert re.search(r"\.q-row \.btn.*height: var\(--btn-h-sm\)", CSS, re.S), "плотные кнопки очереди не 36px"


def test_mobile_fullbleed_and_safe_areas():
    """§1: mobile — без max-width 980, tabbar-отступ контента, резерв под кнопку TG."""
    mob = CSS.split("@media (max-width: 640px)")[1]
    assert "max-width: none" in mob
    assert "var(--tabbar-h)" in mob
    assert "var(--sa-bottom)" in mob
    assert "var(--sa-right)" in mob  # инсет справа учитывает кнопки Telegram
    assert ".sidebar { display: none" in mob


def test_nav_labels_from_i18n_and_short():
    """§4: короткие подписи в I18N + обновление и сайдбара, и tabbar."""
    assert 'nav_status: "Обзор"' in JS and 'nav_status: "Home"' in JS
    assert 'nav_platforms: "Сети"' in JS and 'nav_platforms: "Social"' in JS
    assert "updateNavLabels" in JS
    assert '#nav button[data-view], #tabbar button[data-view]' in JS


def test_newbie_ux_and_sheet():
    """§4.3/§2: шторка «Ещё», stepper на Видео, CTA на Обзоре."""
    assert "function openMoreSheet" in JS and "function gotoView" in JS
    assert 'data-goto="folders"' in JS and 'data-goto="queue"' in JS
    assert "folders_stepper" in JS and "folders_stepper" in HTML or "folders_stepper" in JS


def test_xss_invariants_still_hold():
    """§8: esc() не откатан — нет сырых path/title/url в HTML-шаблонах."""
    assert JS.count("esc(") >= 60
    # name/title используются как ключи (settings["group:"+name]) — проверяем
    # именно утечки путей/URL/ошибок без esc()
    bad = re.findall(r"\$\{(?:it|d|x|b|r|c)\.(?:path|parent|url|last_error|warning)\}", JS)
    assert not bad, f"сырые вставки без esc(): {bad[:3]}"


def test_csp_nonce_untouched():
    """§8: CSP nonce для скриптов не сломан."""
    api = (ROOT / "src" / "orchestrator" / "webapp_api.py").read_text(encoding="utf-8")
    assert "_compose_index(self._key_from_request(qpath, query), nonce)" in api
    assert "nonce" in api and "_webapp_nonce" in api


def test_no_hardcoded_build_in_tests():
    """Урок b811→813: build id в тестах — только динамически."""
    for f in (ROOT / "tests").glob("test_*.py"):
        t = f.read_text(encoding="utf-8")
        needle = "/webapp/b/" + "8"
        assert needle not in t, f"{f.name}: захардкожен build id"


def test_primary_single_per_form_row():
    """§3.5: в одном form-row не более одной primary."""
    for line in JS.splitlines():
        assert not (line.count("btn primary") > 1), f"несколько primary в строке: {line[:80]}"


def _obj_body(text, start_brace):
    i, depth, in_str, esc = start_brace, 0, False, False
    while i < len(text):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start_brace + 1:i]
        i += 1
    raise ValueError("unbalanced object")


def _i18n_keys(name):
    import re as _re

    text = JS
    i18n_brace = text.index("{", text.index("const I18N = {"))
    body = _obj_body(text, i18n_brace)
    off = i18n_brace + 1
    m = _re.search(rf"\b{name}\s*:\s*\{{", body)
    start = off + body.index("{", m.start())
    inner = _obj_body(text, start)
    keys, i, in_str, esc = set(), 0, False, False
    while i < len(inner):
        ch = inner[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        mm = _re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*:", inner[i:])
        if mm:
            keys.add(mm.group(1))
            i += mm.end()
            continue
        i += 1
    return keys


def test_i18n_complete_and_symmetric():
    """Все t("key") определены в ru и en; словари симметричны."""
    import re as _re

    used = set(_re.findall(r'(?<![\w$])t\("([A-Za-z0-9_]+)"\)', JS))
    ru, en = _i18n_keys("ru"), _i18n_keys("en")
    assert not (used - ru), f"нет в ru: {sorted(used - ru)[:5]}"
    assert not (used - en), f"нет в en: {sorted(used - en)[:5]}"
    assert ru == en, f"словари рассинхронизированы: {sorted(ru ^ en)[:5]}"


def test_roots_row_not_force_stretched():
    """Выбор корней не растягивается правилом full-width primary (иначе «синяя стена»)."""
    assert "roots-row" in JS and "roots-row" in CSS
    assert ".form-row:not(.roots-row)" in CSS


def test_no_inline_styles_and_strict_csp():
    """A2: ни одного style-атрибута; CSP без 'unsafe-inline' (script и style)."""

    assert 'style="' not in JS, "в app.js остались инлайн-стили"
    assert 'style="' not in HTML, "в index.html остались инлайн-стили"
    api = (ROOT / "src" / "orchestrator" / "webapp_api.py").read_text(encoding="utf-8")
    assert 'style="' not in api  # шаблоны страницы тоже без инлайна
    csp_src = (ROOT / "src" / "orchestrator" / "http_server.py").read_text(encoding="utf-8")
    csp_code = "\n".join(ln for ln in csp_src.splitlines() if not ln.strip().startswith("#"))
    assert "unsafe-inline" not in csp_code, "CSP всё ещё содержит unsafe-inline"
    assert "style-src 'self'" in csp_code and "nonce-" in csp_code
    assert "Referrer-Policy" in csp_src
    # утилиты, заменившие инлайн, есть в CSS
    for cls in (".w-full", ".flex-1", ".wrap-any", ".pico-20", ".pbar-fill"):
        assert cls in CSS, f"нет утилиты {cls}"
