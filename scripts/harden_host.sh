#!/usr/bin/env bash
# Ужесточение безопасности pve (по плану владельца). Идемпотентно, с проверками.
#
# Что делает:
#   1) панель оркестратора слушает только 127.0.0.1 (публичный адрес через cloudflared не страдает:
#      туннель ходит локально);
#   2) ssh: вход root только по ключу, пароль выключен;
#   3) Samba: шару [video] (её использует видеомейкер 192.168.100.3) пускаем только внутреннюю сеть;
#   4) rpcbind выключаем — NFS на сервере нет, Samba работает без него.
#
# Что НЕ трогает и почему: pveproxy (8006) и spiceproxy (3128) — это управление ВМ в Proxmox,
# они нужны владельцу; закрывать их можно только вместе с отказом от веб-интерфейса Proxmox.
#
# Откат: см. docs/SECURITY.md
#
# Запуск с Mac: PVE_HOST=root@100.95.225.71 bash scripts/harden_host.sh

set -euo pipefail

PVE_HOST="${PVE_HOST:-root@100.95.225.71}"

ssh -o BatchMode=yes "$PVE_HOST" "bash -s" <<'REMOTE'
set -euo pipefail

# 1) панель — только локально
if [ -f /opt/orchestrator/.env ]; then
  sed -i "/^ORCH_HTTP_BIND=/d" /opt/orchestrator/.env
  printf "ORCH_HTTP_BIND=127.0.0.1\n" >> /opt/orchestrator/.env
fi

# 2) ssh — только ключи
install -d -m 755 /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/99-orchestrator-hardening.conf <<'EOF'
# Ужесточение по плану владельца: вход root только по ключу, пароли выключены.
PermitRootLogin prohibit-password
PasswordAuthentication no
KbdInteractiveAuthentication no
EOF
sshd -t

# 3) Samba — только внутренняя сеть (шара для видеомейкера остаётся)
if ! grep -q "hosts allow = 127.0.0.1 192.168.100.0/24" /etc/samba/smb.conf; then
  cp -a /etc/samba/smb.conf "/etc/samba/smb.conf.bak-$(date +%F)"
  sed -i "/^\[global\]/a \\\thosts allow = 127.0.0.1 192.168.100.0/24\n\\thosts deny = 0.0.0.0/0" /etc/samba/smb.conf
fi
testparm -s >/dev/null

# 4) rpcbind не нужен
systemctl disable --now rpcbind.socket rpcbind.service >/dev/null 2>&1 || true

systemctl daemon-reload
systemctl restart orchestrator.service
systemctl reload ssh
systemctl reload smbd 2>/dev/null || systemctl restart smbd
sleep 4

echo -n "оркестратор: "; systemctl is-active orchestrator.service
echo -n "health локально: "; curl -sf --max-time 5 http://127.0.0.1:8080/health >/dev/null && echo ok || echo ПРОБЛЕМА
echo -n "sshd: "; sshd -T 2>/dev/null | grep -E "^(permitrootlogin|passwordauthentication)" | tr '\n' ' '; echo
echo -n "samba: "; systemctl is-active smbd nmbd winbind | tr '\n' ' '; echo
echo -n "rpcbind: "; systemctl is-active rpcbind.service 2>/dev/null || echo "выключен"
echo "порты наружу: $(ss -tlnp | grep -vE '127.0.0.1|\[::1\]' | awk '{print $4}' | sort -u | tr '\n' ' ')"
REMOTE
