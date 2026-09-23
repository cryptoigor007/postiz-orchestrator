# Verification Checklist

Полный чеклист проверки системы. Выполнять сверху вниз. Все команды — из корня репозитория.

## 0. Локальные статические проверки
- [ ] `./scripts/check.sh` → «ALL CHECKS PASSED»
  - [ ] ruff — без замечаний
  - [ ] `compileall -q src scripts` — ok
  - [ ] `node --check webapp/app.js` — ok
  - [ ] `pytest -q` — все зелёные
- [ ] `git status` — чисто

## 1. Схема БД и миграции
- [ ] `python -c "from orchestrator.db import SCHEMA_VERSION; print(SCHEMA_VERSION)"` → актуальная (9+)
- [ ] таблицы: `long_videos, shorts, entity_platform_status, platform_queue_state,
      platform_safety_state, publish_log, system_state, platform_uploads`
- [ ] `platform_uploads` имеет уникальный ключ `(engine, platform, platform_video_id)` и частичный
      UNIQUE `(engine, platform, matched_entity_type, matched_entity_id) WHERE confirmed`

## 2. Сервисы (pve)
- [ ] `systemctl is-active orchestrator.service cloudflared-webapp.service cloudflared-url-sync.timer orchestrator-watchdog.timer` → active
- [ ] `curl -s http://127.0.0.1:8080/health` → `{"ok": true, ...}`

## 3. Сервисы (VM 120)
- [ ] `systemctl is-active token-broker.service` → active
- [ ] `docker ps` → postiz, postiz-db (healthy), postiz-redis, postiz-temporal, postiz-nginx-https-1, postiz-media
- [ ] broker: `curl -H "X-Broker-Secret: $S" http://192.168.100.60:9099/health` → `{"ok": true}`
- [ ] чужой IP/секрет → 403/401

## 4. WebApp API (эндпоинты)
Проверять с ключом `?key=$WEBAPP_ACCESS_KEY` (или заголовком `X-Webapp-Key`).
- [ ] `GET  /webapp/api/version`
- [ ] `GET  /webapp/api/status`
- [ ] `GET  /webapp/api/metrics` (есть `live` с queue/published/failed)
- [ ] `GET  /webapp/api/calendar` (сливается с Postiz)
- [ ] `GET  /webapp/api/queue`
- [ ] `GET  /webapp/api/platforms`
- [ ] `GET  /webapp/api/tail`
- [ ] `GET  /webapp/api/failed`
- [ ] `GET  /webapp/api/roots` (есть `browse_roots`)
- [ ] `GET  /webapp/api/browse?path=`
- [ ] `POST /webapp/api/scan`
- [ ] `POST /webapp/api/pause` / `resume` / `resume_platform` / `pause_platform`
- [ ] `POST /webapp/api/series_end`
- [ ] `POST /webapp/api/distribute`
- [ ] `POST /webapp/api/schedule`
- [ ] `POST /webapp/api/sync`
- [ ] `POST /webapp/api/reconcile`
- [ ] `POST /webapp/api/backup`
- [ ] `POST /webapp/api/force_link`
- [ ] `GET  /webapp/api/manual/plan`
- [ ] `GET  /webapp/api/manual/uploads`
- [ ] `GET  /webapp/api/manual/uploads/:id/candidates`
- [ ] `POST /webapp/api/manual/scan`
- [ ] `POST /webapp/api/manual/uploads/:id/confirm|reassign|reject|ignore|claim-mark|claim-action`

## 5. WebApp UI (рендер)
- [ ] разделы видны: Статус, Папки, Ручные, Календарь, Очередь, Платформы, Хвост, Ошибки,
      Метрики, Действия, Справка
- [ ] «Действия»: кнопки Синхронизировать / Реконсиляция / Бэкап / Разложить по слотам /
      Обновить ссылку (список платформ динамический, включает telegram)
- [ ] «Платформы»: Пауза и Возобновить на каждой
- [ ] «Ручные»: Сканировать всё/по платформе; Пометить клейм; Подтвердить/Не моё/Игнорировать
- [ ] «Папки»: корни Сеть/Локально; Открыть/Вверх/Добавить/Сканировать
- [ ] переключатель RU/EN работает; скролл на телефоне работает; панель на всю высоту

## 6. MCP
- [ ] `scripts/mcp_server.py` — инструменты включают `orch_sync/reconcile/backup/schedule/
      pause_platform/manual_*`
- [ ] `scripts/postiz_mcp_server.py` — `postiz_integrations/posts/create/...`
- [ ] в ИИ-клиенте (opencode) MCP подключается и отдаёт tools

## 7. Публичный доступ
- [ ] `cat /var/lib/cloudflared-webapp.url` → URL с `/webapp/k/<key>/b/<build>/`
- [ ] `getChatMenuButton` бота → тот же URL
- [ ] headless-рендер URL: `#gate hidden`, `#app` виден

## 8. Безопасность
- [ ] секретов нет в трекнутых файлах (`git grep <secret>` пусто)
- [ ] `.env` в `.gitignore`
- [ ] broker ограничен секретом и IP-allowlist
- [ ] webapp API rate-limit (`WEBAPP_RATE_LIMIT`) → 429 при превышении

## 9. Деплой
- [ ] `rsync -ain --delete ... ./ root@pve:/opt/orchestrator/` → `IDENTICAL`
- [ ] после restart `orchestrator.service` active, `/health` ok

## 10. Ручные загрузки (требует подключённого канала)
- [ ] в Postiz подключён канал нужной платформы (иначе `token broker: no token for ...`)
- [ ] `POST /manual/scan` находит ручные загрузки (origin=manual), предлагает кандидатов
- [ ] подтверждение → `match_status=confirmed`, `entity_platform_status=published` + `release_url`
- [ ] повторный скан не дублирует; конфликт → 409
- [ ] клейм: пометка → warning → удалить/оставить/игнорировать
