# Stage acceptance checklist (операционная приёмка)

Цель: не «аудит закрыт в коде», а **система работает на stage**.
Пункт отмечать только после проверки на stage (или prod с бэкапом).

Код: `__version__` 8.1.1+, `WEBAPP_BUILD=81` (или выше).

## 0. Подготовка

- [ ] `__version__` совпадает с деплоем
- [ ] `WEBAPP_BUILD` = в URL панели `/webapp/b/<build>/`
- [ ] Backup SQLite + известен rollback
- [ ] Секреты только в env, не в git
- [ ] `WEBAPP_BROWSE_ROOT` задан и существует
- [ ] Один writer на БД
- [ ] `./scripts/check.sh` exit 0
- [ ] `PYTHONPATH=src pytest tests/ -q` green

## 1–9. Функциональные блоки

См. чеклист в сообщении приёмки (Security, Publish, Scheduling, Panel=daemon=CLI,
YT→TG, Tail, Media, Status, Config). Каждый пункт — **ручная** проверка на stage.

## 10. Polish (код 8.1.1)

| # | Статус в коде |
|---|----------------|
| 10.1 VACUUM → `Connection.backup()` | done |
| 10.2 Cloudflared без `?key=` (default) | done; legacy `ORCH_WEBAPP_URL_WITH_KEY=1` |
| 10.3 TLS verify default ON | done; opt-out `POSTIZ_INSECURE_TLS=1` |
| 10.4 `/webapp/k/` только с `ORCH_LEGACY_PATH_KEY=1` | done |
| 10.5 esc() на error paths | partial (ошибки); полный CSP — отдельный UI pass |
| 10.6 Ротация ключей | **ops**, не код |

## 11. E2E день

- [ ] long+shorts → watch → schedule → Postiz scheduled
- [ ] published+URL → TG/thematic refresh
- [ ] limits/pause/tail
- [ ] следующий день: лимиты по TZ

## 12. Sign-off

- [ ] §1–9 и §11 на stage
- [ ] Residual runtime принят
- [ ] Backup/rollback известны
- [ ] Подпись: дата ____ / версия ____
