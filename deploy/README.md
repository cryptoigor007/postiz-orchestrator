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
sudo systemctl enable --now postiz-tunnel-sync.timer
```

## Что лежит в deploy/ (юниты и скрипты)

| Файл | Куда ставится | Зачем |
|---|---|---|
| `orchestrator.service` | `/etc/systemd/system/` | основная служба: публикация, панель, синхронизация |
| `orchestrator-watchdog.{service,timer}` | туда же | сторож службы (проверка раз в 2 мин) |
| `infra-watchdog.{service,timer}` | туда же | панель + токен-брокер + туннель, и защита от сетевого «спама» (раз в 5 мин) |
| `orch-backup.{service,timer}` | туда же | ночной бэкап конфигурации и БД (04:00, `/usr/local/lib/orch-backup/backup.sh`) |
| `token-broker.service` | туда же | брокер токенов Postiz |
| `net-watchdog.{service,timer}` + `net-watchdog-safe.sh` | туда же + `/usr/local/sbin/net-watchdog.sh` | безопасное восстановление сети (без «войны маршрутов»), раз в 60 с |
| `lan-fix.service` + `lan-fix.sh` | туда же + `/usr/local/sbin/` | маршрут до ВМ Postiz через Wi-Fi; от него зависит `cloudflared-postiz` и публикация |
| `lan-default.sh` | `/usr/local/sbin/` | дефолтный LAN-маршрут (запускается udev-правилом на USB-сетевухе) |
| `vm-nat.service` + `vm-nat.sh` | туда же | NAT/форвардинг для ВМ Postiz |
| `cloudflared-url-sync.{service,timer}` + `cloudflared_url_sync.sh` | туда же + `/usr/local/bin/` | публичный URL панели → меню-кнопка Telegram (раз в минуту) |
| `cloudflared-postiz.service` | туда же | quick tunnel к ВМ Postiz (`https://192.168.100.60`) — публичный доступ к панели Postiz (адрес меняется при перезапуске, см. строку ниже); `ExecStartPost` пишет текущий адрес в `/var/lib/cloudflared-postiz.url` |
| `cloudflared-postiz-url.conf` | drop-in: `/etc/systemd/system/cloudflared-postiz.service.d/10-postiz-url.conf` | та же строка `ExecStartPost` отдельным дроп-ином для уже работающей службы (юнит не трогаем, туннель не перезапускаем — иначе сменится адрес). Если юнит поставлен из репо, дроп-ин не нужен, но и не мешает (запись идемпотентна). В дроп-ине — **только** `ExecStartPost`: `ExecStart=` там повторять нельзя, systemd добавит второй и откажется стартовать юнит |
| `postiz-tunnel-sync.{service,timer}` + `postiz_tunnel_sync.sh` | `/etc/systemd/system/` (pve) + `/opt/orchestrator/scripts/` (ставится деплоем) | проверяет, что публичный адрес quick-туннеля Postiz совпадает с `MAIN_URL`/`FRONTEND_URL` в compose ВМ; при расхождении пишет в журнал, что именно поменять (раз в 30 мин) |
| `postiz-purge-drafts.{service,timer}` + `postiz_purge_drafts.sh` | **в ВМ 120**: `/etc/systemd/system/`, `/usr/local/bin/` | мягкое удаление черновиков Postiz старше часа, каждые 15 мин |
| `logrotate-host-logs` | `/etc/logrotate.d/orchestrator-host-logs` | ротация `/var/log/{net-watchdog,lan-default,usb-net-restore,ssd_backup}.log` (5 МБ × 5, сжатие) |
| `postiz_patch_streaming_upload.js`, `set_youtube_oauth.sh` | вручную | патч потоковой загрузки Postiz и разовая настройка YouTube OAuth |

Установка логротации: `sudo cp deploy/logrotate-host-logs /etc/logrotate.d/orchestrator-host-logs`.
Юниты `postiz-purge-drafts*` ставятся не на pve, а внутрь ВМ 120; `postiz-tunnel-sync*` — наоборот, на pve.

Проверка адреса туннеля Postiz (сменился адрес → публикация «в никуда», что обновлять: `docs/PLATFORM_SETUP.md`):
```bash
ssh root@<pve> 'bash /opt/orchestrator/scripts/postiz_tunnel_sync.sh'          # полный отчёт
ssh root@<pve> 'bash /opt/orchestrator/scripts/postiz_tunnel_sync.sh --check'  # режим таймера: тихо, пока всё синхронно
```
Скрипт только читает: он печатает готовые команды, а выполняет их человек. Таймер делает то же самое
каждые 30 минут и попадает в журнал только при расхождении.
Файл `/var/lib/cloudflared-postiz.url` теперь пишется сам при каждом естественном запуске туннеля
(`ExecStartPost`), вручную его править не нужно — скрипт в любом случае берёт свежий адрес из журнала.

## WebApp (Telegram)
- `WEBAPP_PUBLIC_URL=https://<public-https>/webapp/` (валидный TLS обязателен)
- Menu Button бота → этот URL (BotFather или `setChatMenuButton`)
- Публичный HTTPS: Tailscale Funnel (`tailscale funnel 8080`) либо Cloudflare Tunnel
- **Ключ доступа намеренно остаётся в URL панели** (`…/webapp/b/<BUILD>/?key=<WEBAPP_ACCESS_KEY>`) —
  осознанное решение от 2026-09-23: так открывается Mini App у владельца, ломать не нужно. Более старый
  вариант «ключа в URL нет» (флаг `ORCH_WEBAPP_URL_WITH_KEY` в версии скрипта на 40 строк) не используется —
  не «чинить» обратно.

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
rsync -az --delete --no-owner --no-group \
  --exclude venv --exclude .git --exclude __pycache__ --exclude .pytest_cache --exclude .ruff_cache \
  --exclude data --exclude backups --exclude logs --exclude .DS_Store --exclude .env \
  --exclude .cache \
  ./ root@<pve>:/opt/orchestrator/
ssh root@<pve> 'chown -R orchestrator:orchestrator /opt/orchestrator && \
  chmod 600 /opt/orchestrator/.env && systemctl restart orchestrator.service'
```

(на macOS штатный rsync не поддерживает `--chown` — владельца правим на сервере)

Если владелец уже сбит:
```bash
ssh root@<pve> 'chown -R orchestrator:orchestrator /opt/orchestrator && chmod 600 /opt/orchestrator/.env && systemctl restart orchestrator.service'
```
