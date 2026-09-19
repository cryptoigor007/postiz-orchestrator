# Деплой Orchestrator

## Установка
```bash
sudo useradd -r -s /usr/sbin/nologin orchestrator || true
sudo mkdir -p /opt/orchestrator/{data,backups,logs}
sudo cp -a . /opt/orchestrator/
sudo chown -R orchestrator:orchestrator /opt/orchestrator
# deps in a venv (Debian 13 is externally-managed)
sudo python3 -m venv /opt/orchestrator/venv
sudo /opt/orchestrator/venv/bin/pip install -r /opt/orchestrator/requirements.txt
# .env next to config.yaml (POSTIZ_*, TELEGRAM_*, WEBAPP_*)
sudo cp /opt/orchestrator/.env.example /opt/orchestrator/.env  # then edit
sudo cp /opt/orchestrator/deploy/*.service /opt/orchestrator/deploy/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now orchestrator.service
sudo systemctl enable --now orchestrator-watchdog.timer
```

## WebApp (Telegram)
- `WEBAPP_PUBLIC_URL=https://<public-https>/webapp/` (валидный TLS обязателен)
- Menu Button бота → этот URL (BotFather или `setChatMenuButton`)
- Публичный HTTPS: Tailscale Funnel (`tailscale funnel 8080`) либо Cloudflare Tunnel

## Health
curl http://127.0.0.1:8080/health

## Rollback
systemctl stop orchestrator.service
cp backups/data_YYYYMMDD_HHMMSS.sqlite data/data.sqlite
systemctl start orchestrator.service

## Обновление (деплой с Mac)
ВАЖНО: rsync не должен менять владельца файлов, иначе сервис потеряет запись в SQLite
(«attempt to write a readonly database»). Используй:

```bash
rsync -az --delete --no-owner --no-group --chown=orchestrator:orchestrator \
  --exclude venv --exclude .git --exclude __pycache__ --exclude .pytest_cache \
  --exclude data --exclude backups --exclude logs --exclude .DS_Store --exclude .env \
  ./ root@<pve>:/opt/orchestrator/
ssh root@<pve> 'systemctl restart orchestrator.service'
```

Если владелец уже сбит:
```bash
ssh root@<pve> 'chown -R orchestrator:orchestrator /opt/orchestrator && chmod 600 /opt/orchestrator/.env && systemctl restart orchestrator.service'
```
