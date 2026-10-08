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
    """§3: единые токены высоты и плотные варианты.

    8.4.51 (P5): одна семья контролов. Кнопка (.btn, .btn.sm) — нажатие и поверхность
    44px (--ctl-h); плотная поверхность 36px (--ctl-hv) остаётся только у чипов,
    вкладок сегмента и переключателя языка (и рисуется внутри 44px нажатия).
    Было: .btn.sm 36px с радиусом 10px — «мелкая» кнопка вне семьи.
    """
    for token in ("--btn-h: 44px", "--btn-h-sm: 36px", "--btn-pad-x", "--btn-radius: 12px",
                  "--ctl-h: var(--btn-h)", "--ctl-hv: var(--btn-h-sm)", "--ctl-r: 12px"):
        assert token in CSS, f"нет токена {token}"
    assert "height: var(--btn-h)" in CSS
    sm = _css_rule(".btn.sm")
    assert "height: var(--ctl-h)" in sm, "компактная кнопка не 44px (тап-цель меньше 44px)"
    assert "border-radius: var(--ctl-r)" in sm, "радиус компактной кнопки не из семьи"
    # (мёртвые селекторы .q-row/.queue-col/.status-btn в CSS оставлены как есть — вне правки;
    # проверяем живую часть того же правила: кнопки поиска папок и шапки панели)
    assert "height: var(--ctl-h)" in _css_rule(".panel-header .btn, .search-list .btn"), \
        "кнопки поиска папок/шапки панели выпали из семьи (не 44px)"
    assert "border-radius: var(--ctl-r)" in _css_rule(".panel-header .btn, .search-list .btn"), \
        "радиус кнопок поиска не из семьи"


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


def test_calendar_month_cell_containment():
    """S1: иконки платформ в ячейке месяца не вылезают за её границы.

    Регрессия: пост на 5 платформ давал 5 иконок по 16px + поле 4px, а содержимое
    ячейки — ~30px (380px) / ~22px (320px). Замер в Chrome: выход до 71.5px за
    границу ячейки и 13 налезаний на соседние дни.
    """
    start = JS.index("const dots = shown.map")
    end = JS.index('}).join("");', start)
    body = JS[start:end]
    assert "slice(0, 2)" in body, "иконки платформ в ячейке месяца не ограничены двумя"
    # 8.4.50: строк иконок не больше трёх (иначе строка сетки выше соседних), остальные — «+N»
    assert "groups.slice(0, 3)" in JS, "в ячейке месяца не ограничено число строк иконок"
    # страховка от переполнения: ячейка и контейнер иконок обрезают содержимое
    assert re.search(r"\.cal-cell \{[^}]*overflow: hidden", CSS, re.S), \
        "ячейка месяца не обрезает переполнение"
    assert re.search(r"\.cal-dot \{[^}]*max-width: 100%[^}]*overflow: hidden", CSS, re.S), \
        "контейнер иконок месяца не ограничен шириной ячейки"
    # 8.4.51 (P5): размер значков месяца — из общего токена --ico-mark = 12px
    assert ".cal-cell .pico, .cal-cell .pico svg,\n.cal-row .q-plat .pico, .cal-row .q-plat .pico svg,\n.cal-witem .q-plat .pico, .cal-witem .q-plat .pico svg { width: var(--ico-mark); height: var(--ico-mark); }" in CSS, \
        "иконки в ячейке месяца не сведены к общему размеру --ico-mark (12px)"
    assert re.search(r"--ico-mark: 12px;", CSS), "токен --ico-mark должен быть 12px (клетка 320px: 26px)"
    assert ".cal-cell .pico { margin-right: 0; }" in CSS, \
        "у иконок в ячейке месяца осталось поле 4px (не влезают две)"
    # 8.4.50: иконки месяца больше не уменьшаются до 10px (владелец: «мелко, ~7px»).
    # Вместо этого на самых узких экранах (≤340px) сужаются внутренние поля ячейки:
    # при 320px ячейка ~34px, содержимое 24px (две иконки по 12px) + зазор 1px = 25px влезает.
    assert ".cal-cell .pico, .cal-cell .pico svg { width: 10px; height: 10px; }" not in CSS, \
        "иконки месяца снова уменьшаются до 10px вместо сужения полей ячейки"
    narrow = CSS.index("@media (max-width: 340px)")
    narrow_block = CSS[narrow:narrow + 300]
    assert ".cal-cell { padding-left: 3px; padding-right: 3px; }" in narrow_block, \
        "нет сужения полей ячейки месяца для очень узких экранов (пара значков 28px не влезет)"
    assert ".cal-month { gap: 2px; }" in narrow_block, \
        "нет уплотнения сетки месяца на очень узких экранах"
    # 8.4.51: зазор пары одинаков во всех трёх видах (--ico-mark-gap = 4px), а не «1px в месяце»
    dot = _css_rule(".cal-dot")
    assert "gap: var(--ico-mark-gap)" in dot, \
        "зазор пары значков в месяце не из общего токена --ico-mark-gap"


def test_calendar_filter_bar_not_stretched():
    """S2: полоса фильтров календаря не растягивает сегмент «День | Неделя | Месяц».

    Регрессия: у .cal-bar не было align-items (по умолчанию stretch), а чипы проектов
    переносились в 3 ряда — мобильный медиазапрос .chips (flex-wrap: nowrap) перекрывался
    базовым правилом .chips ниже по файлу. Серая подложка .seg вытягивалась до 120px,
    подписи занимали 31px → 70% подложки было пустым (замер в Chrome при 380px).
    """
    bar = re.search(r"\.cal-bar \{([^}]*)\}", CSS, re.S)
    assert bar, "нет правила .cal-bar"
    body = bar.group(1)
    assert "align-items: center" in body, "полоса календаря растягивает сегмент по высоте"
    assert "gap:" in body, "чипы проектов слипаются с сегментом (нет gap)"
    # окно поиска — ровно мобильный медиазапрос (по балансу скобок): фиксированные 900 символов
    # ломались от любой новой строки комментария внутри блока
    mob_start = CSS.index(".cal-week { grid-template-columns: 1fr")
    mob_at = CSS.rindex("@media", 0, mob_start)          # сам медиазапрос, а не его первое правило
    depth, k = 0, CSS.index("{", mob_at)
    while True:
        if CSS[k] == "{":
            depth += 1
        elif CSS[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    cal_mob = CSS[mob_start:k]
    assert re.search(r"\.cal-bar \.chips \{[^}]*flex-wrap: nowrap", cal_mob, re.S), \
        "чипы проектов в полосе календаря переносятся «этажами» вместо одной строки"



# ===== 8.4.48: календарь — единый стиль, крупные стрелки ‹ › во всех видах, тап-цели =====
# Репро (Chrome, 320–430px, до правки): стрелки ‹ › в виде «День» — 29.8×36px, «Сегодня» — 79×36px,
# сегмент — 57×32px, чипы — 36px; в неделе/месяце стрелок нет вообще; заголовок «День»
# дублировал выбранный пункт сегмента; правые края пар плашек статусов «плясали»
# (171.7 / 186 / 264.3 при 320px); сетка недели/месяца начиналась с 12px, а строки — с 16px.

CAL_SRC = JS[JS.index("function calRow(g) {"):JS.index("async function bulkDelete")]


def _css_rule(selector: str) -> str:
    """Тело CSS-правила по точному селектору ('' если правила нет)."""
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS, re.S)
    return m.group(1) if m else ""


def test_calendar_arrows_are_uniform_44px_and_in_all_views():
    """Стрелки ‹ ›: один строитель на три вида, тап-цель 44×44, у краёв строки, дата по центру.

    Регресс: в «Неделе» и «Месяце» стрелок не было, а в «Дне» они были 29.8×36px.
    """
    assert "calNav" in CAL_SRC, "нет единого строителя строки навигации календаря"
    assert CAL_SRC.count("${calNav(") == 3, "стрелки не во всех трёх видах (день/неделя/месяц)"
    builder = CAL_SRC[CAL_SRC.index("calNav"):CAL_SRC.index("calNav") + 700]
    assert builder.count('data-act="cal-shift"') == 2, "в строке навигации не две стрелки"
    assert 'data-n="-1"' in builder and 'data-n="1"' in builder, "нет шагов ‹ и ›"
    assert "cal-period" in builder, "в строке навигации нет подписи периода"
    assert "aria-label" in builder, "у стрелок нет подписи для скринридера"
    # 8.4.51 (P5): стрелка — член семейства контролов: нажатие --ctl-h (= --btn-h = 44px),
    # видимая поверхность 36px накладкой ::before с инсетом --ctl-pad (44 − 2×4 = 36)
    step = _css_rule(".cal-step")
    assert step, "нет правила .cal-step"
    assert "var(--ctl-h)" in step, "стрелки не привязаны к токену нажатия семейства (--ctl-h = 44px)"
    assert re.search(r"min-width:\s*var\(--ctl-h\)", step), "ширина стрелки меньше 44px"
    before = _css_rule(".cal-step::before")
    assert "inset: var(--ctl-pad)" in before, "видимая поверхность стрелки не 36px внутри 44px нажатия"
    nav = _css_rule(".cal-nav")
    assert re.search(r"grid-template-columns:[^;]*var\(--btn-h\)[^;]*minmax\(0,\s*1fr\)[^;]*var\(--btn-h\)", nav), \
        "дата не по центру строки (нет сетки 44px / 1fr / 44px)"
    assert "text-align: center" in _css_rule(".cal-period"), "подпись периода не отцентрована"


def test_calendar_today_available_in_all_views():
    """«Сегодня» — одна кнопка на все виды, в верхней полосе (в «Дне» её не было)."""
    assert CAL_SRC.count('data-act="cal-today"') == 1, "кнопка «Сегодня» продублирована/отсутствует"
    assert "cal-today" in CAL_SRC[:CAL_SRC.index("if (!days.length)")], \
        "«Сегодня» не отрисовывается всегда — при пустом календаре навигации нет"


def test_calendar_no_duplicate_view_title():
    """Внутри карточки нет заголовка, дублирующего выбранный пункт «День|Неделя|Месяц»."""
    assert not re.search(r'<h3>\$\{t\("cal_(day|week|month)"\)\}', CAL_SRC), \
        "заголовок карточки дублирует сегмент переключателя"
    assert 'class="cal-period"' in CAL_SRC, "нет подписи периода вместо дублирующего заголовка"


def test_calendar_dense_controls_have_44px_tap_area():
    """Тап-цели: визуально плотные чипы/сегмент/«Сегодня» получают область нажатия 44px.

    У .chip и .seg button область расширяет невидимая накладка ::after, у .btn так нельзя
    (overflow: hidden ради многоточия режет накладку) — там видимая поверхность 36px
    нарисована накладкой ::before внутри 44px кнопки (8.4.51, P5).
    """
    for selector in (".chip", ".seg button"):
        m = re.search(re.escape(selector) + r"[^{]*::after\s*\{([^}]*)\}", CSS, re.S)
        assert m, f"нет расширения тап-цели для {selector}::after"
        assert "height: var(--ctl-h)" in m.group(1), f"{selector}::after: область нажатия меньше 44px"
    today = _css_rule(".btn.sm")
    # 8.4.51 (P5): та же геометрия семейства, но поверхность 36px — накладкой ::before,
    # а не прозрачными рамками с background-clip: 44 − 2×4 = 36
    assert "height: var(--ctl-h)" in today, "«Сегодня»: область нажатия меньше 44px"
    before = _css_rule(".btn.sm::before")
    assert "inset: var(--ctl-pad) 0" in before, "«Сегодня»: видимая поверхность не 36px (инсет --ctl-pad)"
    assert "background: var(--ctl-fill)" in before, "«Сегодня»: заливка не из общего токена --ctl-fill"
    assert _css_rule(".cal-step"), "нет правила .cal-step"
    # «Сегодня» в полосе всегда одна и та же кнопка на все три вида
    assert CAL_SRC.count('data-act="cal-today"') == 1


def test_calendar_rows_and_badge_columns_aligned():
    """Строки календаря: время — фиксированная колонка, пары плашек статусов — по правому краю."""
    assert "cal-row" in CAL_SRC and "cal-badges" in CAL_SRC, "строка календаря без классов выравнивания"
    assert "justify-content: flex-end" in _css_rule(".cal-row .item__meta.cal-badges"), \
        "пары статусов не прижаты к правому краю — правые края «пляшут»"
    assert re.search(r"min-width:\s*\d+px", _css_rule(".cal-row .cal-time")), \
        "колонка времени не фиксирована — заголовки строк не выровнены"
    for sel in (".cal-week", ".cal-month"):
        body = _css_rule(sel)
        assert re.search(r"padding:[^;]*var\(--sp-4\)", body), \
            f"{sel}: боковой отступ не совпадает с остальными рядами карточки (16px)"


def test_calendar_swipe_is_pan_y_only():
    """Свайп периода: поверхность жеста — pan-y (вертикальная промотка остаётся браузеру)."""
    assert "cal-swipe" in CAL_SRC, "нет поверхности для свайпа"
    swipe = _css_rule(".cal-swipe")
    assert "touch-action: pan-y" in swipe, "свайп перехватывает вертикальную промотку"
    assert "pointerdown" in JS and "pointerup" in JS, "нет обработчиков жеста"
    assert "pointerType" in JS, "жест не отключается для мыши (мешает выделению текста)"


def test_mobile_native_touch_rules():
    """mobile-native: мгновенный тап, без залипающего hover, без «синей вспышки»."""
    assert "touch-action: manipulation" in CSS, "нет touch-action: manipulation (задержка тапа)"
    assert "-webkit-tap-highlight-color: transparent" in CSS, "осталась вспышка тапа"
    # :hover — только там, где устройство умеет hover (иначе на телефоне залипает после тапа)
    stripped = re.sub(r"@media\s*\(hover:\s*hover\)[^{]*\{(?:[^{}]|\{[^{}]*\})*\}", "", CSS)
    bad = [ln.strip() for ln in stripped.splitlines() if ":hover" in ln]
    assert not bad, f":hover вне @media (hover: hover): {bad[:3]}"
