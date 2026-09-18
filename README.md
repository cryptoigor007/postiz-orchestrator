# Orchestrator v7.3.0

VideoMaker + ShortsMaker → Postiz  
ТЗ 7.0 + Telegram bot + macOS WebApp (emilkowalski/skills polish)

## Quick start
```bash
export PYTHONPATH=src
export ORCH_FAST_RETRY=1 WEBAPP_DEV=1   # tests / local webapp
python3 -m pytest tests/ -q
python3 -m orchestrator.main --version
python3 -m orchestrator.main --config config.yaml --db data/data.sqlite --dry-run --once
python3 -m orchestrator.main --daemon --health-port 8080
```

## Env
```
POSTIZ_BASE_URL=
POSTIZ_API_TOKEN=
POSTIZ_PATH_UPLOAD=/api/media/upload
POSTIZ_PATH_POSTS=/api/posts
TELEGRAM_BOT_TOKEN=
TELEGRAM_MODE=poll
WEBAPP_PUBLIC_URL=https://host/webapp
WEBAPP_DEV=1
```

## WebApp
- Local: `http://127.0.0.1:8080/webapp/?dev=1`
- Prod: BotFather Menu Button → `WEBAPP_PUBLIC_URL`
- Screens: status, calendar, queue, platforms, tail, failed, metrics, actions

## Stage
`./scripts/stage_run.sh` + `config.stage.yaml`

## Deploy
See `deploy/README.md`, `docs/ROLLBACK.md`

## Design
`docs/EMIL_SKILLS.md` — emilkowalski/skills applied to WebApp motion/materials
