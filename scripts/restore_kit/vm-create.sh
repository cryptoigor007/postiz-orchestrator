#!/usr/bin/env bash
# ШАГ 2а. Создание VM Postiz с нуля (нужен, только если VM потеряна).
#
# Запуск на хосте:  bash restore/vm-create.sh <каталог_распакованного_архива> [IP]
# Параметры: VMID=120, IP=192.168.100.60, GW=192.168.100.1, BRIDGE=vmbr0,
#            STORAGE=local-lvm, DISK=240 — можно переопределить переменными.
#
# Ядра, память и имя берутся из сохранённого конфига VM (proxmox/_vm-120-config.txt),
# образ системы — официальный Ubuntu cloud image (скачивается автоматически).

set -euo pipefail

SRC="${1:?укажи каталог распакованного архива}"
VMID="${VMID:-120}"
IP="${2:-192.168.100.60}"
GW="${GW:-192.168.100.1}"
BRIDGE="${BRIDGE:-vmbr0}"
STORAGE="${STORAGE:-local-lvm}"
DISK="${DISK:-240}"
CFG="$SRC/proxmox/_vm-$VMID-config.txt"
IMG="${IMG:-/var/lib/vz/template/iso/ubuntu-cloudimg-amd64.img}"
IMG_URL="https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"

CORES="$(awk '/^cores:/{print $2}' "$CFG" 2>/dev/null || echo 4)"
MEM="$(awk '/^memory:/{print $2}' "$CFG" 2>/dev/null || echo 8192)"
NAME="$(awk '/^name:/{print $2}' "$CFG" 2>/dev/null || echo postiz)"

if qm status "$VMID" >/dev/null 2>&1; then
  echo "VM $VMID уже существует — создавать не нужно (шаг vm-create пропущен)"
  exit 0
fi

echo "1/5 образ системы"
[ -f "$IMG" ] || { echo "  качаю Ubuntu cloud image"; curl -fL --progress-bar -o "$IMG" "$IMG_URL"; }

echo "2/5 создаю VM $VMID ($NAME: $CORES ядра, $MEM МБ, диск ${DISK}G, сеть $BRIDGE)"
qm create "$VMID" --name "$NAME" --cores "$CORES" --memory "$MEM" \
  --scsihw virtio-scsi-single --net0 "virtio,bridge=$BRIDGE" \
  --serial0 socket --vga serial0 --agent enabled=1 --onboot 1

echo "3/5 диск"
qm importdisk "$VMID" "$IMG" "$STORAGE" >/dev/null
qm set "$VMID" --scsi0 "$STORAGE:vm-$VMID-disk-0,discard=on,iothread=1"
qm resize "$VMID" scsi0 "${DISK}G" || true
qm set "$VMID" --ide2 "$STORAGE:cloudinit" --boot order=scsi0

echo "4/5 сеть и доступ по ключу"
[ -f /root/.ssh/authorized_keys ] || { echo "  нет /root/.ssh/authorized_keys — восстанови ключи (шаг 1)"; exit 1; }
qm set "$VMID" --ipconfig0 "ip=$IP/24,gw=$GW" --ciuser root --sshkeys /root/.ssh/authorized_keys
qm start "$VMID"

echo "5/5 жду загрузку и ssh (до 5 минут)"
for _ in $(seq 1 60); do
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=3 "root@$IP" true 2>/dev/null && break
  sleep 5
done
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "root@$IP" 'cloud-init status --wait >/dev/null 2>&1 || true; uname -a' || true

echo
echo "ГОТОВО (VM создана). Дальше: bash restore/vm-data.sh $SRC $IP"
