#!/usr/bin/env bash
# fuse-podman-check.sh — Verify mergerfs FUSE is accessible from Podman
# =====================================================================
# Tests write access through mergerfs → Podman in rootful, rootless, 
# and with --userns=keep-id configurations.
#
# Usage: bash fuse-podman-check.sh [/mnt/mergerfs]
#
set -Eeuo pipefail

MERGERFS_MOUNT="${1:-/mnt/mergerfs}"
TAG=".fuse_test_$(date +%s)"

echo "╔══════════════════════════════════════════════════╗"
echo "║  FUSE → Podman Compatibility Check              ║"
echo "║  Mount: $MERGERFS_MOUNT"
echo "╚══════════════════════════════════════════════════╝"

# Prerequisites
for cmd in podman mount; do
  command -v "$cmd" >/dev/null 2>&1 || { echo " $cmd required"; exit 1; }
done

if ! mountpoint -q "$MERGERFS_MOUNT"; then
  echo " $MERGERFS_MOUNT is not a mount point"
  exit 1
fi

cleanup() {
  find "$MERGERFS_MOUNT" -name ".fuse_test_*" -delete 2>/dev/null || true
}
trap cleanup EXIT

PASS=0
FAIL=0

check() {
  local label="$1"
  shift
  echo -n "  $label ... "
  if "$@" 2>/dev/null; then
    echo ""
    ((PASS++))
  else
    echo ""
    ((FAIL++))
  fi
}

echo ""
echo "1. Host-level tests:"
echo "-------------------"
check "Direct write" touch "$MERGERFS_MOUNT/$TAG.host"
check "Direct read" ls -la "$MERGERFS_MOUNT/$TAG.host"
check "Direct delete" rm "$MERGERFS_MOUNT/$TAG.host"

echo ""
echo "2. Rootful Podman:"
echo "------------------"
check "Sudo write" sudo podman run --rm \
  -v "$MERGERFS_MOUNT:/data:z" \
  alpine touch "/data/$TAG.rootful"
check "Sudo read" sudo podman run --rm \
  -v "$MERGERFS_MOUNT:/data:z" \
  alpine ls "/data/$TAG.rootful"
check "Sudo delete" sudo podman run --rm \
  -v "$MERGERFS_MOUNT:/data:z" \
  alpine rm "/data/$TAG.rootful"

echo ""
echo "3. Rootless Podman (default):"
echo "-----------------------------"
check "Write (default)" podman run --rm \
  -v "$MERGERFS_MOUNT:/data:U" \
  alpine touch "/data/$TAG.rootless" 2>&1 || echo "      (expected to fail on strict FUSE)"
# Don't fail the whole test — rootless + FUSE is the known problem
rm -f "$MERGERFS_MOUNT/$TAG.rootless" 2>/dev/null || true

echo ""
echo "4. Rootless Podman (--userns=keep-id):"
echo "--------------------------------------"
check "Write (keep-id)" podman run --rm \
  --userns=keep-id \
  -v "$MERGERFS_MOUNT:/data:U" \
  alpine touch "/data/$TAG.keepid"
check "Read (keep-id)" podman run --rm \
  --userns=keep-id \
  -v "$MERGERFS_MOUNT:/data:U" \
  alpine ls "/data/$TAG.keepid"
check "Delete (keep-id)" podman run --rm \
  --userns=keep-id \
  -v "$MERGERFS_MOUNT:/data:U" \
  alpine rm "/data/$TAG.keepid"

echo ""
echo "5. SELinux check:"
echo "-----------------"
if command -v getenforce &>/dev/null; then
  echo "  SELinux: $(getenforce)"
  if [ "$(getenforce)" = "Enforcing" ]; then
    echo "  SELinux contexts on mount:"
    ls -Z "$MERGERFS_MOUNT" 2>/dev/null | head -3 || echo "  (cannot read)"
    echo ""
    echo "  Tip: If :z flag gives errors, try:"
    echo "    sudo chcon -Rt container_file_t $MERGERFS_MOUNT"
  fi
else
  echo "  (not available)"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Results: $PASS passed, $FAIL failed"
echo "╚══════════════════════════════════════════════════╝"

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "Troubleshooting:"
  echo "  - Rootless + FUSE: Use --userns=keep-id -v ...:U"
  echo "  - SELinux: Add :z flag to volume mount"
  echo "  - Permissions: sudo chown -R \$USER:\$USER $MERGERFS_MOUNT"
  exit 1
fi
