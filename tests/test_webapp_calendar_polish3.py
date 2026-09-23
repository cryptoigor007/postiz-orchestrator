"""8.4.51: единое семейство контролов панели + остаток приёмки по календарю.

Репро (Chrome/CDP, стенд /tmp/orch-cal3/stand.py, 320/360/390/430px, светлая и тёмная схема,
замеры до правки — /tmp/orch-cal3/data-before.json). Владелец (msg 283):
«Почему у тебя в календаре разного типа кнопки… сделай всё в одном стиле». Замеры «до»:

  * на одном экране «Календарь» три семейства контролов: стрелки ‹ › — 44×44, r=12,
    заливка rgba(120,120,128,.14); «Сегодня» — 44 (видно 36 из-за прозрачных рамок), r=14;
    чипы проектов — 36, r=999 (pill), шрифт 12px; переключатель вида — трек 36/r=10,
    вкладка 28/r=8, «выбрано» = белая таблетка + тень (у чипов «выбрано» = синяя заливка);
  * белый текст на синем чипе: 4.02:1 (светлая) и 3.65:1 (тёмная) при норме ≥4.5:1;
  * «обновить» (icon-ghost): 3.6:1 акцентом по светлому фону, подпись tabbar — 3.6:1;
  * .btn.danger 2.94:1, .btn.success 1.95:1, .btn.danger-text 3.01:1, .btn.success-text 2.73:1;
  * значок платформы: очередь 16px, день/неделя календаря 14px, месяц 12px (правило
    .q-row .q-plat .pico { width: 14px } мертво — в разметке нет .q-row);
  * зазор пары «видео + отправить»: день 8px (column-gap .item__meta), неделя 0px, месяц 2px;
  * строка чипов у правого края обрезана (321px контента в 171px окна при 320px) без всякой
    подсказки, что список листается; промежутки чипов 6px (очередь) / 8px (календарь);
  * плашки статусов: .badge 24px/11.5px/r=999 против .pill 19px/11px/r=999 — один смысл,
    два размера.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CSS_RAW = (ROOT / "webapp" / "styles.css").read_text(encoding="utf-8")
JS = (ROOT / "webapp" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "webapp" / "index.html").read_text(encoding="utf-8")
CSS = re.sub(r"\s+", " ", re.sub(r"/\*.*?\*/", " ", CSS_RAW, flags=re.S))


def _all_rules(css: str, media: str | None = None) -> dict:
    """{селектор: [(тело, условие @media или None), ...]} в порядке файла."""
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
            inner = prelude if media is None else media + " " + prelude
            for sel, items in _all_rules(body, inner).items():
                out.setdefault(sel, []).extend(items)
        else:
            for sel in prelude.split(","):
                out.setdefault(sel.strip(), []).append((body, media))
        i = k
    return out


ALL_RULES = _all_rules(CSS)


def _rule(selector: str) -> str:
    """Первое безусловное правило (для одинаковой специфичности выигрывает последнее — см. _last)."""
    items = ALL_RULES.get(selector, [])
    for body, media in items:
        if media is None:
            return body
    return items[0][0] if items else ""


def _last(selector: str) -> str:
    """Последнее безусловное правило: при равной специфичности оно и побеждает в CSS."""
    bodies = [body for body, media in ALL_RULES.get(selector, []) if media is None]
    return bodies[-1] if bodies else _rule(selector)


def _in_media(selector: str, needle: str) -> str:
    return " ".join(body for body, media in ALL_RULES.get(selector, [])
                    if media and needle in media)


def _joined(selector: str) -> str:
    """Все тела правила подряд — когда важна любая из перегрузок (в т.ч. в @media)."""
    return " ".join(body for body, _ in ALL_RULES.get(selector, []))


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
    """Эффективные токены: базовый :root + (для тёмной) переопределения из её :root.

    В тёмной схеме переопределена лишь часть токенов — остальные наследуются, поэтому
    конкатенация; значения берём последним объявлением (как в CSS)."""
    light = _rule(":root")
    if not dark:
        return light
    block = CSS[CSS.index("@media (prefers-color-scheme: dark)"):]
    dark_root = ""
    for body, media in _all_rules(block, "@media (prefers-color-scheme: dark)").get(":root", []):
        if media:
            dark_root = body
    assert dark_root, "не нашёл тёмную схему"
    return light + " " + dark_root


def _token(scheme: str, name: str) -> str:
    found = re.findall(rf"--{re.escape(name)}: ([^;]+);", scheme)
    assert found, f"нет токена --{name} в схеме"
    return found[-1].strip()


def _card(scheme: str) -> tuple[float, float, float]:
    m = re.findall(r"--card: var\(--tg-card, (#[0-9a-fA-F]{3,6})\)", scheme)
    assert m, "нет цвета карточки (--card)"
    return _hex(m[-1])


def _accent_fill(scheme: str) -> tuple[float, float, float]:
    """--accent-fill: color-mix(in srgb, var(--accent) N%, #000) → цвет заливки акцентом."""
    m = re.findall(r"--accent: var\(--tg-accent, (#[0-9a-fA-F]{3,6})\)", scheme)
    assert m, "нет цвета акцента (--accent)"
    a = _hex(m[-1])
    mix = re.search(r"color-mix\(in srgb, var\(--accent\) (\d+)%, #000\)", _token(scheme, "accent-fill"))
    assert mix, "--accent-fill должен быть затемнением акцента: color-mix(in srgb, var(--accent) N%, #000)"
    p = int(mix.group(1)) / 100
    return (a[0] * p, a[1] * p, a[2] * p)


# --------------------------------------------------------------------------
# 1. Единый набор токенов контрола
# --------------------------------------------------------------------------
def test_control_tokens_single_family():
    """Один набор токенов контрола: высота нажатия, видимая высота, скругление, заливка, шрифт, зазор."""
    for dark in (False, True):
        scheme = _scheme_css(dark)
        for name in ("ctl-h", "ctl-hv", "ctl-pad", "ctl-r", "ctl-fill", "ctl-font",
                     "ctl-pad-x", "ctl-gap", "ctl-on-fill", "ctl-on-fg", "ico-mark", "ico-mark-gap"):
            _token(scheme, name)
        assert _token(scheme, "ctl-h") == "var(--btn-h)", \
            "--ctl-h (нажатие) должен быть 44px = var(--btn-h) — тап-цель из mobile-native"
        assert _token(scheme, "ctl-hv") == "var(--btn-h-sm)", \
            "--ctl-hv (видимая поверхность) должен быть 36px = var(--btn-h-sm)"
        assert _token(scheme, "ctl-pad") == "4px", \
            "--ctl-pad: 36 + 2×4 = 44 — арифметика, на которой держится единая высота"
        assert _token(scheme, "ctl-on-fill") == "var(--accent-fill)", \
            "«выбрано» должно краситься одной акцентной заливкой --accent-fill"


def test_calendar_controls_are_one_family():
    """Стрелки, «Сегодня», чипы и вкладки переключателя — одно семейство.

    Нажатие 44 / видимая поверхность 36 / r=12 / одна заливка / один шрифт.
    У стрелок и «Сегодня» (это .btn с overflow: hidden) серая поверхность 36px нарисована
    накладкой ::before с инсетом --ctl-pad внутри 44px кнопки: 44 − 2×4 = 36. У чипов и
    вкладок сегмента поверхность 36px — сам элемент, а 44px нажатия добирается накладкой."""
    # арифметика, на которой держится «одна высота»
    light = _scheme_css(False)
    assert _token(light, "btn-h") == "44px" and _token(light, "ctl-h") == "var(--btn-h)"
    assert _token(light, "btn-h-sm") == "36px" and _token(light, "ctl-hv") == "var(--btn-h-sm)"
    assert _token(light, "ctl-pad") == "4px", "--ctl-pad: 36 + 2×4 = 44"
    # тела правил у одного селектора могут быть разнесены (базовый блок + блок тап-целей)
    for sel in (".btn.cal-step", ".btn.sm", ".chip", ".seg button"):
        body = _joined(sel)
        assert body, f"нет правила {sel}"
        assert "border-radius: var(--ctl-r)" in body, f"{sel}: скругление не из общего токена --ctl-r"
    for sel in (".btn.cal-step", ".btn.sm"):
        assert "height: var(--ctl-h)" in _joined(sel), f"{sel}: нажатие не 44px (--ctl-h)"
        assert "inset: var(--ctl-pad)" in _joined(sel + "::before"), \
            f"{sel}: видимая поверхность не вписана инсетом --ctl-pad (44 − 2×4 = 36)"
    for sel in (".chip", ".seg button"):
        assert "height: var(--ctl-hv)" in _joined(sel), f"{sel}: видимая высота не --ctl-hv (36px)"
        assert "height: var(--ctl-h)" in _joined(sel + "::after"), \
            f"{sel}: область нажатия не добита до 44px (--ctl-h)"
    for sel in (".btn.cal-step::before", ".btn.sm::before", ".chip", ".seg"):
        assert "background: var(--ctl-fill)" in _joined(sel), f"{sel}: обычная заливка не --ctl-fill"
    assert "padding: var(--ctl-pad)" in _joined(".seg"), ".seg: трек не собран инсетом --ctl-pad (36+2×4=44)"
    assert "border-radius: var(--ctl-r)" in _joined(".seg"), ".seg: скругление трека не --ctl-r"
    for sel in (".chip", ".seg button", ".btn.sm"):
        assert "font-size: var(--ctl-font)" in _joined(sel), f"{sel}: шрифт не из общего токена --ctl-font"


def test_selected_state_is_the_only_difference():
    """Отличается только «выбрано» — акцентная заливка; второй способ выделения (белая таблетка) убран."""
    for sel in (".seg button.on", ".chip.on"):
        body = _rule(sel)
        assert body, f"нет правила {sel}"
        assert "background: var(--ctl-on-fill)" in body, f"{sel}: «выбрано» не акцентной заливкой --ctl-on-fill"
        assert "color: var(--ctl-on-fg)" in body, f"{sel}: текст «выбрано» не --ctl-on-fg"
    seg_on = _rule(".seg button.on")
    assert "var(--card)" not in seg_on and "box-shadow" not in seg_on, \
        ".seg button.on: остался второй тип выделения (белая таблетка с тенью)"


# --------------------------------------------------------------------------
# 2. Контраст: белый текст на акценте ≥4.5:1 в обеих схемах
# --------------------------------------------------------------------------
def test_white_on_accent_at_least_4_5_both_schemes():
    """Белый текст на акцентной заливке ≥4.5:1 (WCAG AA, мелкий текст 12–15px).

    Было: #007aff → 4.02:1 (светлая), #0a84ff → 3.65:1 (тёмная). Оттенок тот же, светлее/темнее
    только заливка — смысловой цвет остальных элементов (ссылки, подписи) не меняется.
    """
    for dark in (False, True):
        scheme = _scheme_css(dark)
        fill = _accent_fill(scheme)
        on_fg = _token(scheme, "accent-text")
        assert "#fff" in on_fg.lower() or "#ffffff" in on_fg.lower(), "текст на акценте должен быть белым"
        ratio = _ratio((255, 255, 255), fill)
        assert ratio >= 4.5, (
            f"{'тёмная' if dark else 'светлая'} схема: белый текст на акцентной заливке {ratio:.2f}:1 < 4.5:1")
    # все носители белого текста на акценте берут заливку из токена
    for sel in (".btn.primary", ".chip.on", ".seg button.on"):
        assert "var(--ctl-on-fill)" in _rule(sel) or "var(--accent-fill)" in _rule(sel), \
            f"{sel}: заливка не из общего акцентного токена"
    # счётчик на активном чипе больше не полупрозрачный белый (0.85 → 4.0:1)
    cnt = _rule(".chip.on .cnt")
    assert cnt and "var(--ctl-on-fg)" in cnt, \
        ".chip.on .cnt: полупрозрачный белый на акценте давал 4.0:1 — нужен плотный --ctl-on-fg"
    for sel in (".chip:has(.chip__input:checked) .cnt", ".chip:has(.chip__input:checked) .pico"):
        assert "var(--ctl-on-fg)" in _rule(sel), f"{sel}: текст/значок выбранного чипа не --ctl-on-fg"


def test_danger_success_buttons_contrast_both_schemes():
    """Зелёные/красные кнопки панели ≥4.5:1 в обеих схемах (было 1.95–3.01:1)."""
    pairs = ((".btn.danger", "err", r"background: (rgba?\([^)]*\)|var\(--ctl-fill\))"),
             (".btn.success", "ok", r"background: (rgba?\([^)]*\)|var\(--ctl-fill\))"),
             (".btn.danger-text", "err", r"background: (rgba?\([^)]*\)|var\(--ctl-fill\))"),
             (".btn.success-text", "ok", r"background: (rgba?\([^)]*\)|var\(--ctl-fill\))"))
    for dark in (False, True):
        scheme = _scheme_css(dark)
        card = _card(scheme)
        for sel, kind, bg_re in pairs:
            body = _rule(sel)
            assert body, f"нет правила {sel}"
            assert f"color: var(--badge-{kind}-fg)" in body, (
                f"{sel}: текст не из проверенного токена --badge-{kind}-fg (контраст плашек уже посчитан)")
            m = re.search(bg_re, body)
            assert m, f"{sel}: фон не задан"
            fg = _hex(_token(scheme, f"badge-{kind}-fg"))
            if m.group(1).startswith("var(--ctl-fill"):
                bg = _mix(_rgba("120,120,128,0.14"), card)
            else:
                bg = _mix(_rgba(m.group(1)), card)
            ratio = _ratio(fg, bg)
            assert ratio >= 4.5, (
                f"{'тёмная' if dark else 'светлая'} схема, {sel}: контраст {ratio:.2f}:1 < 4.5:1")


def _accent_text(scheme: str) -> tuple[float, float, float]:
    """--accent-on-bg как цвет RGB: либо готовый токен, либо затемнение акцента."""
    tok = _token(scheme, "accent-on-bg")
    if tok.startswith("var("):
        name = re.search(r"var\(--([a-z0-9-]+)\)", tok).group(1)
        return _hex(
            re.search(rf"--{name}: var\(--tg-[a-z-]+, (#[0-9a-fA-F]{{3,6}})\)", scheme).group(1)
        )
    m = re.search(r"color-mix\(in srgb, var\(--accent\) (\d+)%, #000\)", tok)
    a = _hex(re.findall(r"--accent: var\(--tg-accent, (#[0-9a-fA-F]{3,6})\)", scheme)[-1])
    p = int(m.group(1)) / 100
    return (a[0] * p, a[1] * p, a[2] * p)


def test_accent_as_text_contrast_both_schemes():
    """Акцент как текст/значок на нейтральном фоне ≥4.5:1 (tabbar 10.5px, значок «обновить», «сегодня» в шапке колонки)."""
    for dark in (False, True):
        scheme = _scheme_css(dark)
        fg = _accent_text(scheme)
        bg = _card(scheme)
        ratio = _ratio(fg, bg)
        assert ratio >= 4.5, (
            f"{'тёмная' if dark else 'светлая'} схема: акцент как текст {ratio:.2f}:1 < 4.5:1 (было 3.6:1)"
        )
        assert "var(--accent-on-bg)" in _rule(".tabbar button.active"), (
            ".tabbar button.active: цвет не из токена --accent-on-bg (3.6:1 для подписи 10.5px)"
        )


# --------------------------------------------------------------------------
# 3. Значки платформ: один размер и один зазор пары во всех видах
# --------------------------------------------------------------------------
def test_platform_marker_icon_one_size_panel_wide():
    """Значок-маркер платформы — один размер на всей панели (было 16 в очереди, 14 в календаре, 12 в месяце)."""
    for sel in (".q-plat .pico", ".q-plat .pico svg", ".chip .pico"):
        body = _rule(sel)
        assert body, f"нет правила размера значка платформы: {sel}"
        assert "width: var(--ico-mark)" in body and "height: var(--ico-mark)" in body, \
            f"{sel}: значок-маркер не приведён к общему размеру --ico-mark"
    # ни один контекст не переопределяет размер маркера (плашка статуса, чип, панель, шапка)
    for sel in (".badge .pico", ".badge .q-plat .pico", ".item__meta .q-plat .pico"):
        assert sel not in ALL_RULES, f"{sel}: размер значка-маркера переопределён вне общего правила"
    # крупные (аватар-икона карточки) остаются крупными — это другая роль
    assert "26px" in _rule(".q-plat.big .pico"), "крупный значок карточки (.q-plat.big) должен остаться 26px"
    # мёртвое правило .q-row .q-plat .pico { width: 14px } убрано: в разметке нет .q-row,
    # но правила хватило бы, чтобы значок снова стал 14px (специфичность выше общей)
    assert ".q-row .q-plat .pico" not in ALL_RULES, \
        "мёртвое правило .q-row .q-plat .pico { width: 14px } осталось — ловушка для размера значка"


def test_calendar_icon_pair_same_size_and_gap_all_views():
    """Пара «видео + отправить»: один размер и один зазор в дне, неделе и месяце.

    Замер до правки: день 14px/gap 8, неделя 14px/gap 0, месяц 12px/gap 2.
    Клетка месяца при 320px: ширина 34.28px − поля 2×4px = 26px → 12+12+4 = 28 > 26,
    поэтому на узком экране (≤340px) сетка и поля клетки ужимаются: gap 2px + поля 3px
    → 35.14 − 6 = 29.14px ≥ 28px (запас 1.14px). Размер 12px — единственный, при котором
    пара влезает в клетку; на нём же сходятся и остальные «маркеры» панели (--ico-mark).
    """
    for sel in (".cal-row .q-plat .pico", ".cal-row .q-plat .pico svg",
                ".cal-witem .q-plat .pico", ".cal-witem .q-plat .pico svg",
                ".cal-cell .pico", ".cal-cell .pico svg"):
        body = _rule(sel)
        assert body, f"нет правила размера значков календаря: {sel}"
        assert "width: var(--ico-mark)" in body and "height: var(--ico-mark)" in body, \
            f"{sel}: размер не из общего токена --ico-mark"
    gaps = {
        ".cal-row .item__meta:not(.cal-badges)": "column-gap",
        ".cal-witem .q-plat": "gap",
        ".cal-dot": "gap",
    }
    for sel, prop in gaps.items():
        body = _joined(sel)
        assert body, f"нет правила зазора пары значков: {sel}"
        assert f"{prop}: var(--ico-mark-gap)" in body, \
            f"{sel}: зазор пары не из общего токена --ico-mark-gap"
    # арифметика узкого экрана: 320px → клетка 34.28px; шаг 2px и поля 3px дают 29.14px ≥ 28px
    assert "gap: 2px" in _in_media(".cal-month", "max-width: 340px"), \
        "на 320px сетке месяца нужен gap 2px, иначе пара значков 28px не влезает в клетку"
    pad = _in_media(".cal-cell", "max-width: 340px")
    assert "padding-left: 3px" in pad and "padding-right: 3px" in pad, \
        "на 320px полю клетки месяца нужно 3px: 34.28 − 6 = 28.28px при нужных 28px"
    assert "gap: 1px" not in _in_media(".cal-dot", "max-width: 340px"), \
        "мелкий зазор 1px у значка месяца — разнобой с днём/неделей"


# --------------------------------------------------------------------------
# 4. Строка чипов: один зазор, мягкое затемнение у края
# --------------------------------------------------------------------------
def test_chip_rows_single_gap():
    """Промежутки чипов — один токен (было 6px в очереди и 8px в календаре; замер приёмки — 8 и 10px)."""
    for sel in (".chips", ".cal-bar .chips"):
        body = _rule(sel)
        assert body, f"нет правила {sel}"
        assert "gap: var(--ctl-gap)" in body, f"{sel}: промежуток чипов не из общего токена --ctl-gap"
    for sel in (".cal-bar", ".q-toolbar", ".cover-tabs"):
        body = _joined(sel)
        assert "gap: var(--ctl-gap)" in body, f"{sel}: зазор строки контролов не --ctl-gap"


def test_chips_scroller_has_edge_fade_only_when_overflowing():
    """Обрезка чипов у правого края = подсказка «можно листать» (маска), а не дефект."""
    body = _joined(".chips.more-right")
    assert "mask-image" in body and "linear-gradient" in body, \
        ".chips.more-right: нет мягкого затемнения (mask-image + linear-gradient)"
    assert "-webkit-mask-image" in body, ".chips.more-right: нет -webkit-mask-image (Safari/Telegram iOS)"
    assert "var(--ctl-gap)" not in body
    left = _joined(".chips.more-left")
    assert "mask-image" in left, ".chips.more-left: нет затемнения у левого края (когда список прокручен)"
    assert "syncChipFade" in JS, "нет JS-функции, которая включает маску только при переполнении"
    assert "scrollWidth" in JS and "clientWidth" in JS, \
        "маска должна включаться по факту переполнения (scrollWidth > clientWidth)"
    assert re.search(r'syncChipFade\(', JS.split("function syncChipFade")[1]), "syncChipFade не вызывается"
    assert 'addEventListener("scroll"' in JS or "addEventListener('scroll'" in JS, \
        "маска не пересчитывается при прокрутке чипов"


# --------------------------------------------------------------------------
# 5. Плашки статусов и кнопки-иконки: один размер/скругление
# --------------------------------------------------------------------------
def test_status_plaques_same_size():
    """.badge и .pill — один смысл (плашка статуса) → один размер, шрифт и скругление."""
    badge, pill = _rule(".badge"), _rule(".pill")
    assert badge and pill
    assert "height: 24px" in badge and "font-size: 11.5px" in badge, "эталон плашки изменился"
    assert "height: 24px" in pill, ".pill: высота 19px против 24px у .badge — разнобой"
    assert "font-size: 11.5px" in pill, ".pill: шрифт 11px против 11.5px у .badge — разнобой"
    assert "border-radius: 999px" in pill and "border-radius: 999px" in badge, "скругление плашек разъехалось"


def test_icon_buttons_one_family():
    """.icon-btn и .icon-ghost — одно семейство: 44×44, r=--ctl-r, нажатие --dur-press/--ease-out."""
    for sel in (".icon-btn", ".icon-ghost"):
        body = _last(sel)
        assert body, f"нет правила {sel}"
        assert "border-radius: var(--ctl-r)" in body, f"{sel}: скругление не --ctl-r (было 50% у ghost)"
    assert "scale(0.97)" in _last(".icon-ghost:active"), \
        "у значка-кнопки другая реакция на нажатие (нужно scale(.97))"
    assert "scale(0.97)" in _last(".icon-btn:active"), \
        "у кнопки-иконки другая реакция на нажатие (нужно scale(.97))"
    assert "background: var(--ctl-fill)" in _last(".icon-btn"), \
        ".icon-btn: заливка не из общего токена --ctl-fill (кнопка-иконка выпадает из семейства)"


def test_nav_icon_sizes_consistent():
    """Один и тот же значок навигации в tabbar и в шторке «Ещё» — одного размера (было 23 vs 22px)."""
    tabbar = _joined(".tabbar button .ico") + _joined(".tabbar button .ico svg")
    sheet = _joined(".sheet-item .ico") + _joined(".sheet-item .ico svg")
    assert tabbar and sheet
    assert "var(--ico-nav)" in tabbar and "var(--ico-nav)" in sheet, \
        "размер значка навигации не из общего токена --ico-nav (было 23px в tabbar против 22px в шторке)"


def test_sheet_nav_icon_actually_matches_tabbar():
    """Значки шторки «Ещё» реально 22px, а не 16px: icon(x, 22) даёт .pico.pico-22,

    который перебивается поздним базовым .pico { width: 16px } (одинаковая специфичность,
    правило ниже по файлу). Замер в Chrome: tabbar 22px, шторка 16px — один смысл, два размера.
    """
    cell = _joined(".sheet-item .pico") + _joined(".sheet-item .pico svg")
    assert "var(--ico-nav)" in cell, \
        "значок шторки «Ещё» остаётся 16px (.pico перебивает .pico-22) — против 22px в tabbar"
    assert "margin-right: 0" in _joined(".sheet-item .pico"), \
        "у значка шторки остался margin-right: 4px — зазор до подписи 16px вместо 12px (gap строки)"


def test_lang_switch_is_in_control_family():
    """Переключатель RU/EN — член семьи: видимая поверхность 36px внутри нажатия 44px, r=12, шрифт 13."""

    body = _rule(".lang-btn")
    assert body, "нет правила .lang-btn"
    assert "min-height: var(--ctl-hv)" in body, "переключатель языка не 36px (видимая поверхность)"
    assert "border-radius: var(--ctl-r)" in body, "радиус переключателя языка не из семьи (было 8px)"
    assert "font-size: var(--ctl-font)" in body, "шрифт переключателя языка не из семьи (было 12px)"
    assert "background: var(--ctl-fill)" in body, "заливка переключателя не из общего токена"
    assert "height: var(--ctl-h)" in _joined(".lang-btn::after"), \
        "у переключателя языка нет тап-цели 44px (было 22px по содержимому)"
    assert "gap: var(--ctl-gap)" in _rule(".lang"), "зазор в ряду переключателей не --ctl-gap (было 6px)"


def test_calendar_day_cells_one_radius():
    """Ячейка дня «Недели» и ячейка «Месяца» — один смысл → одно скругление (было 9 против 10px)."""
    week = _rule(".cal-witem")
    month = _rule(".cal-cell")
    assert week and month
    assert "border-radius: 10px" in week, "ячейка дня «Недели» выпала из скругления ячейки «Месяца»"
    assert "border-radius: 10px" in month, "эталон скругления ячейки месяца изменился"


def test_before_surface_does_not_paint_over_labels():
    """Поверхность контрола нарисована ПОД текстом/значком: ::before с z-index:-1 внутри

    isolation:isolate. Без этого заливка ложилась поверх подписи: замер в Chrome — самый тёмный
    пиксель «Сегодня» (41,41,43) вместо цвета текста (28,28,30), т.е. подпись была под 14% серого.
    """
    for host, pseudo in ((".btn.cal-step", ".btn.cal-step::before"),
                         (".btn.sm", ".btn.sm::before")):
        assert "isolation: isolate" in _last(host), \
            f"{host}: нет своего контекста наложения — поверхность уедет под фон родителя"
        assert "z-index: -1" in _last(pseudo), \
            f"{pseudo}: поверхность рисуется поверх подписи (текст темнеет на 14% серого)"
    assert "position: relative" in _last(".btn.cal-step .pico"), \
        "шеврон не поднят над поверхностью ::before"


def test_checkbox_tap_target_is_44px():
    """Кружок выбора в строке очереди/корзины: 26px видимых, 43×44 нажатия (было 26×26)."""
    assert "position: relative" in _rule(".q-check"), "у кружка нет позиции для накладки нажатия"
    after = _joined(".q-check::after")
    assert "height: var(--ctl-h)" in after, "тап-цель кружка выбора меньше 44px"
    assert "left: -9px" in after and "right: -8px" in after, \
        "накладка кружка должна расширяться влево/вправо до края обложки, но не перекрывать её"


def test_no_dead_platform_icon_size_rule():
    """Мёртвое правило .panel-header .q-plat .pico (22px) убрано: в разметке нет такого сочетания,

    иначе это третий размер одного значка платформы (12 — маркер, 26 — «аватар», 22 — призрак).
    """
    assert not _all_rules(CSS).get(".panel-header .q-plat .pico"), \
        "мёртвое правило размера значка в .panel-header осталось"
    pico = _joined(".sheet-item .pico")
    assert pico, "нет правила размера значка шторки"


# --------------------------------------------------------------------------
# 8.4.52 (P6): приёмка №2 — 13 дефектов, найденных по скриншотам after-*.png
# Замеры «до» (Chrome/CDP, /tmp/orch-cal3/review2-320_390-light_dark.json):
#   * подпись «День» в синей таблетке сегмента прижата влево (чернила x 12…29 из 73);
#   * кнопка «Выбрать» в очереди 44px против 36px у чипов и зазор 10px против 8px;
#   * разнобой значков шторки: высоты 16,16,16,16,16,18,18,18,17 / ширины 18,18,16,16,16,20,18,18,14,
#     у «Справки» вместо «?» — сплошное пятно (центр 100% чернил), у «Настроек» — «снежинка» без отверстия;
#   * значок «Календаря» в tabbar 18×18 против 16×16 у соседей, «Ещё» — 16×4;
#   * перенесённый чип дня в «Неделе» вставал под подписью дня (x=31 вместо x=97);
#   * подпись сегодняшнего дня в «Неделе» — чистый акцент #007AFF по белому (4.02:1);
#   * в ячейке месяца три ряда точек упирались в нижнюю кромку (запас 0px);
#   * зазор в ряду плашек статусов 6px против 8px по вертикали;
#   * значки кнопок очереди стояли на 2px левее центра (base .pico { margin-right: 4px });
#   * «Очередь ↻» в шапке: заголовок по центру экрана, но кнопка не прижата к правому краю (разрыв 2px),
#     подпись при этом не могла занять строку целиком;
#   * подпись периода на 320px обрезалась многоточием («21–27 сентября · Се…», нужно 180px, окно 154px).
# --------------------------------------------------------------------------
def test_seg_label_is_centered():
    """Подпись вкладки сегмента — по центру таблетки (было: чернила «День» 12…29 из 73)."""
    body = _rule(".seg button")
    assert body, "нет правила .seg button"
    assert "display: inline-flex" in body, "подпись вкладки не центрируется (нужен inline-flex)"
    assert "align-items: center" in body and "justify-content: center" in body, (
        "вкладка сегмента не центрирует подпись по обеим осям"
    )
    assert "text-align: center" in body, (
        "у вкладки сегмента осталось выравнивание текста по умолчанию"
    )


def test_dense_button_visible_surface_36_inside_44_hit():
    """Плотная кнопка семьи: нажатие 44px, видимая поверхность 36px, r=--ctl-r, шрифт --ctl-font.

    Так «Выбрать» в очереди перестала быть отдельным контролом (было 44 с padding 6px 12px и
    шрифтом 12px против 36px/13px у чипов и «Сегодня»).
    """
    sm = _last(".btn.sm")
    assert "height: var(--ctl-h)" in sm and "min-height: var(--ctl-h)" in sm, (
        "плотная кнопка: область нажатия не 44px"
    )
    assert "margin: calc(-1 * var(--ctl-pad)) 0" in sm, (
        "плотная кнопка не компенсирует отрицательными полями лишнюю высоту нажатия"
    )
    assert "padding: 0 var(--ctl-pad-x)" in sm, "боковые поля плотной кнопки не из семьи"
    assert "background: transparent" in sm and "border: 0" in sm, (
        "поверхность плотной кнопки должна рисоваться накладкой ::before, а не рамками"
    )
    assert "border-radius: var(--ctl-r)" in sm and "font-size: var(--ctl-font)" in sm, (
        "плотная кнопка выпала из семьи (радиус/шрифт)"
    )
    before = _last(".btn.sm::before")
    assert "inset: var(--ctl-pad) 0" in before, "видимая поверхность плотной кнопки не 36px"
    assert "background: var(--ctl-fill)" in before, "заливка плотной кнопки не из общего токена"
    assert not _all_rules(CSS).get(".q-sel-btn"), (
        "у «Выбрать» снова своя геометрия — она должна наследовать .btn.sm"
    )
    m = re.search(r'class="btn \$\{select \? "primary" : "secondary"\} ([^"]*)"', JS)
    assert m and "sm" in m.group(1).split(), (
        "кнопка «Выбрать» в разметке без класса sm — остаётся 44px видимой поверхности"
    )


def test_queue_toolbar_one_gap_and_meta_one_gap():
    """Один зазор в ряду кнопок очереди и один — в мета-строке (было 10px против 8px и 6px против 8px)."""
    assert "gap: var(--ctl-gap)" in _last(".q-toolbar"), (
        "зазор ряда «Выбрать»/чипов не общий --ctl-gap (было 10px против 8px)"
    )
    meta = _last(".item__meta")
    assert "gap: var(--sp-2)" in meta, (
        "зазор мета-строки не общий (было 6px по горизонтали против 8px)"
    )
    assert "6px var(--sp-2)" not in _joined(".item__meta"), "остался прежний двухосный зазор"


def test_week_today_head_is_accent_text_not_accent_fill():
    """Подпись сегодняшнего дня в «Неделе» — акцентный ТЕКСТ (≥4.5:1), а не чистый #007AFF (4.02:1)."""
    body = _last(".cal-wcol.today .cal-whead")
    assert "color: var(--accent-on-bg)" in body, (
        "подпись сегодняшнего дня снова чистым акцентом (4.02:1 на белом)"
    )
    for dark in (False, True):
        scheme = _scheme_css(dark)
        ratio = _ratio(_accent_text(scheme), _card(scheme))
        assert ratio >= 4.5, (
            f"{'тёмная' if dark else 'светлая'} схема: подпись сегодняшнего дня {ratio:.2f}:1 < 4.5:1"
        )


# Харнесс покадрового замера лежит вне репозитория (локальный стенд /tmp/orch-cal3).
# Тест сторожит ловушку приёмки №2: зонд мягкого края чипов уводил полосу в scrollLeft=9999,
# и следующий кадр «после» снимался с прокрученной полосой — обрезанный край читался как дефект вёрстки.
FRAME_HARNESS = Path("/tmp/orch-cal3/measure.mjs")


@pytest.mark.skipif(
    not FRAME_HARNESS.exists(), reason="стенд покадрового замера недоступен (вне репозитория)"
)
def test_frame_capture_resets_chip_scroll():
    """Перед снятием кадра прокрутка полосы чипов сброшена в 0 (иначе в кадр попадёт обрезанный край)."""
    src = FRAME_HARNESS.read_text(encoding="utf-8")
    assert "scrollLeft=0" in src, "в харнессе пропал сброс прокрутки полосы чипов"
    step = src.index("const m = await ev(COLLECT);")
    capture = src.index("Page.captureScreenshot", step)
    window = src[step:capture]
    assert "scrollLeft=0" in window, (
        "полоса чипов не возвращается в начало перед снятием кадра — обрезанный край снова попадёт в «после»"
    )


def test_month_cell_geometry_is_reference():
    """Ячейка месяца: три ряда значков + подпись дают ровно 63px контента → ряд сетки 73px, шаг 75/76.

    Геометрия эталонная: gap 4px и поля 5px (любое уменьшение «уплотняет» месяц и ломает шаг сетки).
    Четвёртого ряда быть не может — код берёт три группы, остальное считает в «+N» (проверено ниже).
    """
    body = _rule(".cal-cell")
    assert "gap: 4px" in body, "зазор рядов в ячейке месяца не 4px — поехал шаг сетки 75/76"
    assert "padding: 5px 6px" in body, "поля ячейки месяца не эталонные (5px/6px)"
    assert "min-height: 58px" in body, "минимальная высота ячейки месяца изменилась"
    assert "overflow: hidden" in body, (
        "ячейка месяца должна обрезать лишнее, а не вылезать за рамку"
    )
    # арифметика ряда: подпись дня 15px + 3 ряда значков 12px + 3 зазора 4px = 63px контента
    assert 15 + 3 * 12 + 3 * 4 == 63, "контент ячейки с тремя рядами значков должен быть 63px"
    assert 63 + 2 * 5 == 73, "ряд сетки месяца должен остаться 73px"
    assert ".slice(0, 3)" in JS or "slice(0,3)" in JS, (
        "в коде пропал предел трёх рядов значков — четвёртый ряд начнёт вылезать из ячейки"
    )


def test_queue_action_icon_glyph_centered():
    """Значок кнопки-иконки очереди — по центру кнопки (было смещение 2px из-за margin-right: 4px)."""
    for sel in (".icon-btn .pico", ".icon-btn .pico svg"):
        assert "margin-right: 0" in _joined(sel), (
            f"{sel}: базовый отступ .pico сдвигает значок из центра"
        )


def test_topbar_refresh_is_right_aligned():
    """«Очередь ↻» в шапке: кнопка прижата к правому краю (было 2px разрыва и уезжающий заголовок)."""
    bar = _joined(".topbar")
    assert "position: relative" in bar, "шапке не от чего отсчитывать правый край"
    assert "--topbar-pad-r" in bar and "var(--sa-right)" in bar, (
        "правый отступ шапки не учитывает безопасную зону Telegram"
    )
    ghost = _joined(".topbar .icon-ghost")
    assert "position: absolute" in ghost and "right: var(--topbar-pad-r" in ghost, (
        "кнопка обновления не прижата к правому краю контента"
    )
    assert "translateY(-50%)" in ghost, "кнопка обновления не выровнена по центру строки"
    assert "var(--topbar-pad-r)" in _in_media(".topbar", "max-width: 640px"), (
        "на телефоне правый отступ шапки не пересчитан (14px вместо 22px)"
    )
    assert "max-width: calc(100% - 104px)" in _rule(".topbar-center"), (
        "заголовок может заехать под кнопку обновления"
    )


def test_week_chips_wrap_inside_agenda_column():
    """«Неделя» на телефоне: перенесённый чип дня остаётся в колонке дней (x=97), а не под подписью (x=31)."""
    assert _rule(".cal-wchips"), "чипы дня не вынесены в свою колонку (.cal-wchips)"
    col = _in_media(".cal-wcol", "max-width: 640px")
    assert "flex-wrap: nowrap" in col, (
        "ряд дня переносит колонку чипов на новую строку — чипы уезжают под подпись дня"
    )
    chips = _in_media(".cal-wchips", "max-width: 640px")
    assert "flex: 1 1 0" in chips, "колонка чипов не занимает ровно остаток строки"
    # разметка: чипы завёрнуты в .cal-wchips (иначе CSS не сработает)
    assert 'class="cal-wchips"' in JS, "в разметке «Недели» нет обёртки .cal-wchips"


def test_period_label_not_clipped_on_narrow_screens():
    """Подпись периода на 320px: «· Сегодня» скрывается, сама дата остаётся целой (было «21–27 сентября · Се…»)."""
    assert 'class="cal-note"' in JS, "приписка «· Сегодня» не вынесена в отдельный узел"
    assert 'esc(t("cal_today"))' in JS, "приписка «· Сегодня» потеряла перевод"
    note = _in_media(".cal-note", "max-width: 345px")
    assert "display: none" in note, (
        "на узких экранах приписка не скрывается — подпись снова обрежется"
    )
    assert "text-overflow: ellipsis" in _rule(".cal-period"), (
        "у подписи периода не осталось страховки от переполнения"
    )


def _svg_tags(src: str) -> list[tuple[str, float]]:
    """[(viewBox, stroke-width корневого <svg>)] — толщина берётся только у корня, не у зубцов."""
    out = []
    for m in re.finditer(r"<svg ([^>]*)>", src):
        attrs = m.group(1)
        vb = re.search(r'viewBox="([^"]+)"', attrs)
        sw = re.search(r'stroke-width="([\d.]+)"', attrs)
        if vb and sw:
            out.append((vb.group(1), float(sw.group(1))))
    return out


def test_icons_one_live_area_and_one_line_weight():
    """Все значки — в одной сетке: живая площадь квадратная, штрих при рендере 1.65px.

    ip_1: нормировка значка шторки/навигации делается viewBox'ом (чернила = 0.8 бокса), а толщина
    линии компенсируется (stroke-width = 1.8 × S / 24), иначе крупный viewBox утоньшал бы штрих,
    а мелкий — утолщал. Проверка ловит и трёхзначный viewBox (Chrome его молча игнорирует).
    """
    tags = _svg_tags(JS) + _svg_tags(HTML)
    assert len(tags) >= 25, f"разобрано слишком мало значков: {len(tags)}"
    for vb, sw in tags:
        nums = vb.split()
        assert len(nums) == 4, f"viewBox «{vb}» не из четырёх чисел — браузер его игнорирует"
        _x, _y, w, h = (float(v) for v in nums)
        assert abs(w - h) < 1e-6, f"живая площадь значка не квадратная: «{vb}»"
        assert w > 0
        if abs(w - 24) > 1e-6:  # нормированные значки: штрих приведён к 1.8 юнита при боксе 24
            assert abs(sw * 24 / w - 1.8) <= 0.02, (
                f"значок с viewBox «{vb}»: штрих {sw} даёт {sw * 24 / w:.2f} вместо 1.8 юнита — "
                "линия выпадает из общего веса"
            )


def test_icon_dots_are_visible_not_hairline():
    """Точки внутри значков — не волосок: «?»/«!» ≥0.9 юнита, точки «Ещё» 2.2 (было 0.6–0.7 и 1.6)."""
    for name in ("help", "warn"):
        svg = re.search(rf"{name}: '(<svg[^']+)'", JS).group(1)
        r = max(
            float(x) for x in re.findall(r'<circle[^>]*r="([\d.]+)"[^>]*fill="currentColor"', svg)
        )
        assert r >= 0.9, f"{name}: точка {r} юнита при 22px — волосок (нужно ≥0.9)"
    more = re.search(r'data-more="1"[\s\S]*?<svg[^>]*>([\s\S]*?)</svg>', HTML).group(1)
    radii = sorted(float(x) for x in re.findall(r'r="([\d.]+)"', more))
    assert radii == [2.2, 2.2, 2.2], f"точки «Ещё» {radii} — значок «тоньше» соседей по tabbar"


def test_gear_has_hole_and_thick_teeth():
    """Шестерня читается шестернёй: отверстие в центре и зубцы толще обводки (было «снежинкой»)."""
    gear = re.search(r"gear: '(<svg[^']+)'", JS).group(1)
    circles = [
        (float(a), float(b), float(c))
        for a, b, c in re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"', gear)
    ]
    assert len(circles) == 2, "у шестерни нет отдельного отверстия (было сплошное пятно)"
    outer, hole = max(circles, key=lambda c: c[2]), min(circles, key=lambda c: c[2])
    assert hole[2] >= 3.0, f"отверстие шестерни {hole[2]} юнита — при 22px не видно"
    assert outer[2] > hole[2] + 1.5, "обод и отверстие слиплись"
    teeth = re.search(r'<path[^>]*stroke-width="([\d.]+)"', gear)
    root = float(re.search(r'stroke-width="([\d.]+)"', gear).group(1))
    assert teeth and float(teeth.group(1)) >= root * 1.3, (
        "зубцы не толще обводки — шестерня снова выглядит снежинкой"
    )

def test_outline_icons_are_not_filled_by_css():
    """П6 (приёмка №3): CSS `fill` перебивает атрибут fill="none" у корня SVG — значки рисовались заливкой.

    Замер кадра after-light-390-more.png: «Справка» — сплошной диск (0 светлых пикселей внутри
    рамки чернил), «Ошибки» — сплошной треугольник, «Настройки» — ядро без отверстия; computed
    fill у значка был rgb(99,99,102) вместо none. Контурные значки (icon()) не заливаются,
    логотипы платформ (pIcon()) получают заливку отдельным классом .pico-brand.
    """
    base = _rule(".pico svg")
    assert "fill: none" in base, 'контурные значки снова заливаются: CSS fill перебивает fill="none"'
    brand = _rule(".pico-brand svg")
    assert "fill: currentColor" in brand, "логотипы платформ остались без заливки"
    assert 'class="pico pico-brand"' in JS, "pIcon() не помечает логотипы платформ классом .pico-brand"
    # правило-исключение должно идти после базового: специфичность одинаковая
    assert CSS.index(".pico svg { width: 16px") < CSS.index(".pico-brand svg"), \
        ".pico-brand svg стоит выше базового .pico svg и не сработает"
    block = JS[JS.index("const PLATFORM_ICONS"):JS.index("function pIcon")]
    assert 'fill="none"' not in block, "логотипы платформ стали контурными — заливка больше не нужна?"


def test_sheet_icons_are_item_ink_not_secondary():
    """Значки шторки — чернила пункта, а не «второстепенный» серый.

    Замер: значок #6E6E71 (--text-2) при подписи #2C2C2E (--text) — список читался неактивным.
    """
    body = _joined(".sheet-item .pico")
    assert "color: var(--text)" in body, "значок шторки не в чернилах пункта"
    assert "color: var(--text-2)" not in body, "значок шторки снова светлее подписи"


def test_today_ring_uses_ink_accent():
    """Кольцо «сегодня» в месяце — общий акцент для чернил, а не сырой --accent (#007AFF).

    Замер: неделя рисовала «сегодня» как #0064D1, месяц — кольцом #007AFF (бледнее).
    """
    body = _rule(".cal-cell.today")
    assert "outline" in body and "var(--accent-on-bg)" in body, \
        "кольцо «сегодня» ушло из общего акцента для чернил"
    assert "solid var(--accent)" not in body, "кольцо «сегодня» вернулось к сырому --accent"

