# Восстановление сервера из этого архива — короткий путь

Порядок: **хост → VM platform → наш оркестратор → проверка.** Всё скриптами, руками ничего править не надо.

```bash
# 0. распаковать архив (на новом сервере, от root)
tar -xzf orch-server-*.tar.gz && cd orch-server-*

# 1. хост Proxmox: /etc, конфиги VM, ключи, /usr/local, cloudflared, сервисы
bash restore/host.sh .

# 2а. если VM platform потеряна — создать её (образ Ubuntu скачается сам)
bash restore/vm-create.sh .
# 2б. восстановить содержимое VM (docker, каталог, compose, все базы, образ)
bash restore/vm-data.sh .

# 3. наш оркестратор: код, настройки, секреты, база, окружение, сервисы
bash restore/app.sh .

# 4. проверка: панель, API, Telegram-кнопка, VM, база
bash restore/checks.sh .
```

## Что важно знать
- **Видео-диски.** Оркестратор следит за `/mnt/video` и `/mnt/ssd_src` — после восстановления их нужно
  смонтировать (`/etc/fstab` вернётся на шаге 1). Само содержимое в архив не входит, но состав
  и объёмы записаны в `proxmox/_video_disks.txt`.
- **Права.** Сервис работает от пользователя `orchestrator` (не root) — `app.sh` создаёт его сам.
- **Секреты внутри.** В архиве `.env` (токен бота, ключ панели) и дампы баз — держать как секрет.
- **Медиа в архив не входит** (так решил владелец). Уже опубликованные видео/обложки не вернутся,
  но подключения к каналам и их токены лежат в базе platform, поэтому публикации продолжатся.
- **Образ platform** (`platform-fixed`) в интернете не публикуется: он собирается из патча
  `/home/platform/patch/Dockerfile` — это делает `vm-data.sh` (нужен интернет).
- **Версии пакетов** — в `proxmox/_packages.txt` и `platform/_packages.txt` (с версиями, не только имена).
- **Что проверить после восстановления:** `bash restore/checks.sh` → должно быть «ИТОГ: восстановление подтверждено».
- Полезные документы рядом: `RESTORE.md` (подробно по шагам), `personal/README.md` (личные файлы владельца).

## Если что-то не поднялось
1. Смотри журнал: `journalctl -u orchestrator -n 100 --no-pager`.
2. Панель изнутри: `curl -H "X-Webapp-Key: $(grep -oP '^WEBAPP_ACCESS_KEY=\K.*' /opt/orchestrator/.env)" http://127.0.0.1:8080/webapp/api/status`.
3. platform: `ssh root@<VM_HOST> 'cd /home/platform/platform && docker compose logs --tail=50 platform'`.
4. Повтори шаг: скрипты идемпотентны — их можно запускать повторно.
