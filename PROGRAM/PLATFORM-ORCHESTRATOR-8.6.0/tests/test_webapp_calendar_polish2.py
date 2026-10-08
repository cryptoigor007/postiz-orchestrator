"""8.4.50: «Календарь», вторая точечная полировка (контраст плашек, иконки, ритм сеток).

Репро (Chrome/CDP, стенд scripts/ci_gui_smoke-подобный, 320–430px, светлая/тёмная схема,
замеры до правки — /tmp/orch-cal2/measure-before.json):
  * плашки статусов: «запланировано» 3.39:1, «в ожидании»/«опубликовано» 2.83:1,
    «ошибка» 2.90:1 (светлая) и 3.96/3.96/4.11 (тёмная) при норме ≥4.5:1 для мелкого текста;
  * иконки платформ: день/неделя 16px цветом var(--text-2)/var(--text), месяц 10–12px —
    один и тот же значок выглядел в трёх видах по-разному;
  * «Неделя»: шаг заголовков дней плясал 32.5/48/80.5/32.5/32.5/17px — пустые «сб 26»/«вс 27»
    слипались (зазор 4px против 19.5px у дней с постами);
  * «Месяц»: строка 21–27 была 67px против 58px у остальных (шаг сетки 61/61/61/70);
  * строка чипов: 6px между чипами против 8px до «Сегодня», у неактивных чипов — обводка,
    у активного — заливка (два разных «выделенных» вида);
  * шевроны ‹ › — текстовый глиф ~8×14px при кнопке 44×44.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_RAW = (ROOT / "webapp" / "styles.css").read_text(encoding="utf-8")
JS = (ROOT / "webapp" / "app.js").read_text(encoding="utf-8")
CSS = re.sub(r"\s+", " ", re.sub(r"/\*.*?\*/", " ", CSS_RAW, flags=re.S))  # без комментариев — проще разбирать правила
CAL_SRC = JS[JS.index("function calRow(g) {"):JS.index("async function bulkDelete")]


def _rules(css: str) -> dict:
    """Карта «селектор → тело правила» (первое правило побеждает, @media разворачиваются)."""
    return {sel: bodies[0] for sel, bodies in _all_rules(css).items()}


def _all_rules(css: str) -> dict:
    """Карта «селектор → список тел всех правил с этим селектором»."""
    out: dict = {}
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        prelude = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        body = css[j + 1:k - 1]
        if prelude.startswith("@"):
            for sel, bodies in _all_rules(body).items():
                out.setdefault(sel, []).extend(bodies)
        else:
            for sel in prelude.split(","):
                out.setdefault(sel.strip(), []).append(body)
        i = k
    return out


ALL_RULES = _all_rules(CSS)


RULES = _rules(CSS)


def _rule(selector: str) -> str:
    """Тело первого CSS-правила по точному селектору ('' если правила нет)."""
    return RULES.get(selector, "")


def _rgba(text: str) -> tuple[float, float, float, float]:
    nums = [float(x) for x in re.findall(r"-?\d*\.?\d+", text)[:4]]
    while len(nums) < 4:
        nums.append(1.0)
    return nums[0], nums[1], nums[2], nums[3]


def _hex(text: str) -> tuple[float, float, float]:
    h = text.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mix(fg, bg):
    a = fg[3]
    return (fg[0] * a + bg[0] * (1 - a), fg[1] * a + bg[1] * (1 - a), fg[2] * a + bg[2] * (1 - a))


def _lum(c) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def _ratio(a, b) -> float:
    x, y = _lum(a), _lum(b)
    hi, lo = (x, y) if x > y else (y, x)
    return (hi + 0.05) / (lo + 0.05)


def _scheme_css(dark: bool) -> str:
    if not dark:
        return _rule(":root")
    block = CSS[CSS.index("@media (prefers-color-scheme: dark)"):]
    return _rules(block).get(":root", "")


def test_status_badges_contrast_at_least_4_5_both_schemes():
    """Контраст текста плашек статусов ≥4.5:1 (WCAG AA для мелкого текста 11.5px) в обеих схемах.

    Смысловые цвета (зелёный/красный/синий/оранжевый) сохраняются, меняется только светлота
    оттенка под схему: --badge-*-fg. Раньше текст был #23a455 / var(--red) / var(--accent)
    на тонированном фоне — 2.83–4.11:1.
    """
    kinds = ("ok", "info", "warn", "err")
    for dark in (False, True):
        scheme = _scheme_css(dark)
        card_txt = re.search(r"--card: var\(--tg-card, (#[0-9a-fA-F]{3,6})\)", scheme)
        assert card_txt, "не найден цвет карточки (--card) в схеме"
        card = _hex(card_txt.group(1))
        for kind in kinds:
            fg_txt = re.search(rf"--badge-{kind}-fg: (#[0-9a-fA-F]{{3,6}})", scheme)
            assert fg_txt, f"нет токена --badge-{kind}-fg для {'тёмной' if dark else 'светлой'} схемы"
            badge = _rule(f".badge.{kind}")
            assert badge, f"нет правила .badge.{kind}"
            bg_txt = re.search(r"background: (rgba?\([^)]*\))", badge)
            assert bg_txt, f".badge.{kind}: фон не задан"
            eff = _mix(_rgba(bg_txt.group(1)), card)
            ratio = _ratio(_hex(fg_txt.group(1)), eff)
            assert ratio >= 4.5, (
                f"{'тёмная' if dark else 'светлая'} схема, .badge.{kind}: контраст {ratio:.2f}:1 < 4.5:1")
            assert f"color: var(--badge-{kind}-fg)" in badge, \
                f".badge.{kind} не использует доступный токен --badge-{kind}-fg"
            pill = _rule(f".pill.{kind}")
            assert pill, f"нет правила .pill.{kind}"
            assert f"color: var(--badge-{kind}-fg)" in pill, \
                f".pill.{kind} не использует доступный токен --badge-{kind}-fg (стиль плашек разъехался)"


def test_calendar_platform_icons_uniform_size_and_color():
    """Иконка платформы — один размер (--ico-mark = 12px) и один зазор пары во всех трёх видах.

    8.4.51 (P5): было 16px в очереди, 14px в «Дне»/«Неделе», 12px в «Месяце» и зазор пары
    8px / 0px / 2px. Общий токен --ico-mark = 12px задаёт клетка месяца при 320px
    (34.28px − поля 2×4px = 26px; 12+12+4 = 28 > 26, поэтому на ≤340px поля клетки 3px и
    шаг сетки 2px дают 29.14px). Зазор — общий токен --ico-mark-gap = 4px.
    """
    for sel in (".cal-row .q-plat .pico", ".cal-row .q-plat .pico svg",
                ".cal-witem .q-plat .pico", ".cal-witem .q-plat .pico svg"):
        size = _rule(sel)
        assert size, f"нет правила размера иконок платформ: {sel}"
        assert "width: var(--ico-mark)" in size and "height: var(--ico-mark)" in size, \
            f"{sel}: иконки платформ не сведены к общему размеру --ico-mark"
    assert re.search(r"--ico-mark: 12px;", CSS_RAW), "токен --ico-mark должен быть 12px"
    assert "column-gap: var(--ico-mark-gap)" in _rule(".cal-row .item__meta:not(.cal-badges)"), \
        "зазор пары значков в «Дне» не из общего токена --ico-mark-gap"
    assert "gap: var(--ico-mark-gap)" in " ".join(ALL_RULES.get(".cal-witem .q-plat", [])), \
        "зазор пары значков в «Неделе» не из общего токена --ico-mark-gap"
    for sel in (".cal-row .q-plat", ".cal-witem .q-plat", ".cal-cell .pico"):
        color = " ".join(ALL_RULES.get(sel, []))
        assert color, f"нет правила единого цвета иконок платформ: {sel}"
        assert "color: var(--text-2)" in color, f"{sel}: иконки платформ разного цвета в трёх видах"
    month = _rule(".cal-cell .pico")
    assert "width: var(--ico-mark)" in month, "иконки в ячейке месяца не приведены к --ico-mark (12px)"
    assert ".cal-cell .pico, .cal-cell .pico svg { width: 10px; height: 10px; }" not in CSS_RAW, \
        "иконки месяца всё ещё уменьшаются до 10px (вместо сужения полей ячейки)"
    narrow = re.search(r"@media \(max-width: 340px\) \{(.{0,260})", CSS, re.S)
    assert narrow, "нет media-запроса для очень узких экранов (≤340px)"
    assert ".cal-month { gap: 2px; }" in narrow.group(1), \
        "нет уплотнения сетки месяца на самых узких экранах"
    assert ".cal-cell { padding-left: 3px; padding-right: 3px; }" in narrow.group(1), \
        "на узких экранах не сужены поля ячейки месяца (пара значков 28px не влезет)"


def test_calendar_week_rows_have_even_rhythm():
    """Ритм «Недели»: день без постов — тоже строка 44px (иначе дни слипались).

    Замер до правки: шаг заголовков 32.5/48/80.5/32.5/32.5/17px, зазор «сб 26»→«вс 27» = 4px
    (у дней с постами 19.5px), т.к. пустая колонка была высотой 13px.
    """
    assert re.search(r"\.cal-wcol \{[^}]*min-height: var\(--btn-h\)", CSS), \
        "колонка дня в «Неделе» не имеет минимальной высоты 44px — ритм строк неровный"


def test_calendar_month_rows_are_uniform():
    """«Месяц»: строки сетки одной высоты (было 58px и 67px, шаг 61/61/61/70)."""
    month = _rule(".cal-month")
    assert "grid-auto-rows: 1fr" in month, \
        "строки сетки месяца не выровнены по высоте (нет grid-auto-rows: 1fr)"
    assert "grid-template-rows: auto" in month, \
        "строка подписей дней недели не выведена из выравнивания (grid-template-rows: auto)"


def test_calendar_chip_row_even_gaps_and_single_active_look():
    """Строка чипов: одинаковые промежутки (8px, как до «Сегодня») и один вид выделения.

    Было: 6px между чипами против 8px до «Сегодня»; у неактивного чипа обводка (--border-strong),
    у активного — заливка. Теперь неактивный чип — мягкая нейтральная заливка (как .seg/.btn.secondary),
    выделение ровно одно: акцентная заливка.
    """
    chips = _rule(".cal-bar .chips")
    assert chips, "нет правила .cal-bar .chips"
    # 8.4.51 (P5): один зазор строки контролов — --ctl-gap (8px), он же у .cal-bar до «Сегодня»
    assert "gap: var(--ctl-gap)" in chips, \
        "промежутки между чипами не совпадают с отступом до «Сегодня» (--ctl-gap = 8px)"
    assert "gap: var(--ctl-gap)" in _rule(".cal-bar"), "зазор «чипы ↔ Сегодня» не из общего токена"
    base = re.search(r"\.chip \{ display: inline-flex[^}]*\}", CSS)
    assert base, "нет базового правила чипа"
    body = base.group(0)
    assert "border: 1px solid transparent" in body, \
        "у неактивного чипа осталась обводка — два разных «выделенных» вида"
    assert "background: var(--ctl-fill)" in body, \
        "неактивный чип не в стиле остальных мягких плашек (.seg/ .btn.secondary)"
    on = _rule(".chip.on")
    assert "background: var(--ctl-on-fill)" in on, \
        "активный чип не выделен общей акцентной заливкой (--ctl-on-fill)"
    assert "color: var(--ctl-on-fg)" in on, "текст активного чипа не из токена --ctl-on-fg"


def test_calendar_chevrons_are_large_and_thick():
    """Шевроны ‹ ›: крупная SVG-галка (26px, штрих ≥2.6) вместо текстового глифа 8×14px."""
    assert "chevL" in JS and "chevR" in JS, "нет SVG-шевронов для стрелок календаря"
    builder = CAL_SRC[CAL_SRC.index("const calNav"):CAL_SRC.index("const bar")]
    # 8.4.51 (P5): шеврон 22px — та же доля видимой поверхности (22/36 = 0.61, что 26/44)
    assert 'icon("chevL", 22)' in builder and 'icon("chevR", 22)' in builder, \
        "стрелки календаря не используют SVG-шеврон под поверхность 36px (22px)"
    assert "aria-label" in builder, "у стрелок пропала подпись для скринридера"
    chev = re.search(r"chevL: '([^']*)'", JS)
    assert chev, "нет разметки SVG-шеврона"
    width = re.search(r"stroke-width=\"([\d.]+)\"", chev.group(1))
    assert width and float(width.group(1)) >= 2.6, "штрих шеврона тонкий (<2.6)"
    ico = _rule(".btn.cal-step .pico")
    assert "margin-right: 0" in ico, "шеврон смещён полем .pico (не по центру кнопки)"
    assert "opacity: 1" in ico, "шеврон остаётся полупрозрачным (выглядит бледно)"
    # размер задаём явно: общие правила .pico/.pico svg (16px) идут ниже и перебивают .pico-22
    assert "width: 22px" in ico and "height: 22px" in ico, \
        "размер шеврона не задан явно — общий .pico (16px) его перебивает"
    svg = _rule(".btn.cal-step .pico svg")
    assert "width: 22px" in svg and "height: 22px" in svg, "SVG шеврона не 22px"
    assert "fill: none" in svg, "шеврон заливается currentColor (правило .pico svg) — форма ломается"
    step = _rule(".btn.cal-step")
    assert "var(--ctl-h)" in step and re.search(r"min-width: var\(--ctl-h\)", step), \
        "кнопка стрелки перестала быть 44×44 (--ctl-h)"
    assert "inset: var(--ctl-pad)" in _rule(".btn.cal-step::before"), \
        "видимая поверхность стрелки не 36px внутри 44px нажатия"


def test_calendar_segmented_control_equal_width_and_visible_track():
    """Сегмент «День|Неделя|Месяц»: одинаковая ширина вкладок и видимый серый трек.

    Было: белая «таблетка» скакала 57/72.8/66.6px, трек по краям — 2px.
    """
    seg = _rule(".cal-bar .seg")
    assert seg, "нет правила .cal-bar .seg"
    assert "grid-auto-flow: column" in seg and "grid-auto-columns: minmax(0, 1fr)" in seg, \
        "вкладки сегмента разной ширины (таблетка «скачет»)"
    base = _rule(".seg")
    # 8.4.51 (P5): трек = 36px-вкладка + 2×4px инсета = 44px (--ctl-pad = --sp-1 = 4px)
    assert "padding: var(--ctl-pad)" in base, "серый трек по краям почти срезан (нужно 4px, --ctl-pad)"
    btn = _rule(".seg button")
    assert "height: var(--ctl-hv)" in btn, \
        "высота вкладки не скомпенсирована под трек 4px (нужно 36px = --ctl-hv)"
    assert "border-radius: var(--ctl-r)" in btn, "скругление вкладки не из токена семейства --ctl-r"
    on = _rule(".seg button.on")
    assert "background: var(--ctl-on-fill)" in on and "color: var(--ctl-on-fg)" in on, \
        "«выбрано» в сегменте не акцентной заливкой семейства (осталась белая таблетка)"
    # тап-цель остаётся 44px (невидимая накладка)
    after = re.search(r"\.seg button::after \{([^}]*)\}", CSS)
    assert after and "height: var(--ctl-h)" in after.group(1), \
        "тап-цель вкладки сегмента меньше 44px"
