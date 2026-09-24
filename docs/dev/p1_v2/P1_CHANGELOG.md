# P1 v2 — правки по фактам репо (720298f)

## Принято из ответа репозитория
- entity_platform_status: **нет** `updated_at`
- waiting_for_youtube = `status='ready' AND last_error='waiting_for_youtube'`, время = `postiz_scheduled_for`
- publish_log: колонка **`details`**, не `detail`
- `/webapp/api/modules_status` **нет** → убрано из P1
- Token/auth_status алерты → **P2** (token_store)
- `/force_link_update` уже делегирует в `link_updater` → правка только link_updater
- core_min не enforced; bump 8.5.0 в P5
- Postiz-путь thumbnail **не** чиним в P1
- QUOTA/AUTH: match по реальным `action` (upload_fail, create_fail, …), не ModuleErrorCode

## Файлы
- `p1/link_updater.py` — force_update для любого entity_type (как 2.1)
- `p1/infra_watchdog.py` — алерты по реальной схеме
- `tests/test_link_updater_force.py`

## Порядок
0) git pull && ./scripts/check.sh
1) скопировать P1 → check.sh → commit
2) только потом P2
