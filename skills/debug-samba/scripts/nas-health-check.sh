#!/usr/bin/env bash
# nas-health-check.sh — Full NAS Stack Layer Status
# ==================================================
# Dumps health of all layers: storage → shares → containers → apps
# Usage: sudo bash nas-health-check.sh [mergerfs-mount-path]
#
set -Eeuo pipefail

MOUNT="${1:-/mnt/mergerfs}"
echo "========================================"
echo " NAS Stack Health Check — $(date -Iseconds)"
echo "========================================"

# ─── LAYER 0: Hardware ──────────────────────────────────────────
echo ""
echo "=== HARDWARE ==="
echo "CPU: $(nproc --all) cores"
echo "RAM: $(free -h | awk '/^Mem:/ {print $2}') total, $(free -h | awk '/^Mem:/ {print $7}') available"
echo "Swap: $(free -h | awk '/^Swap:/ {print $3}') used"
echo "Disks:"
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE 2>/dev/null | grep -v loop || true

# ─── LAYER 1: Storage (Physical) ────────────────────────────────
echo ""
echo "=== STORAGE — Physical ==="
df -h --type=ext4 --type=btrfs --type=xfs 2>/dev/null || df -h | grep -E '(/dev/)' | head -10
echo ""
echo "SMART status:"
for d in /dev/sd[a-z] /dev/nvme[0-9]n[0-9]; do
  [ -e "$d" ] || continue
  sudo smartctl -H "$d" 2>/dev/null | grep -E '(SMART overall-health|SMART Health Status|PASSED|FAILED)' && echo "  $d: OK" || echo "  $d: (no SMART data)"
done 2>/dev/null

# ─── LAYER 2: Storage (mergerfs / FUSE) ─────────────────────────
echo ""
echo "=== STORAGE — mergerfs/FUSE ==="
if mount | grep -q "mergerfs"; then
  echo "mergerfs is mounted:"
  mount | grep mergerfs
  echo ""
  echo "mergerfs branches (via xattr):"
  getfattr -d "$MOUNT" 2>/dev/null | grep "user.mergerfs" || echo "  (xattrs unavailable — is mergerfs xattr passthrough enabled?)"
  echo ""
  echo "FUSE operation queue:"
  for f in /sys/fs/fuse/connections/*/waiting; do
    [ -r "$f" ] && echo "  $f: $(cat $f)"
  done 2>/dev/null || echo "  (no FUSE sysfs entries)"
else
  echo "  ✗ mergerfs NOT mounted"
fi

# ─── LAYER 3: Shares (Samba) ────────────────────────────────────
echo ""
echo "=== SHARES — Samba ==="
if command -v smbstatus &>/dev/null; then
  echo "smbd status:"
  systemctl is-active smbd 2>/dev/null && echo "  active" || echo "  inactive"
  echo ""
  echo "Active connections:"
  smbstatus -S 2>/dev/null | head -20 || echo "  (none)"
  echo ""
  echo "Config validation:"
  testparm -s -q 2>/dev/null && echo "  smb.conf: valid" || echo "  smb.conf: INVALID"
  echo ""
  echo "Listeners:"
  ss -tlnp 2>/dev/null | grep -E '445|139' || echo "  ✗ Not listening on 445/139"
else
  echo "  ✗ smbstatus not installed"
fi

# ─── LAYER 4: Containers (Podman) ───────────────────────────────
echo ""
echo "=== CONTAINERS — Podman ==="
if command -v podman &>/dev/null; then
  echo "Podman version: $(podman version 2>/dev/null | grep 'Version' | head -1)"
  echo ""
  echo "Running containers:"
  podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  (none)"
  echo ""
  echo "All containers:"
  podman ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null
  echo ""
  echo "Networks:"
  podman network ls 2>/dev/null
else
  echo "  ✗ podman not installed"
fi

# ─── LAYER 5: Applications ──────────────────────────────────────
echo ""
echo "=== APPLICATION HEALTH ==="

# Jellyfin
if curl -so /dev/null -w "%{http_code}" http://localhost:8096 2>/dev/null | grep -q 200; then
  echo "  ✓ Jellyfin (port 8096)"
else
  echo "  ○ Jellyfin not responding on :8096"
fi

# Nextcloud (check common ports)
for port in 80 443 8080 4443; do
  if curl -so /dev/null -w "%{http_code}" "http://localhost:$port" 2>/dev/null | grep -qE '200|302|401'; then
    echo "  ✓ Nextcloud/web on :$port"
    break
  fi
done || echo "  ○ No web service detected on common ports"

# ─── LAYER 6: Log Errors ────────────────────────────────────────
echo ""
echo "=== RECENT LOG ERRORS ==="
echo "--- Samba errors (last 20 lines) ---"
journalctl -u smbd -n 20 --no-pager 2>/dev/null | grep -iE 'error|fail|denied' | tail -5 || echo "  (none)"
echo ""
echo "--- Podman errors (last 20 lines) ---"
journalctl --user -xeu podman -n 20 --no-pager 2>/dev/null | grep -iE 'error|fail|denied' | tail -5 || journalctl -xeu podman -n 20 --no-pager 2>/dev/null | grep -iE 'error|fail|denied' | tail -5 || echo "  (none)"
echo ""
echo "--- Kernel/FUSE errors ---"
dmesg 2>/dev/null | grep -iE 'fuse|mergerfs|i/o error' | tail -5 || echo "  (none)"

echo ""
echo "========================================"
echo " Health Check Complete"
echo "========================================"
