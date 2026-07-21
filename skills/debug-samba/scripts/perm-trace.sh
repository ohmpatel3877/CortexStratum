#!/usr/bin/env bash
# perm-trace.sh — Full Permission Trace Across NAS Stack
# ========================================================
# Traces permissions from a file through POSIX → SMB → mergerfs → Container
#
# Usage: bash perm-trace.sh /path/to/file [smb-user]
#
set -Eeuo pipefail

FILE="${1:-}"
SMB_USER="${2:-smbuser}"

if [ -z "$FILE" ]; then
  echo "Usage: $0 /path/to/file [smb-user]"
  exit 1
fi

echo "╔══════════════════════════════════════════════════╗"
echo "║  Permission Trace                                ║"
echo "║  File: $FILE"
echo "╚══════════════════════════════════════════════════╝"

echo ""
echo "1. POSIX Permission Chain"
echo "-------------------------"
namei -l "$FILE" 2>/dev/null || ls -la "$FILE"

echo ""
echo "2. ACLs"
echo "-------"
getfacl "$FILE" 2>/dev/null || echo "  (no ACL support)"

echo ""
echo "3. Owner/Group Details"
echo "----------------------"
STAT=$(stat -c '%U %G %a %s' "$FILE" 2>/dev/null) || STAT=$(stat -f '%Su %Sg %Lp %z' "$FILE" 2>/dev/null)
echo "  $STAT"

echo ""
echo "4. Samba User Mapping"
echo "---------------------"
if command -v pdbedit &>/dev/null; then
  pdbedit -L 2>/dev/null | head -20 || echo "  (no Samba users)"
  echo ""
  if id "$SMB_USER" &>/dev/null; then
    echo "  System user '$SMB_USER': $(id $SMB_USER)"
  else
    echo "  System user '$SMB_USER' not found"
  fi
else
  echo "  (pdbedit not installed)"
fi

echo ""
echo "5. mergerfs Branch"
echo "------------------"
getfattr -n user.mergerfs.branch "$FILE" 2>/dev/null || echo "  (not mergerfs or no xattr)"

echo ""
echo "6. Podman Container Access"
echo "--------------------------"
if command -v podman &>/dev/null; then
  for c in $(podman ps --format '{{.Names}}' 2>/dev/null); do
    mounts=$(podman inspect "$c" 2>/dev/null | python3 -c "
import json, sys
try:
  data = json.load(sys.stdin)
  for m in data[0].get('Mounts', []):
    src = m.get('Source', '')
    dest = m.get('Destination', '')
    if '$FILE'.startswith(src):
      print(f'  {c}: {src} → {dest}')
except: pass
" 2>/dev/null) || true
    [ -n "$mounts" ] && echo "$mounts"
  done
else
  echo "  (podman not available)"
fi

echo ""
echo "7. Filesystem Type & Features"
echo "-----------------------------"
df -T "$FILE" 2>/dev/null | tail -1 | awk '{print "  Type: "$2}'
mount | grep -E "$(df "$FILE" 2>/dev/null | tail -1 | awk '{print $1}')" 2>/dev/null | head -1 || true

echo ""
echo "╠═══ PERMISSION DIAGNOSIS ═══╣"

# Detect common issues
if [ -r "$FILE" ]; then
  echo "   World-readable"
else
  echo "   NOT world-readable — check group/other permissions"
fi

OWNER=$(stat -c '%u' "$FILE" 2>/dev/null || stat -f '%u' "$FILE" 2>/dev/null)
SMB_UID=$(id "$SMB_USER" 2>/dev/null | grep -oP 'uid=\K[0-9]+' || echo "")
if [ -n "$SMB_UID" ] && [ "$OWNER" != "$SMB_UID" ]; then
  echo "   File owner ($OWNER) ≠ SMB user ($SMB_USER/$SMB_UID)"
  echo "    Fix: chown $SMB_USER '$FILE'"
fi
