#!/usr/bin/env bash
# VM Test Engine — Linux Quick Provision (QEMU/KVM)
# Usage: ./vm-test.sh --provider qemu --os ubuntu-server --name test-vm

set -Eeuo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}▶${NC} $1"; }
ok()    { echo -e "${GREEN}✓${NC} $1"; }
fail()  { echo -e "${RED}✗${NC} $1"; exit 1; }

PROVIDER=""
OS=""
NAME="test-vm-$(date +%s)"
MEMORY=4096
CORES=2

while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider) PROVIDER="$2"; shift 2 ;;
    --os) OS="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --memory) MEMORY="$2"; shift 2 ;;
    --cores) CORES="$2"; shift 2 ;;
    --destroy) DESTROY=1; shift ;;
    --help) echo "Usage: $0 --provider [qemu|vagrant] --os [ubuntu|debian] --name <name>"; exit 0 ;;
    *) fail "Unknown option: $1" ;;
  esac
done

check_deps() {
  for cmd in qemu-img qemu-system-x86_64 cloud-localds; do
    command -v "$cmd" >/dev/null 2>&1 || fail "Missing: $cmd. Install qemu-utils and cloud-image-utils."
  done
}

create_cloudinit() {
  local seed="/tmp/${NAME}-seed.img"
  cat > /tmp/cloud-init.yaml << YAML
#cloud-config
hostname: ${NAME}
users:
  - name: tester
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - $(cat ~/.ssh/id_rsa.pub 2>/dev/null || echo "ssh-rsa AAAAB3...your-key-here")
packages:
  - docker.io
  - git
  - curl
runcmd:
  - systemctl start docker
  - echo "VM ready for testing"
YAML
  cloud-localds "$seed" /tmp/cloud-init.yaml
  echo "$seed"
}

create_qemu_vm() {
  local img="/var/lib/libvirt/images/${NAME}.qcow2"
  local seed
  seed=$(create_cloudinit)

  info "Creating QEMU VM: ${NAME}"

  # Download Ubuntu cloud image if not present
  local cloud_img="/var/lib/libvirt/images/ubuntu-24.04-server-cloudimg-amd64.img"
  if [ ! -f "$cloud_img" ]; then
    info "Downloading Ubuntu cloud image..."
    sudo mkdir -p /var/lib/libvirt/images
    sudo wget -q "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img" -O "$cloud_img"
    sudo qemu-img resize "$cloud_img" 40G
  fi

  # Create VM with qemu directly (no libvirt needed)
  sudo qemu-img create -f qcow2 -b "$cloud_img" -F qcow2 "$img" 40G

  ok "VM image created: ${img}"
  info "Starting VM (connect with: ssh tester@localhost -p 2222)..."
  
  sudo qemu-system-x86_64 \
    -machine q35,accel=kvm \
    -cpu host \
    -smp "${CORES}" \
    -m "${MEMORY}" \
    -drive file="${img}",format=qcow2,if=virtio \
    -drive file="${seed}",format=raw,if=virtio \
    -netdev user,id=net0,hostfwd=tcp::2222-:22 \
    -device virtio-net,netdev=net0 \
    -nographic \
    -pidfile "/tmp/${NAME}.pid" &
  
  ok "VM started (PID: $(cat /tmp/${NAME}.pid 2>/dev/null || echo 'unknown'))"
}

case "$PROVIDER" in
  qemu)
    check_deps
    if [ "${DESTROY:-0}" = "1" ]; then
      sudo kill "$(cat /tmp/${NAME}.pid 2>/dev/null)" 2>/dev/null || true
      sudo rm -f "/var/lib/libvirt/images/${NAME}.qcow2" "/tmp/${NAME}-seed.img" "/tmp/${NAME}.pid"
      ok "VM ${NAME} destroyed"
    else
      create_qemu_vm
    fi
    ;;
  vagrant)
    if [ "${DESTROY:-0}" = "1" ]; then
      vagrant destroy -f
    else
      vagrant init "${OS:-ubuntu/jammy64}" 2>/dev/null || vagrant init
      vagrant up
    fi
    ;;
  *)
    fail "Provider required: --provider [qemu|vagrant]"
    ;;
esac
