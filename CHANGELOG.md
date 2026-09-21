# Changelog

## 8.4.6 — P1 backend-пакет: publishing-дедлок, read-only, mock, слоты «в прошлом», sync

### Fixed
- **P1-1** `Publisher`: резерв `publishing` снимается на всех early-return (safety-block, пауза
  платформы, конфликт `ScheduleGuard`, read-only, hourly-limit). Раньше `_already_exists` вечно
  возвращал `__publishing__` — пара (сущность, платформа) больше не публиковалась никогда.
- **P1-2** флаг `--read-only` теперь реально выставляет `ORCH_READ_ONLY=1` (раньше только писал лог,
  и `orchestrator --read-only --daemon` продолжал публиковать «вживую»).
- **P1-7** long-слоты: `start_date` из прошлого больше не создаёт посты с датой в прошлом
  (Postiz публикует такие немедленно); фильтр `slot <= now` как у standalone.
- **P1-8** `create_postiz_client(dry_run=False)` при пустом `POSTIZ_API_TOKEN` — fail-fast вместо
  тихой подмены моком (панель показывала «запланировано» без реальной публикации).
- **P1-4** `StatusSync`: успешный `get_post` сбрасывает счётчик `missing_in_postiz:N`; строки
  `error` с живым `postiz_post_id` снова попадают в синхронизацию и восстанавливаются.

### Tests
- +4 (328): релиз резерва при safety-block, отсутствие слотов в прошлом, восстановление sync,
  fail-fast фабрики Postiz. version 8.4.6 (build 825).

## 8.4.5 — P0: чтение произвольных файлов через /webapp/b/<build>/

### Security
- **P0 (критично)**: `WebAppAPI._file()` строил путь как `WEBAPP_DIR / name`, а `name` берётся из URL.
  Абсолютный путь (`GET /webapp/b/825//etc/host.conf`, без ключа) давал `Path(base) / "/etc/…" == "/etc/…"`
  → **неаутентифицированное чтение любых файлов**, доступных пользователю сервиса: `.env` (819 Б),
  `data/data.sqlite` (544 КБ), pinned CA и т.п. Проверялся только `".." not in qpath`, ведущий `/` не отбивался.
- Фикс: `_file` резолвит путь и требует, чтобы он лежал внутри `WEBAPP_DIR` (containment), плюс срезает
  ведущие `/`; иначе 404. Симптом воспроизведён живьём на проде (в т.ч. через публичный cloudflared-туннель).
- Регресс-тест: `tests/test_webapp_roots.py::test_build_path_rejects_absolute_and_dotdot`

### Tests
- 324 теста · ruff 0 · check.sh PASS · version 8.4.5 (build 825)

## 8.4.4 — Заголовок страницы по-настоящему по центру

### Fixed
- «Обновить» вынесена из потока (absolute у правого края заголовка): иконка больше не входит
  в центрируемую группу и не сдвигает название раздела влево. Замер CDP 390px:
  центр заголовка = центр экрана (**offset 0**); было −22px (title cx=173 при центре 195)
- press-scale и focus иконки сохранены (`translateY(-50%)` учитывается в `:active`/`:focus-visible`);
  правый верх по-прежнему пуст под нативные кнопки Telegram

### Tests
- 323 теста · ruff 0 · xss/csp linter · check.sh PASS · gui_check PASS
- version 8.4.4 / WEBAPP_BUILD=825

## 8.4.3 — Заголовок по центру + «Обновить» символом рядом

### Changed
- Заголовок страницы выровнен **ровно по центру** экрана; рядом с ним — «Обновить»
  в виде **символа-иконки** (↻, ghost-кнопка без заливки, тап 44px, press-scale, спин при обновлении)
- Правый верхний угол **полностью свободен** под нативные кнопки Telegram (✕/⋮) —
  перекрытий не может быть в принципе; полоса резерва 60px сохраняется для старых клиентов
- Подписи кнопки «Обновить» ушли в aria-label/title (локализуются при смене языка)

### Tests
- 323 теста · ruff 0 · check.sh PASS · gui_check PASS (боевой b824)
- CDP-замер: groupCenter == viewportCenter (offset 0), зона кнопок TG пуста (0 элементов),
  overflow 0
- version 8.4.3 / WEBAPP_BUILD=824
## 8.4.2 — Выравнивание CTA на «Обзоре» + полоса кнопок Telegram

### Fixed
- «Добавить видео» / «Очередь» теперь живут в **той же сетке, что и карточки** счётчиков:
  левый край = край «Опубликовано», правый = край «В ожидании» (замер: 14→189 и 201→376,
  ширина 175 = как у карточек)
- Полоса нативных кнопок Telegram (✕/⋮) держится **пустой**: в fullscreen заголовок остаётся
  первой строкой слева, действия («Обновить») переносятся второй строкой, выровнены по краю
  карточек; резерв полосы увеличен до 60px (кнопка TG 44px + отступы)

### Tests
- 323 теста · ruff 0 · check.sh PASS · gui_check PASS (боевой b823)
- version 8.4.2 / WEBAPP_BUILD=823
## 8.4.1 — Верхняя полоса Telegram больше не перекрывает интерфейс

### Fixed
- **Критично (было на старых клиентах TG)**: приложение обнуляло `--sa-*`, когда клиент не отдаёт
  `safeAreaInset`/`contentSafeAreaInset` → ломался env-фолбэк и нативные кнопки ✕/⋮ Telegram
  перекрывали наши кнопки и подписи. Теперь: переменные не затираются, а в fullscreen включается
  вертикальный резерв `--chrome-top: 46px` (выравнивание по правому краю сохраняется —
  без «разъезда» относительно карточек)
- Резерв снимается автоматически при выходе из fullscreen (события `fullscreenChanged`/`viewportChanged`)
- Проверено эмуляцией обоих поколений клиентов: старый (нет инсетов, fullscreen) → кнопка «Обновить»
  на 54px от верха, выравнивание по краю карточки сохранено; новый (contentSafeAreaInset=96) → 104px,
  `--chrome-top: 0`

### Tests
- 323 теста · ruff 0 · check.sh PASS · gui_check PASS
- version 8.4.1 / WEBAPP_BUILD=822
## 8.4.0 — UI/UX 2.0: Telegram-native, ровные списки, План (день/неделя/месяц)

### Added
- **Telegram-native**: цвета из `themeParams` (панель совпадает с темой Telegram), инсеты
  `safeAreaInset`+`contentSafeAreaInset` (кнопки ✕/⋮ Telegram больше не перекрывают интерфейс),
  `setBottomBarColor`, `HapticFeedback` на тап/действие, нативная кнопка «Назад» в шторках
  (свой ✕ в шторке обложки скрывается внутри Telegram)
- **План (календарь)**: сегмент День/Неделя/Месяц; день — карточки постов, неделя — 7 дней с чипами,
  месяц — сетка с точками и счётчиком; YT+TG одного видео идут одной строкой (парные иконки)
- Примитивы: `.item` (grid 3 колонки, min-width 0), `.badge` (статусы), `.btn-grid`, `.seg`,
  `.panel-head`, `.field`, `.act-grid`
- Расписание: чипы дней, сегмент «Сколько в день» + time-пикеры, пояснение приоритета
  (платформа → группа → глобально), группы списком с чипами соцсетей
- «Действия»: полные подписи + короткое пояснение под каждой кнопкой, сгруппировано

### Changed
- Очередь: строка-карточка (обложка 72×108, заголовок 2 строки, статус-бейджем ниже,
  редактирование сверху и корзина снизу по граням), редактор — поля с подписью сверху
- Сети: одна кнопка в строке (пауза/возобновить), красный бейдж «Выключено», лимит строкой
- Остаток: ряд из 3 кнопок равной высоты, статус бейджем
- Видео: сетка кнопок равной высоты, «Сканировать» отдельной строкой
- Обзор: CTA равной ширины, счётчики 2×2, платформы списком
- Ошибки: отдельный экран с группировкой по платформе и полным текстом ошибки
- Справка: двухстрочный список (название + описание), без узких колонок
- Возвращены полные подписи кнопок («Распределить остаток», «Убрать лишние посты из Postiz»)
- Чистка legacy CSS (убраны дубли `.queue-col`/`.q-title`, `margin-top:34px` у чекбокса)
- version 8.4.0 / WEBAPP_BUILD=821
## 8.3.2 — Метрики переживают рестарт

### Fixed
- `Metrics` читает прошлый `metrics.json` при старте: счётчики (cycles, test_*, errors…) больше
  не обнуляются рестартом сервиса; `started_at`/`last_cycle_at` — новые

### Tests
- +1 (323): персистентность метрик через рестарт
- version 8.3.2 (WEBAPP_BUILD=820)
## 8.3.1 — Security/ops residual closure (A–F) 
    
### Security
- **A1**: учётка Postiz UI убрана из git; пароль **сменён** (bcrypt), старый отвергается
- **A2**: строгий CSP без `'unsafe-inline'` вообще — инлайн-стили (26 шт.) заменены утилит-классами,
  динамика через CSSOM; script+style подписаны per-request nonce
- **A8**: TLS-проверка к Postiz **включена** через pinned CA (`POSTIZ_VERIFY_TLS=/etc/orchestrator/postiz-ca.pem`,
  поддержка `VERIFY_X509_PARTIAL_CHAIN` для self-signed); `=0` больше не используется
- **A4**: ключ не попадает в логи (`key=***`), `Referrer-Policy: no-referrer`
- **A3**: `scripts/check_xss.py` (esc-инварианты, запрет inline-стилей, строгий CSP, build-id) — в `check.sh` и CI
- **A5**: предупреждение при `test_publish.enabled` с пустым `prod_integration_ids`

### Reliability / UX
- **D11**: авто-бэкап БД перед миграциями схемы (`backups/pre_migration_*.sqlite`)
- **D2**: предпроверка Telegram media >50 МБ (понятная ошибка до создания поста)
- **D12**: ошибки массовых операций очереди больше не глотаются (тост «Ошибок: N» + console.warn)
- **D14**: понятное сообщение при устаревшей сессии (401)
- **B6**: нет FOUC — подписи локализуются до показа приложения
- **F1**: молчаливые `except Exception: pass` → логирование (debug)

### Docs / CI
- `docs/RESIDUAL.md` — единый список остатков и ops-задач (A–F)
- HANDOFF/README/AGENTS/POSTIZ_LIVE синхронизированы (версия, тесты, backup, TLS)
- CI: XSS/CSP-линтер + GUI smoke (jsdom через `scripts/ci_gui_smoke.sh`)
- version 8.3.1 / WEBAPP_BUILD=820
## 8.3.0 — WebApp UI/UX: iPhone-first (Telegram Mini App) + Emil Kowalski

### Added
- Нижний **tabbar** (mobile): Обзор · Видео · Очередь · План + «Ещё» (шторка со вторичными
  разделами и переключателем RU|EN) — верхняя сетка навигации на телефоне убрана
- Шторка «Ещё» в стиле iOS-листа (grabber, safe-area, ровные ряды 44px)
- Новичок: stepper на «Видео» («Папка → Сканировать → Запустить»), 2 CTA на «Обзор»
- Единая система кнопок: токены `--btn-h: 44px`, `--btn-h-sm: 36px`, один ритм отступов,
  ellipsis при переполнении, не более одной primary в блоке
- Mobile full-bleed: `#app` 100% ширины (без max-width 980), высота `var(--wa-h)`
- Резерв под кнопку закрытия Telegram только в правом верхнем углу (`body.tg-fs .topbar`)
- Cover-лист снизу (iOS-шторка) + safe-area

### Changed
- I18N: короткие подписи навигации (Обзор/Видео/План/Сети/Стат.) и кнопок; EN синхронно
- Кнопки: единая плотная высота 36px в очередных/списочных контекстах, чипы фильтров —
  горизонтальный скролл на телефоне; primary на всю ширину только для одно-CTA рядов
  (выбор корней не растягивается)
- Тост на телефоне поднимается над tabbar; цвет статус-бара берётся из токена темы
- Иконки шторки «Ещё»: добавлены gear/chart/help (было swap/film/check)
- Обновление подписей и сайдбара, и tabbar из I18N (в HTML нет «зашитого» EN после boot)

### Tests
- +11 статических UI-тестов (`tests/test_webapp_ui_8_3.py`): tabbar, токены, mobile safe-area,
  I18N-синхронизация, XSS-инварианты, CSP nonce, отсутствие хардкода build id
- version 8.3.0 / WEBAPP_BUILD=819
## 8.2.4 — Live-находки: TTL-повторы + утечка токена в логи

### Fixed
- TTL-авто-очистка: `test_auto_cancelled` теперь исключается из «активных» тест-постов —
  повторные DELETE уже снятого поста каждый цикл (Postiz отвечал 500 на stale id) устранены
- **SECURITY**: httpx/httpcore логгеры приглушены до WARNING — на INFO они печатали полные URL,
  включая `https://api.telegram.org/bot<TOKEN>/getUpdates` (утечка токена в journal)

### Tests
- +2: повторная авто-очистка не делает DELETE; уровень httpx/httpcore ≥ WARNING
- version 8.2.4 / WEBAPP_BUILD=818
## 8.2.3 — Residual list closure (CSP nonce, YT test-clips, live-проверки)

### Security
- CSP: инлайн-скрипты панели подписаны **per-request nonce** (`script-src 'self' https://telegram.org 'nonce-…'`,
  без `'unsafe-inline'`); `style-src` оставлен inline осознанно (style-атрибуты UI) + `object-src 'none'`, `base-uri 'none'`

### Added
- `scripts/yt_cleanup_test_videos.py` — повторяемое удаление роликов `[orch-test]` с канала
  (token broker → OAuth refresh → direct engine; dry-run по умолчанию, `--yes` для удаления)
- Тесты: CSP nonce (unit + HTTP-заголовок), 429-backoff transport, uid-bucket

### Ops / verified live
- Оба тестовых ролика удалены с YouTube (канал = 2 боевых видео)
- initData freshness: свежий → 200, 3-суточный → 401 (боевой сервер)
- TTL-авто-очистка тест-постов: цикл runner снял просроченный пост до публикации, `test_auto_cancelled`,
  метрика `test_cancelled` видна в `/webapp/api/metrics`
- version 8.2.3 / WEBAPP_BUILD=817
## 8.2.2 — Residual polish

### Fixed
- XSS-хвосты в UI (11 мест): `d.parent` в cover-навигации, `data-p` папок/browse/roots,
  `it.title` в календаре, `data-video`, поля поиска и bulk-теги — всё через `esc()`
  (всего в app.js 66 вызовов esc; частичных `.replace(/"/g)` больше нет)
- Rate-limit bucket: user id берётся только из **HMAC-валидированного** initData
  (раньше — regex по сырому заголовку, подделываемо); при невалидном — key/XFF/anon
- CSP: зафиксирован TODO с планом nonce/hash в 8.3 (inline bootstrap панели)

### Tests
- +1 (uid-bucket после валидации; сырой initData bucket не создаёт)
- version 8.2.2 / WEBAPP_BUILD=816
## 8.2.1 — Residual closure (P0/P1/P2)

### Security
- SSRF cover/fetch: pin по проверенному IP (anti-rebinding TOCTOU), redirect-хопы ≤3 с ревалидацией,
  stream cap 25 MiB, отклонение localhost/*.localhost/*.local, decimal/hex/octal/dotted-quad IP-литералов и userinfo
- initData: проверка свежести auth_date (ORCH_WEBAPP_INIT_MAX_AGE_SEC, default 86400)
- UI XSS: 37 вставок данных API/ФС обёрнуты в esc() (paths, names, titles, warnings, errors, urls, атрибуты)
- Content-Length cap (ORCH_MAX_BODY_BYTES, default 50 MiB) — 413 до чтения тела
- test_publish: test_integration_ids allowlist (fail-closed) + prod-guard
- rate-limit identity: ключ/user-id/первый XFF (раньше — весь Init-Data, менялся каждый запрос)

### Fixed
- N1: ask_backlog/remind_backlog/backlog_distributed/broadcast_markup были вложены в setup_commands
  и вызывались через несуществующий self → вопрос о остатке серии молча не отправлялся; вынесены на класс
- P0.11: ask_series_end теперь регистрирует pending-диалог; ответ "да" чистит pending и включает хвост
- P0.9: soft-end и backlog больше не делят одни поля (schema v13: pending_backlog_*; миграция переносит старые pending)
- P0.10: backlog-слоты считаются из effective-настроек (override/группы/исключения), а не из сырого конфига
- P0.4: cancel_test_post — точное совпадение post id (префикс больше не матчит чужой пост)
- P0.8: активные тест-посты исключены из cleanup_orphans и reconciliation
- P1.1: DELETE/PUT через retry-helper; 429 учитывает Retry-After (clamp 1..60)
- P1.2: тест-пост не расходует daily_limit/min_interval, но уважает паузу платформы
- P1.3/P1.11: авто-снятие тест-постов старше cleanup_after_hours (24ч) в цикле runner
- P1.4: pause_platform/resume_platform — UPSERT (нет строки → создаётся)
- P1.5: cloudflared_url_sync — безопасный JSON, проверка ответа Telegram, рестарт только при смене env
- P1.9: direct_youtube.delete не возвращает True при ошибке транспорта
- P1.10: send_message проверяет ответ Bot API и делает backoff на 429
- P2: watcher LRU-trim кэша размеров; TODO по CSP; ScheduleGuard TTL из ORCH_GUARD_TTL_SEC;
  MCP-инструменты orch_test_schedule/status/cancel; метрики test_scheduled/cancelled/rejected
- Конфиг: backup.method=sqlite_backup (код всегда использовал Connection.backup)

### Tests
- +45 тестов (255 → 300): SSRF-pin (22), миграции (4), P0.9–P0.12, P1.x, изоляция тест-контура, SQLi, read-only
- version 8.2.1 / WEBAPP_BUILD=815
## 8.2.0 — Test publish (отдельный контур) + регресс-закрепление H1–H3

### Added
- `test_publish` (config): enabled/allowlist/лимиты задержки/title_prefix/prod-guard/zero_jitter; по умолчанию выключено
- `POST /webapp/api/test/schedule` — пробный пост в Postiz через N минут (по умолчанию 1), БЕЗ записи в `entity_platform_status`
- `GET /webapp/api/test/status` — состояние контура + последние тестовые посты
- `POST /webapp/api/test/cancel` — удалить тестовый пост из Postiz (только помеченные `test_scheduled`)
- UI: панель «Проверка (тестовый пост)» в Actions (платформа из allowlist, задержка, entity, dry-run, отмена)
- CLI: `--test-schedule --test-platform P --test-entity TYPE:ID [--test-delay N] [--test-dry-run]`
- Тесты: `tests/test_test_publish.py` (13): границы задержки, allowlist, prod-guard, dry-run, cancel, API-level, read-only, SQLi

### Изменено
- `broker` доступен компонентам через `comps` (симлинк-медиа для тестового поста)
- version 8.2.0 / WEBAPP_BUILD=814

## 8.1.2 — Final parity polish

### Fixed
- Restored `scripts/ssd_copy_verify.sh` (was missing vs upstream)
- `BackupCfg.method` label → `sqlite_backup` (matches Connection.backup API)
- `gui_check.sh` no longer uses `/webapp/k/` path key by default
- Baseline `Content-Security-Policy` on HTML responses
- version 8.1.2 / WEBAPP_BUILD=812

## 8.1.1 — Stage polish (§10 checklist)

### Fixed
- **10.1**: backup via `sqlite3.Connection.backup()` (no `VACUUM INTO` f-string)
- **10.2**: cloudflared menu URL without `?key=` by default (`ORCH_WEBAPP_URL_WITH_KEY=1` = legacy)
- **10.3**: Postiz TLS verify **ON** by default; `POSTIZ_INSECURE_TLS=1` for lab
- **10.4**: `/webapp/k/<key>/` only when `ORCH_LEGACY_PATH_KEY=1`
- **docs**: `.env.example` security hints; `STAGE_ACCEPTANCE.md` for ops checklist

## 8.1.0 — Deep residual closure

### Fixed
- **R5**: log orphan media ids after CREATE fail (uploaded media without post)
- **R7**: media `_cached_size` wired + bounded cache
- **R2**: watcher `_size_cache` hard-capped (10k entries)
- **L14**: `posts_today` resets on timezone calendar day change in `record_post`
- **publisher**: deduped create-retry block; reserve always released to `error` on fail
- **version**: 8.1.0 / WEBAPP_BUILD=81

## 8.0.0 — Full residual closure (P2/Q)

### Fixed
- **README**: engines description aligned with §6 (manual_uploads only, not main Publisher)
- **S8**: broker SQL alphanumeric whitelist (no free-form injection)
- **S16**: rate-limit uses first X-Forwarded-For hop only
- **S17**: MCP servers refuse start without token when `ORCH_MCP_REQUIRE_TOKEN=1`
- **S19**: metrics payload sanitized (strip token/secret keys)
- **R3**: partial UNIQUE index on `postiz_post_id` (schema v12)
- **R9**: schedule_guard TTL via `ORCH_GUARD_TTL_SEC` (default 86400)
- **R13**: read_only blocks mutating webapp API routes
- **L9**: overflow move batch hard-capped (200)
- **L30**: `exception_days` respected in `can_schedule`
- **XSS**: `esc()` on error messages in webapp
- **Q CORS**: optional `ORCH_CORS_ORIGIN`
- **Q**: bare `except:` → `except Exception:` across orchestrator
- **version**: `__version__=8.0.0`, `WEBAPP_BUILD=80`

### Prior waves (summary)
- **7.5.2 A**: S1–S7, S11, R1', CREATE-flow integrity
- **7.6.0 B**: L1–L8, L12, L46 scheduling truth
- **7.7.0 C**: L17–L21, L28–L29, L43–L45 tail/links/honesty
- **7.8.0–7.9.0 D+**: L38, R6, R8, S14, S18, D9, soft-enter, compress TG limit

### Residual runtime risks (cannot close in static code alone)
- Postiz OAuth / state machine on live API
- Multi-host SQLite writers without external lock
- SMB/network FS races for in-flight encodes
- Historical secrets in git history (rotate keys operationally)
- Full CSP on every innerHTML title field (partial esc only)

