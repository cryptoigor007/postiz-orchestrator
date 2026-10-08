# Deploy notes (Platform Orchestrator)

**HARD_CUT:** runtime = module path. Postiz VM / tunnel **не required**.

## Config

```bash
# рядом с config.yaml
cp .env.example .env
# TELEGRAM_*, WEBAPP_*, optional TOKEN_BROKER_*
# POSTIZ_* — deprecated, не использовать
```

## Типичные unit-файлы (host)

| Unit | Назначение |
|------|------------|
| `orchestrator.service` | основной процесс |
| `token-broker.service` | OAuth token broker (не Postiz) |
| `webapp` / reverse-proxy | панель :8080 |

## Deprecated (не enable как required)

Следующие unit/скрипты относятся к legacy Postiz VM и **не** нужны module-path:

- `postiz-tunnel-sync.timer` / `postiz-tunnel-sync.service`
- `cloudflared-postiz.service`
- `lan-fix` / `vm-nat` «до ВМ Postiz»
- `postiz-purge` / operational POSTIZ_* env

Если файлы ещё лежат в `deploy/`, считать их historical; gate и runtime их не требуют.

## Gate

```bash
export PYTHONPATH=src:scripts
bash scripts/gate_platform_zero.sh
```

## Tokens

`tokens/*.json` на хосте оркестратора, не в БД Postiz.
