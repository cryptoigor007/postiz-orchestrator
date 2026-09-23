# Безопасность сервера pve — что закрыто и как откатить

Выполнено по плану владельца (msg 248). Скрипт-повторитель: `scripts/harden_host.sh`
(идемпотентный, можно запускать после восстановления сервера).

## Сделано
1. **Панель слушает только `127.0.0.1:8080`** (`ORCH_HTTP_BIND=127.0.0.1` в `/opt/orchestrator/.env`).
   Публичный адрес через cloudflared продолжает работать — туннель ходит к панели локально.
   Проверено: `http(s)://<cloudflared>/webapp/...` отдаёт 200, API — 200.
   **Что изменилось для владельца:** прямой адрес `http://100.95.225.71:8080` больше не открывается;
   панель доступна по публичной ссылке (её же использует Telegram Mini App) или через ssh-туннель.
2. **SSH: только по ключам** (`/etc/ssh/sshd_config.d/99-orchestrator-hardening.conf`):
   `PermitRootLogin prohibit-password`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`.
   Проверено: `sshd -T` показывает `permitrootlogin without-password`, `passwordauthentication no`.
3. **Samba ограничена внутренней сетью**: в `[global]` добавлено
   `hosts allow = 127.0.0.1 192.168.100.0/24` и `hosts deny = 0.0.0.0/0`.
   Шару `[video]` (`/mnt/video`) использует видеомейкер с `192.168.100.3` — ему по-прежнему можно.
   Проверено: с внутреннего адреса шары видны, с внешнего (Tailscale) — отказ
   (`NT_STATUS_INVALID_NETWORK_RESPONSE`); сессия видеомейкера не разорвана.
4. **rpcbind выключен** (`rpcbind.socket`/`rpcbind.service`): NFS на сервере нет, Samba в режиме
   `ROLE_STANDALONE` без него работает. Проверено: Samba и winbind активны, шары отдаются.

## Осталось как есть (и почему)
- **`pveproxy` (8006) и `spiceproxy` (3128)** — это веб-интерфейс и консоль Proxmox, ими владелец
  управляет виртуальными машинами. Закрывать их = отказаться от управления ВМ через браузер.
  Если нужно — можно ограничить их сетевым экраном (только Tailscale/LAN), это отдельная задача.
- **`sshd` (22)** — слушает, но вход теперь только по ключу.

## Откат
```bash
# панель обратно наружу (не рекомендуется)
ssh root@100.95.225.71 "sed -i '/^ORCH_HTTP_BIND=/d' /opt/orchestrator/.env && systemctl restart orchestrator"

# ssh обратно (не рекомендуется)
ssh root@100.95.225.71 "rm /etc/ssh/sshd_config.d/99-orchestrator-hardening.conf && systemctl reload ssh"

# samba — снять ограничение
ssh root@100.95.225.71 "sed -i '/hosts allow = 127.0.0.1/d;/hosts deny = 0.0.0.0/d' /etc/samba/smb.conf && systemctl reload smbd"

# rpcbind — вернуть
ssh root@100.95.225.71 "systemctl enable --now rpcbind.socket rpcbind.service"
```
Копии конфигов до правки: `/etc/samba/smb.conf.bak-<дата>`. Все эти файлы попадают в ночной бэкап
(`orch-backup.timer`), поэтому после восстановления сервера достаточно запустить `scripts/harden_host.sh`.

## Проверка «наружу» (что видно снаружи сейчас)
`22` (sshd, только ключи), `139/445` (Samba, только внутренняя сеть), `8006` (pveproxy — управление ВМ),
`3128` (spiceproxy — консоль ВМ), остальное — локально или Tailscale.
