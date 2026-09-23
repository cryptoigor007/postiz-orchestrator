#!/usr/bin/env bash
# Серверная часть бэкапа: собирает архив на pve и делает ротацию.
#
# Запускается двумя путями:
#   1) с Mac:  bash scripts/backup_server.sh   (он передаёт NAME/REMOTE_DIR/KIT_SRC через ssh)
#   2) на pve: systemd-таймер orch-backup.timer (ежедневно в 04:00, Persistent=true)
# Поэтому у переменных есть значения по умолчанию — на сервере без них всё работает.
#
# Ротация: KEEP ежедневных архивов (7) + MONTHLY_KEEP месячных (12, каталог monthly/).

set -euo pipefail

NAME="${NAME:-orch-server-$(date +%Y-%m-%d_%H%M)}"
REMOTE_DIR="${REMOTE_DIR:-/root/backups}"
KEEP="${KEEP:-7}"
MONTHLY_KEEP="${MONTHLY_KEEP:-12}"
VM_IP="${VM_IP:-192.168.100.60}"
BACKUP_PERSONAL="${BACKUP_PERSONAL:-0}"
BACKUP_WITH_BINARY="${BACKUP_WITH_BINARY:-1}"
# набор скриптов восстановления: с Mac его присылают в /tmp/restore-kit,
# на сервере лежит постоянная копия в /usr/local/lib/orch-backup/restore_kit
KIT_SRC="${KIT_SRC:-/tmp/restore-kit}"
[ -d "$KIT_SRC" ] || KIT_SRC="/usr/local/lib/orch-backup/restore_kit"

set -euo pipefail
TMP="/tmp/$NAME"
OUT="$REMOTE_DIR"
rm -rf "$TMP"; mkdir -p "$TMP"/{orchestrator,systemd,proxmox,postiz} "$OUT"

# ── 1. Наш оркестратор: настройки, секреты, базы + снимок исходников ──────────────
if [ -d /opt/orchestrator ]; then
  for f in config.yaml .env; do
    [ -f "/opt/orchestrator/$f" ] && cp -a "/opt/orchestrator/$f" "$TMP/orchestrator/"
  done
  [ -d /opt/orchestrator/data ] && cp -a /opt/orchestrator/data "$TMP/orchestrator/data"
  [ -d /opt/orchestrator/certs ] && cp -a /opt/orchestrator/certs "$TMP/orchestrator/certs"
  find "$TMP/orchestrator" -name '*.log' -delete 2>/dev/null || true
  # исходники и скрипты — чтобы код не зависел от репозитория на Mac
  tar -czf "$TMP/orchestrator/source.tar.gz" -C /opt/orchestrator \
    --exclude='./venv' --exclude='./data' --exclude='./logs' --exclude='./backups' \
    --exclude='./certs' --exclude='./.git' --exclude='__pycache__' --exclude='.pytest_cache' \
    --exclude='*.pyc' . 2>/dev/null || true
  ls -la /opt/orchestrator > "$TMP/orchestrator/_listing.txt" 2>&1 || true
  du -sh "$TMP/orchestrator" > "$TMP/orchestrator/_size.txt" 2>&1 || true
  { uname -a; python3 --version 2>&1; systemctl is-active orchestrator; } \
    > "$TMP/orchestrator/_runtime.txt" 2>&1 || true
  [ -x /opt/orchestrator/venv/bin/pip ] && /opt/orchestrator/venv/bin/pip freeze \
    > "$TMP/orchestrator/_pip_freeze.txt" 2>&1 || true
fi

# ── 2. systemd: наши юниты и что вообще включено на хосте ────────────────────────
for u in orchestrator.service cloudflared-webapp.service cloudflared-url-sync.service cloudflared-url-sync.timer; do
  [ -f "/etc/systemd/system/$u" ] && cp -a "/etc/systemd/system/$u" "$TMP/systemd/"
done
systemctl list-units --type=service --state=running --no-pager > "$TMP/systemd/_running.txt" 2>&1 || true
systemctl list-unit-files --state=enabled --no-pager > "$TMP/systemd/_enabled.txt" 2>&1 || true
systemctl list-timers --all --no-pager > "$TMP/systemd/_timers.txt" 2>&1 || true
crontab -l > "$TMP/systemd/_root_crontab.txt" 2>&1 || true

# ── 3. Proxmox-хост: всё, что нужно для переустановки с нуля ────────────────────
tar -czf "$TMP/proxmox/pve-etc.tar.gz" -C /etc pve 2>/dev/null \
  || echo "не удалось упаковать /etc/pve" > "$TMP/proxmox/_pve_error.txt"
tar -czf "$TMP/proxmox/host-etc.tar.gz" -C / etc 2>/dev/null || true
[ -d /root/.ssh ] && tar -czf "$TMP/proxmox/root-ssh.tar.gz" -C /root .ssh 2>/dev/null || true
# версии обязательно: без них на новой машине встанут другие версии
dpkg-query -W -f='${Package}=${Version}\n' > "$TMP/proxmox/_packages.txt" 2>&1 || true
pveversion -v > "$TMP/proxmox/_pveversion.txt" 2>&1 || true
# свои программы вне /etc: /usr/local (сам cloudflared 39 МБ не берём — он скачивается заново)
tar -czf "$TMP/proxmox/usr-local.tar.gz" -C /usr/local \
  --exclude='bin/cloudflared' --exclude='lib' bin sbin etc share 2>/dev/null || true
{ uname -a; echo; cat /etc/os-release 2>/dev/null | head -3; echo; \
  cloudflared --version 2>&1; docker --version 2>&1; \
  python3 --version 2>&1; pip3 --version 2>&1; git --version 2>&1; } \
  > "$TMP/proxmox/_tools_versions.txt" 2>&1 || true
pvesm status > "$TMP/proxmox/_storage_status.txt" 2>&1 || true
{ lvs 2>/dev/null; vgs 2>/dev/null; pvs 2>/dev/null; zpool status 2>/dev/null; } \
  > "$TMP/proxmox/_storage_layout.txt" 2>&1 || true
{ lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT 2>/dev/null; echo; blkid 2>/dev/null; \
  echo; findmnt --real 2>/dev/null; } > "$TMP/proxmox/_block_devices.txt" 2>&1 || true
{ uname -a; echo; ip -br a 2>/dev/null; echo; ip r 2>/dev/null; } \
  > "$TMP/proxmox/_network.txt" 2>&1 || true
{ nft list ruleset 2>/dev/null || iptables-save 2>/dev/null; } \
  > "$TMP/proxmox/_firewall.txt" 2>&1 || true
[ -s "$TMP/proxmox/_firewall.txt" ] || echo "правил firewall нет (по умолчанию открыто)" \
  > "$TMP/proxmox/_firewall.txt"
sysctl -a > "$TMP/proxmox/_sysctl.txt" 2>&1 || true
# опись видео-дисков: сами медиа не копируем (решение владельца), но фиксируем состав и объёмы
{
  for m in /mnt/video /mnt/ssd_src /mnt/*; do
    [ -d "$m" ] || continue
    echo "== $m"
    df -h "$m" 2>/dev/null | tail -1
    echo "файлов: $(find "$m" -type f 2>/dev/null | wc -l)"
    echo "размер: $(du -sh "$m" 2>/dev/null | cut -f1)"
    find "$m" -maxdepth 2 -type f 2>/dev/null | head -40
    echo
  done
} > "$TMP/proxmox/_video_disks.txt" 2>&1 || true

qm list > "$TMP/proxmox/_qm_list.txt" 2>&1 || true
pct list > "$TMP/proxmox/_pct_list.txt" 2>&1 || true
for id in $(qm list 2>/dev/null | awk 'NR>1 {print $1}'); do
  qm config "$id" > "$TMP/proxmox/_vm-$id-config.txt" 2>&1 || true
done
for id in $(pct list 2>/dev/null | awk 'NR>1 {print $1}'); do
  pct config "$id" > "$TMP/proxmox/_ct-$id-config.txt" 2>&1 || true
done

# ── 4. VM Postiz: compose, каталог с патчем, /etc гостя, дампы всех баз ─────────
if ssh -n -o BatchMode=yes -o ConnectTimeout=6 -o StrictHostKeyChecking=no "root@$VM_IP" true 2>/dev/null; then
  vm() { ssh -n "root@$VM_IP" "$1" 2>/dev/null; }

  vm 'cat /home/postiz/postiz/docker-compose.yml' > "$TMP/postiz/docker-compose.yml" || true
  # каталог целиком (compose + patch/Dockerfile, из которого собирается образ postiz-fixed);
  # скрытые каталоги исключаем — там кеш VSCode на гигабайт
  vm "tar -czf - --exclude='.*' --exclude='*/.*' -C /home postiz" > "$TMP/postiz/home-postiz.tgz" || true
  # конфигурация гостя: /etc (sshd, сеть, shadow), ключи, список пакетов
  vm 'tar -czf - -C / etc' > "$TMP/postiz/vm-etc.tar.gz" || true
  vm 'tar -czf - -C /root .ssh' > "$TMP/postiz/vm-root-ssh.tar.gz" || true
  vm "dpkg-query -W -f='\${Package}=\${Version}\\n'" > "$TMP/postiz/_packages.txt" || true
  vm "tar -czf - -C /usr/local bin sbin etc share" > "$TMP/postiz/vm-usr-local.tar.gz" || true
  vm 'docker --version; docker compose version; node --version; python3 --version; psql --version' \
    > "$TMP/postiz/_tools_versions.txt" || true
  vm 'crontab -l' > "$TMP/postiz/_root_crontab.txt" || true
  vm 'uname -a; echo; lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT; echo; ip -br a; echo; df -h' \
    > "$TMP/postiz/_system.txt" || true
  vm 'docker ps --format "{{.Names}} | {{.Image}} | {{.Status}}" | sort' > "$TMP/postiz/_containers.txt" || true
  vm 'docker images --format "{{.Repository}}:{{.Tag}} | {{.Size}}"' > "$TMP/postiz/_images.txt" || true
  vm 'docker volume ls --format "{{.Name}}"' > "$TMP/postiz/_volumes.txt" || true
  vm 'docker system df' > "$TMP/postiz/_disk_usage.txt" || true
  vm 'cd /home/postiz/postiz && docker compose config' > "$TMP/postiz/_compose_config.txt" || true
  vm 'ls -la /home/postiz /home/postiz/postiz /home/postiz/patch' > "$TMP/postiz/_listing.txt" || true
  vm 'cat /etc/docker/daemon.json' > "$TMP/postiz/_docker_daemon.txt" 2>/dev/null \
    && [ -s "$TMP/postiz/_docker_daemon.txt" ] \
    || echo "своего /etc/docker/daemon.json нет — docker с настройками по умолчанию" \
       > "$TMP/postiz/_docker_daemon.txt"
  # что именно НЕ попало в бэкап (медиа)
  vm 'du -sh /var/lib/docker/volumes/postiz_postiz_uploads 2>/dev/null; \
      find /var/lib/docker/volumes/postiz_postiz_uploads -type f 2>/dev/null | wc -l' \
    > "$TMP/postiz/_media_excluded.txt" || true

  # дампы: pg_dumpall = все базы Postiz и Temporal + роли и права
  # --clean --if-exists: восстановление можно повторять, не спотыкаясь о существующие базы
  if vm 'docker exec postiz-db pg_dumpall -U postiz --clean --if-exists' > "$TMP/postiz/postiz-all-databases.sql" 2>"$TMP/postiz/_db_dump_error.txt"; then
    gzip -f "$TMP/postiz/postiz-all-databases.sql"
    rm -f "$TMP/postiz/_db_dump_error.txt"
  else
    echo "дамп баз Postiz не сделан (см. _db_dump_error.txt)" >&2
    rm -f "$TMP/postiz/postiz-all-databases.sql"
  fi
else
  echo "VM Postiz ($VM_IP) недоступна с pve по ssh" > "$TMP/postiz/_unreachable.txt"
fi

# ── 4б. Личные файлы владельца (по флагу BACKUP_PERSONAL=1) ─────────────────────
if [ "${BACKUP_PERSONAL:-0}" = "1" ]; then
  mkdir -p "$TMP/personal"
  # код и база broll_downloader (venv на 26 МБ не нужен — ставится заново)
  [ -d /root/broll_downloader ] && tar -czf "$TMP/personal/broll_downloader.tgz" -C /root \
    --exclude='broll_downloader/venv' --exclude='__pycache__' broll_downloader 2>/dev/null || true
  # свои скрипты, дампы железа, сетевые бэкапы, история, старые конфиги — только мелкое
  ITEMS=""
  for f in apic.dat bgrt.dat dbg2.dat dbgp.dat dmar.dat dsdt.dat dsl.dsl ecdt.dat facp.dat \
           facs.dat fidt.dat fpdt.dat hpet.dat ss2.dsl ss5.dsl .forward .bash_history \
           check-lid-edp.sh fix-wifi-lan.sh install-zenbook-lid-display.sh \
           network-backup-final-20260811-153828 network-final-20260811-211046 \
           network-backup-safe-20260811-154920; do
    [ -e "/root/$f" ] && ITEMS="$ITEMS $f"
  done
  ITEMS="$ITEMS $(cd /root && ls config.yaml.bak-* 2>/dev/null | tr '\n' ' ')"
  [ -n "${ITEMS// /}" ] && tar -czf "$TMP/personal/root-files.tgz" -C /root $ITEMS 2>/dev/null || true
  # на VM — только служебные мелочи вроде pm2, без кешей и докера
  ssh -n -o BatchMode=yes -o ConnectTimeout=6 "root@$VM_IP" 'tar -czf - -C /root .pm2 .bashrc .profile' \
    > "$TMP/personal/vm-root-misc.tgz" 2>/dev/null || true
  cat > "$TMP/personal/README.md" <<'EOF'
# Личные файлы владельца (раздел personal)

Здесь то, что не нужно для подъёма машины, но принадлежит владельцу:
- `broll_downloader.tgz` — его инструмент (код, `broll.db`, `status.txt`; виртуальное окружение не входит);
- `root-files.tgz` — свои скрипты (`fix-wifi-lan.sh`, `install-zenbook-lid-display.sh`, `check-lid-edp.sh`),
  дампы железа (`dsdt.dat`, `ss*.dsl` и прочие `.dat`), сетевые бэкапы от 11.08, `.bash_history`,
  старые копии `config.yaml`;
- `vm-root-misc.tgz` — служебные мелочи с VM Postiz (`.pm2`, `.bashrc`, `.profile`).

Не вошли: `legacy-logs` (51 МБ логов), старые архивы отката оркестратора (37 МБ),
копии серверных бэкапов (327 МБ — они и так лежат на Mac), кеши (`.cache` 21 МБ, venv 26 МБ).
EOF
  du -sh "$TMP/personal" > "$TMP/personal/_size.txt" 2>&1 || true
fi

# ── 4в. Скрипты восстановления и бинарник cloudflared ───────────────────────────
if [ -d /tmp/restore-kit ]; then
  mkdir -p "$TMP/restore"
  cp -a /tmp/restore-kit/. "$TMP/restore/"
  chmod +x "$TMP/restore"/*.sh 2>/dev/null || true
  echo "restore/ — скрипты восстановления (см. restore/README.md)" > "$TMP/restore/_from_repo.txt"
fi
if [ "${BACKUP_WITH_BINARY:-1}" = "1" ] && [ -x /usr/local/bin/cloudflared ]; then
  cp -a /usr/local/bin/cloudflared "$TMP/proxmox/cloudflared-linux-amd64" 2>/dev/null || true
fi
if ssh -n -o BatchMode=yes -o ConnectTimeout=6 "root@$VM_IP" true 2>/dev/null; then
  ssh -n "root@$VM_IP" 'cat /etc/os-release' > "$TMP/postiz/_os_release.txt" 2>/dev/null || true
fi

# ── 5. Инструкция по восстановлению — внутрь архива ─────────────────────────────
cat > "$TMP/RESTORE.md" <<'EOF'
# Восстановление машины с нуля по этому архиву

## Короткий путь (скриптами, без ручной работы)
```bash
tar -xzf orch-server-*.tar.gz && cd orch-server-*
bash restore/host.sh .            # хост Proxmox
bash restore/vm-create.sh .       # если VM Postiz потеряна
bash restore/vm-data.sh .         # содержимое VM: docker, каталог, compose, базы, образ
bash restore/app.sh .             # наш оркестратор
bash restore/checks.sh .          # проверка: всё ли живо
```
Подробности — в `restore/README.md`. Ниже тот же порядок по шагам, если что-то надо сделать руками.

Архив содержит только конфигурацию: медиа, кеши и образы ПО намеренно не входят —
они восстанавливаются сами (медиа пересоздаётся публикациями, образ собирается из патча).

## 1. Хост Proxmox
1. Поставить Proxmox VE той же версии, что в `proxmox/_pveversion.txt`.
2. Восстановить конфигурацию: `tar -xzf proxmox/host-etc.tar.gz -C /` (это весь `/etc`),
   затем `tar -xzf proxmox/pve-etc.tar.gz -C /etc` (конфиги VM/CT, пользователи PVE).
3. Ключи root: `tar -xzf proxmox/root-ssh.tar.gz -C /root`.
4. Пакеты строго по версиям из `proxmox/_packages.txt`:
   `dpkg --set-selections < _packages.txt` не подходит (там версии) — ставить через
   `apt-get install $(sed 's/=/=/;s/$//' proxmox/_packages.txt)` либо выборочно нужные пакеты.
   Свои программы из `/usr/local` — `tar -xzf proxmox/usr-local.tar.gz -C /usr/local`
   (в том числе `cloudflared_url_sync.sh`); версия cloudflared — в `proxmox/_tools_versions.txt`.
5. Диски и сеть — по `_block_devices.txt`, `_storage_layout.txt`, `_network.txt`,
   `_firewall.txt`, `_sysctl.txt`.
6. Включённые сервисы и таймеры — `systemd/_enabled.txt`, `systemd/_timers.txt`.

## 2. Виртуальная машина Postiz
1. Создать VM по конфигу `proxmox/_vm-120-config.txt` (4 ядра, 8 ГБ памяти, диск ~237 ГБ).
2. Поставить ОС, восстановить `/etc` из `postiz/vm-etc.tar.gz`, ключи из
   `postiz/vm-root-ssh.tar.gz`, `/usr/local` из `postiz/vm-usr-local.tar.gz`,
   пакеты — по `postiz/_packages.txt` (там версии), версии docker/node — `postiz/_tools_versions.txt`.
3. Установить Docker и docker compose.
4. Развернуть каталог: `tar -xzf postiz/home-postiz.tgz -C /home`.
5. Поднять сервисы: `cd /home/postiz/postiz && docker compose up -d`.
6. Восстановить базы (все базы Postiz и Temporal сразу):
   `gunzip -c postiz/postiz-all-databases.sql.gz | docker exec -i postiz-db psql -U postiz`.
7. Образ программы: `postiz-fixed` в интернете не публикуется, он собирается из патча —
   в каталоге `/home/postiz/patch`: `docker build -t postiz-fixed:v1.47.2 .`
   (база — `ghcr.io/gitroomhq/postiz-app:latest`; если compose тянет готовый образ,
   вернуть тег `postiz-fixed:v1.47.2` в `docker-compose.yml`).
8. Медиа: в бэкап не входит (`postiz/_media_excluded.txt` — что именно исключено, там же размер).
   Подключения к каналам и их токены лежат в базе, поэтому после восстановления баз они вернутся.

## 3. Наш оркестратор
1. Скопировать `orchestrator/config.yaml` и `orchestrator/.env` в `/opt/orchestrator/`,
   `orchestrator/data/` — в `/opt/orchestrator/data/`, сертификаты — в `certs/`.
2. Код: `tar -xzf orchestrator/source.tar.gz -C /opt/orchestrator` (полный снимок каталога),
   зависимости — по `orchestrator/_pip_freeze.txt`.
3. Диски с видео: оркестратор следит за `/mnt/video` и `/mnt/ssd_src` — их надо смонтировать
   (см. `/etc/fstab` в `proxmox/host-etc.tar.gz` и `proxmox/_block_devices.txt`). Содержимое этих
   дисков в бэкап не входит, но состав и объёмы записаны в `proxmox/_video_disks.txt`.
4. Если в архиве есть `personal/` — это личные файлы владельца (см. `personal/README.md`),
   они к работе системы не относятся; разложить по желанию.
5. Сервисы: юниты из `systemd/` → в `/etc/systemd/system/` (в юните `User=orchestrator`,
   `PYTHONPATH=/opt/orchestrator/src`, рабочая папка `/opt/orchestrator`),
   затем `systemctl daemon-reload && systemctl enable --now orchestrator cloudflared-webapp`.
6. Проверка: `systemctl is-active orchestrator`, панель на `http://127.0.0.1:8080`.
EOF

# ── 6. Архив, контрольная сумма, ротация ────────────────────────────────────────
tar -czf "$OUT/$NAME.tar.gz" -C /tmp "$NAME"
( cd "$OUT" && sha256sum "$NAME.tar.gz" > "$NAME.tar.gz.sha256" )
rm -rf "$TMP"

# месячная копия: первый архив месяца остаётся надолго (12 штук)
MONTHLY_DIR="$OUT/monthly"
mkdir -p "$MONTHLY_DIR"
MONTH_TAG="$(date +%Y-%m)"
if [ ! -f "$MONTHLY_DIR/orch-server-$MONTH_TAG.tar.gz" ]; then
  cp -a "$OUT/$NAME.tar.gz" "$MONTHLY_DIR/orch-server-$MONTH_TAG.tar.gz"
  ( cd "$MONTHLY_DIR" && sha256sum "orch-server-$MONTH_TAG.tar.gz" > "orch-server-$MONTH_TAG.tar.gz.sha256" )
fi
ls -1t "$MONTHLY_DIR"/orch-server-*.tar.gz 2>/dev/null | tail -n +$((MONTHLY_KEEP + 1)) | xargs -r rm -f
ls -1t "$MONTHLY_DIR"/orch-server-*.tar.gz.sha256 2>/dev/null | tail -n +$((MONTHLY_KEEP + 1)) | xargs -r rm -f

ls -1t "$OUT"/orch-server-*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
ls -1t "$OUT"/orch-server-*.tar.gz.sha256 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
du -h "$OUT/$NAME.tar.gz" | cut -f1
