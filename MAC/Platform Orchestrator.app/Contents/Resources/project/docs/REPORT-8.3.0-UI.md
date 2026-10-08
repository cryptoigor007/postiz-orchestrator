# Отчёт 8.3.0 — WebApp UI/UX (iPhone-first · Telegram Mini App · Emil Kowalski)

**Версия:** 8.3.0 · **Сборка:** b819 · **Тесты:** 321 (+11 UI +1 I18N-полнота) · **ruff:** 0 · `check.sh`: PASS · `gui_check.sh` (боевой): PASS
**Метод проверки вёрстки:** headless Chrome + CDP-эмуляция iPhone (390×844, dsf 3, mobile) и desktop (1280×860) — замеры геометрии + скриншоты.

## §8. Чеклист самопроверки — статусы

### Telegram / экран
- [x] `expand` вызывается; `requestFullscreen` при наличии API — **есть, не менялось** (boot)
- [x] `--wa-h` обновляется на viewportChanged — **есть** (`viewportStableHeight || viewportHeight || innerHeight`)
- [x] mobile `#app` на 100% ширины, без max-width 980 — **замер: innerWidth 390, docScrollW 390, gridW 362**
- [x] safe-area top/bottom учтены; home indicator не режет tab bar — `padding-bottom: env(safe-area-inset-bottom)` у tabbar и контента (**contentPadBottom 73px** = 49 + 24 + safe)
- [x] в fullscreen крестик TG не перекрывает Refresh/заголовок — `body.tg-fs .topbar { padding-right: 60px+safe }` (только правый верх)
- [x] `disableVerticalSwipes` при наличии API — **есть**

### Kowalski / визуал
- [x] ease-out + press scale сохранены; reduced-motion уважается — **не менялось** (токены `--dur-*`, `@media reduce`)
- [x] не больше одной primary-кнопки в видимом блоке — **автотест** `test_primary_single_per_form_row` + ручной аудит 13 мест
- [x] все основные `.btn` одной высоты (44px) в одном ряду — токены `--btn-h: 44px`; **замер: refreshBtnH = 44**
- [x] нет «пляшущих» кнопок из-за текста — `.btn { height; overflow:hidden; text-overflow:ellipsis }` + короткие I18N
- [x] chips одной высоты; horizontal scroll на узком экране — `.chip{min-height:36}` + mobile `flex-wrap:nowrap; overflow-x:auto`
- [x] очередь: единый стиль action controls — 36px для текстовых и иконочных в строке очереди (**замер 36**) 

### Навигация / UX
- [x] mobile: bottom tabs ≤5; вторичное в «Ещё» — **5 табов ×78px = 390** (замер), шторка: 8 пунктов + RU|EN
- [x] desktop: sidebar с теми же короткими подписями из I18N — **замер: tabbar none, sidebar flex, appW 980**
- [x] nav labels не захардкожены английским в HTML — `updateNavLabels()` обновляет и `#nav`, и `#tabbar`; в HTML — русские дефолты
- [x] на «Видео» есть короткий stepper — **проверено в браузере**: «Папка → Сканировать → Запустить. Дальше само.»
- [x] базовый путь: папка → скан → запуск понятен без Help — CTA «Добавить видео»/«Очередь» на «Обзор», stepper на «Видео»

### Безопасность / регресс
- [x] `esc()` не откатан; нет сырых path/title в innerHTML — **автотест** `test_xss_invariants_still_hold` (66+ esc)
- [x] CSP nonce script не сломан — **автотест** + live: заголовок `script-src … 'nonce-…'`, nonce тела совпадает
- [x] pytest / ruff / check.sh PASS — 321 / 0 / PASS
- [x] version 8.3.0 + WEBAPP_BUILD 819 + CHANGELOG + HANDOFF

### Честный residual
- [x] Если fullscreen недоступен — degrade: `expand` + 100% ширины/высоты (CSS), описано в отчёте
- [x] «Проверено на ширине 375» — проверено на **390×844 (iPhone 12/13/14)** через CDP-эмуляцию; **375 не проверял** (при 375 сетка карточек станет 1-2 колонки — ожидаемо)

## Что сделано (файлы)

| Область | Файл | Изменения |
|---|---|---|
| Разметка | `webapp/index.html` | Нижний `#tabbar` (4 раздела + «Ещё»), русские дефолты подписей (boot синкает из I18N) |
| Стили | `webapp/styles.css` | Токены кнопок (`--btn-h 44`, `--btn-h-sm 36`, radius/pad/gap/font), mobile full-bleed `#app`, безопасные зоны, tabbar (blur, 49px + safe, active accent), шторка `.sheet*`, cover-лист снизу, чипы-hscroll, тост над tabbar, плотные 36px в очередных контекстах, `:has()`-правило full-width primary (кроме `.roots-row`), резерв под кнопку TG |
| Логика/UI | `webapp/app.js` | `syncTabs`, `gotoView`, `openMoreSheet/closeMoreSheet` (guard от двойного, Escape), `updateNavLabels` для обоих навигаций, CTA на «Обзор» (`data-goto`), stepper на «Видео», короткие I18N RU/EN (nav/кнопки), +иконки gear/chart/help, цвет темы из CSS-токена для статус-бара |
| Тесты | `tests/test_webapp_ui_8_3.py` | 11 статических UI-тестов (tabbar, токены, mobile safe-area, I18N-синхронизация, XSS-инварианты, CSP nonce, build-id, одна primary, roots-row, I18N-полнота) |
| Доки | `CHANGELOG.md`, `README.md`, `docs/HANDOFF.md` | 8.3.0 / b819 / 321 |

## Найденные и исправленные по ходу дефекты

1. **`t("mu_claim_mark")` не был определён** ни в RU, ни в EN → на кнопке отображался сырой ключ. Добавлено «Отметить клейм» / "Mark claim" + новый **тест полноты I18N** (все `t("…")` есть в обоих словарях, словари симметричны: 345 = 345).
2. **Ложная тревога (честно):** первый скриншот показывал «горизонтальное переполнение» — это артефакт клампа окна headless Chrome (минимум ~500px), а не баг вёрстки. После эмуляции устройства: `docScrollW == innerWidth == 390`, `overflow: []` ✓.
3. **«Синяя стена»** — правило «primary на всю ширину» растягивало кнопку активного корня в ряду выбора; ограничено рядами из 2 элементов + исключён `.roots-row`.
4. **Статический тест падал** из-за комментария с `--bg (` (детектор «вызовов функций» видел `bg(`) → комментарий переформулирован, в ALLOWED добавлены DOM-глобалы.

## Осталось / предстоит (честно)

1. **375px** и **реальный iPhone/Telegram** не проверял (только CDP-эмуляция 390×844 + jsdom-`gui_check` без layout). Рекомендую один раз открыть панель в Telegram на iPhone и глянуть: tabbar, шторку, cover-лист.
2. **`style-src 'unsafe-inline'`** сохранён (style-атрибуты UI) — план: рефакторинг в классы (8.3.x/8.4).
3. **`requestFullscreen` на старых клиентах** может не сработать — degrade есть, но визуально не проверялся.
4. **Иконки шторки** — из ограниченного набора SVG (добавлены gear/chart/help); при желании владельца можно заменить на брендовые.
5. **Тесты вёрстки** — статические (CSS/JS), без pixel-diff; CDP-скрипты лежат в служебной папке и в репо не входят.
