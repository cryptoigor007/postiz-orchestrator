# Деплой Orchestrator

## Установка
```bash
sudo useradd -r -s /usr/sbin/nologin orchestrator || true
sudo mkdir -p /opt/orchestrator/{data,backups,logs}
sudo cp -a . /opt/orchestrator/
sudo chown -R orchestrator:orchestrator /opt/orchestrator
sudo cp /opt/orchestrator/deploy/*.service /opt/orchestrator/deploy/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now orchestrator.service
sudo systemctl enable --now orchestrator-watchdog.timer
```

## Health
curl http://127.0.0.1:8080/health

## Rollback
systemctl stop orchestrator.service
cp backups/data_YYYYMMDD_HHMMSS.sqlite data/data.sqlite
systemctl start orchestrator.service
