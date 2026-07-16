---
name: debug-samba
description: Master debugging of Samba, mergerfs, Podman container NAS, Jellyfin, Nextcloud, and merged NAS storage setups. Covers cross-service interaction troubleshooting, filesystem layering, container networking, media serving, and cloud sync diagnostics. Use when Samba shares are unreachable, mergerfs has split-brain or policy issues, Podman containers can't network, Jellyfin transcoding fails, Nextcloud sync breaks, or any home/enterprise NAS stack needs deep diagnostics.
---

# Debug Samba — NAS & Self-Hosted Service Debugging

Systematic debugging skill for home-lab and production NAS stacks built on **Samba + mergerfs + Podman + Jellyfin + Nextcloud** and their integration points. Treats the stack as a layered system: filesystem → network → container → application → client, and isolates failures layer by layer.

## When to Use This Skill

- Samba shares unreachable or permission-denied (network, auth, or POSIX issues)
- mergerfs shows wrong files, missing files, or branch-selection weirdness
- Podman containers can't reach each other or the outside network
- Jellyfin won't transcode, scan libraries, or play media
- Nextcloud sync fails, hangs, or shows "internal server error"
- Cross-service issues: Samba serving mergerfs mounts that Podman containers write to, consumed by Jellyfin/Nextcloud
- Performance problems in multi-layered storage (mergerfs + SnapRAID + Samba)
- Permission cascading failures across containers → FUSE mounts → network shares

## Architecture Overview — The Stack Layers

```
┌─────────────────────────────────────────────┐
│  Client Layer                                │
│  (Windows Explorer, macOS Finder,           │
│   Jellyfin App, Nextcloud Client, Kodi)     │
├─────────────────────────────────────────────┤
│  Application Layer                           │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │ Jellyfin │  │Nextcloud │  │ Other     │ │
│  │ (media)  │  │ (cloud)  │  │ Containers│ │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘ │
├───────┴──────────────┴──────────────┴───────┤
│  Container Layer (Podman/Docker)             │
│  ┌──────────────────────────────────────┐   │
│  │  Podman Networking (netavark/pasta)  │   │
│  │  Volume Mounts, Rootless Mapping     │   │
│  └────────────────┬─────────────────────┘   │
├───────────────────┴────────────────────────┤
│  Share Layer                                 │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │  Samba   │  │  NFS     │  │  SFTP     │ │
│  │  (CIFS)  │  │          │  │           │ │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘ │
├───────┴──────────────┴──────────────┴───────┤
│  Storage Layer                                │
│  ┌──────────────────────────────────────┐   │
│  │  mergerfs (union mount)              │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐  │   │
│  │  │ disk1  │ │ disk2  │ │ disk3  │  │   │
│  │  │(ext4)  │ │(ext4)  │ │(ext4)  │  │   │
│  │  └────────┘ └────────┘ └────────┘  │   │
│  │  Optional: SnapRAID parity below    │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### Common Failure Propagation Paths

| Symptom | Likely Root Layer | Cascades To |
|---------|-------------------|-------------|
| Samba "permission denied" | Storage (POSIX perms) | Share, Client |
| mergerfs shows stale listing | Storage (policy or cache) | All layers above |
| Podman container can't write | Container (user ns mapping) | Application, Share |
| Jellyfin infinite buffering | Application (transcoding) or Share (read speed) | Client |
| Nextcloud "internal server error" | Application (PHP/DB) or Storage (file locking) | Client |
| Cross-service file conflict | Share (locking/SMB lease) | Multiple apps |

---

## Diagnostic Methodology — Layer Isolation

Always isolate the failing layer before deep-diving:

```
1. CLIENT:   Can you reach the service? (ping, telnet, curl)
2. NETWORK:  Is the port open? (ss, netstat, firewall)
3. SERVICE:  Is the daemon running? (systemctl, podman ps)
4. FILESYSTEM: Can the service read/write its data path? (touch test)
5. PERMS:    Are ownership and mode correct? (ls -la, namei, getfacl)
6. CONFIG:   Is the config file valid? (testparm, nginx -t, podman inspect)
7. LOGS:     What does the log say? (journalctl, container logs, debug mode)
```

---

## 1. Samba (SMB/CIFS) Debugging

### 1.1 Quick Health Check

```bash
# Is smbd running?
systemctl status smbd          # or: smbstatus
smbstatus -S                   # show active connections and locked files

# Is smbd listening?
ss -tlnp | grep -E '(445|139)'

# Validate config
testparm -s                    # silent check, exits 0 if OK
testparm -v                    # verbose, shows all effective settings

# Test auth from local
smbclient -L localhost -N      # anonymous browse
smbclient -L localhost -U <user>  # authenticated browse

# Test remote
smbclient -L //<server-ip> -U <user>
```

### 1.2 Common Failures & Fixes

#### "Permission denied" on share

```bash
# 1. Check share definition in /etc/samba/smb.conf
[myshare]
  path = /pool/media
  valid users = @smbusers
  read only = no
  create mask = 0664
  directory mask = 0775
  force user = smbuser        # maps all SMB users to local uid
  force group = smbgroup

# 2. Check POSIX permissions on the actual path
ls -la /pool/media             # must be readable/writable by smbuser
namei -l /pool/media           # trace every parent dir's perms (all must have +x)

# 3. Check SELinux/AppArmor
getenforce                     # if Enforcing, check avc denials
ausearch -m avc -ts recent     # SELinux audit log
# Fix: restorecon -R /pool/media   or   semanage fcontext ...

# 4. Check that the SMB user exists AND maps to a system user
pdbedit -L                     # list Samba users
pdbedit -L -v <user>           # verbose (includes Unix uid/gid)
id <smbuser>                   # verify system user exists

# 5. Test write as the effective user
sudo -u smbuser touch /pool/media/test.tmp
```

#### Samba slow / high CPU

```bash
# Check for oplock / lease conflicts
smbstatus -L                   # list locked files
echo "111" | smbcontrol smbd close-share <sharename>  # force close

# Profile Samba
smbstatus -p                   # show process pool

# Check socket options in smb.conf
# socket options = TCP_NODELAY IPTOS_LOWDELAY
# min receivefile size = 16384

# Check if vfs modules are causing overhead
# Disable vfs objects temporarily for testing
```

#### Can't resolve NetBIOS name

```bash
# NMBD must be running
systemctl status nmbd

# Test NetBIOS resolution
nmblookup -S <hostname>        # query NetBIOS name
nmblookup -S <ip>              # reverse lookup

# Check WINS settings in smb.conf
# wins support = yes           # if this server is WINS server
# wins server = <ip>          # if using external WINS

# Check that firewall allows:
# UDP 137 (NetBIOS-ns), UDP 138 (NetBIOS-dgm), TCP 139 (NetBIOS-ssn), TCP 445 (SMB)
```

#### SMB Multichannel issues

```bash
# Verify multichannel is enabled
testparm -s | grep "server multi channel support"

# Check number of TCP connections per client
ss -tn | grep 445

# If you see only 1 connection per client despite multichannel:
# - Ensure client supports SMB 3.x+
# - Check all NICs are on same subnet
# - Check for firewall rules blocking secondary connections
```

### 1.3 Debug Logging

```ini
# In [global] section of /etc/samba/smb.conf:
log level = 3 auth:5
# Levels: 0=no logging, 1=default, 2=basic, 3=detailed, 4–10=debug
# Components: auth, smb, rpc, passdb, vfs, etc.
```

```bash
# Watch real-time Samba operations
journalctl -fu smbd
tail -f /var/log/samba/log.smbd
```

---

## 2. mergerfs Debugging

### 2.1 Quick Health Check

```bash
# Is mergerfs mounted?
mount | grep mergerfs
df -Th | grep fuse.mergerfs

# Show mergerfs version
mergerfs -v

# Show runtime settings (policies, options)
cat /sys/fs/fuse/connections/*/waiting  # check for stuck FUSE operations

# For mergerfs >= 2.38.x: xattr-based runtime control
getfattr -d /mnt/mergerfs                # show xattrs on mount root
getfattr -n user.mergerfs.branches /mnt/mergerfs  # show configured branches
```

### 2.2 Branch Configuration Debugging

```bash
# Show which branch a file lives on (critical for troubleshooting "wrong file" bugs)
# If using xattr passthrough:
getfattr -n user.mergerfs.branch /pool/media/movies/Movie.mkv

# Without xattrs, use path-based detection:
find /mnt/disk1 /mnt/disk2 /mnt/disk3 -path "*/movies/Movie.mkv" -exec ls -la {} \;
```

### 2.3 Policy Debugging

mergerfs policies control which branch is selected for file creation and read operations. This is the #1 source of "weird behavior."

```bash
# Check current policy (via xattr or mount options)
cat /etc/fstab | grep mergerfs
mount | grep mergerfs | grep -o 'category.create=[^,]*'
mount | grep mergerfs | grep -o 'category.search=[^,]*'

# Common policies and when they cause problems:
# ┌────────────────┬──────────────────────────────────────────┐
# │ Policy         │ Behavior & Failure Mode                   │
# ├────────────────┼──────────────────────────────────────────┤
# │ epmfs (default)│ Existing path, most free space. Can cause │
# │                │ files to scatter randomly across disks.   │
# │ lfs            │ Least free space. Fills one disk first.   │
# │ mfs            │ Most free space. Spreads writes out.      │
# │ rand           │ Random. Unpredictable test behavior.      │
# │ ff             │ First found. Creates on first writable    │
# │                │ branch.                                   │
# │ epff           │ Existing path, first found. Best for      │
# │                │ minimizing scatter — creates files on     │
# │                │ the same branch as the parent.            │
# └────────────────┴──────────────────────────────────────────┘

# Test: simulate what mergerfs will do
/usr/bin/mergerfs -o use_ino,category.create=epff,<other-opts> /mnt/disk1:/mnt/disk2 /mnt/merged
# Then check getfattr for branch path
```

### 2.4 "Missing File" Debugging

```bash
# If a file exists on a disk but isn't visible in mergerfs:
# 1. Check it's not hidden by higher-priority branch
stat /mnt/disk3/path/to/file    # confirm it exists
ls -la /mnt/merged/path/to/file # check visibility from mergerfs

# 2. If visible on disk but not through mergerfs, check for:
#    - RO branch listed before RW branch (mergerfs stops at first hit by default)
#    - FUSE writeback cache issues
#    - Mount options: `direct_io` vs `writeback_cache`

# 3. Force cache flush
echo 1 | sudo tee /proc/sys/vm/drop_caches  # drop kernel page cache
```

### 2.5 mergerfs + SnapRAID Integration

```bash
# Common symptom: files appear as 0-length or missing after SnapRAID sync
# Cause: SnapRAID modifies files directly on underlying disks
# Fix: Run `mergerfs.fsck` to reconcile

mergerfs.fsck /mnt/merged      # check for inconsistencies
mergerfs.ctl /mnt/merged       # runtime control interface

# Best practice: set SnapRAID content files on each disk, not through mergerfs
# SnapRAID should sync at block level on underlying disks
```

### 2.6 Performance Debugging

```bash
# Check FUSE operation queue
cat /sys/fs/fuse/connections/*/waiting
# If > 0 consistently, mergerfs is bottlenecked

# Benchmark individual disks vs mergerfs mount
dd if=/dev/zero of=/mnt/disk1/test bs=1M count=1024 oflag=direct
dd if=/dev/zero of=/mnt/merged/test bs=1M count=1024 oflag=direct

# Check if direct_io is enabled (adds overhead but necessary for some apps)
mount | grep mergerfs | grep -o 'direct_io'
```

---

## 3. Podman Container NAS Debugging

### 3.1 Quick Health Check

```bash
# Container status
podman ps -a
podman stats --no-stream
podman top <container> aux

# Network connectivity
podman exec <container> ping -c 3 8.8.8.8
podman exec <container> ping -c 3 <other-container-name>

# DNS resolution
podman exec <container> getent hosts google.com
podman exec <container> nslookup <other-container-name>

# Network info
podman network ls
podman network inspect <network>
podman inspect <container> --format '{{.NetworkSettings.IPAddress}}'
```

### 3.2 Rootless Container Issues

Rootless Podman is the #1 source of NAS permission headaches.

```bash
# Check user namespace mapping — CRITICAL for volume mounts
podman inspect <container> --format '{{.HostConfig.BindMounts}}'
podman unshare ls -la /path/to/mount  # view files as the container user

# Common failure: "Permission denied" writing to mounted volume
# Root cause: UID/GID mismatch between host and container user namespace

# Fix strategy:
# 1. Check the container user
podman exec <container> id

# 2. Check the host user mapping
podman unshare id

# 3. If mismatch, either:
#    a. Use --userns=keep-id when running
#    b. Set podman run --user <UID>:<GID>
#    c. Use podman create --userns=auto:size=65536
#    d. Reconcile host filesystem permissions: chown -R <UID>:<GID> /path/to/volume

# Verify mapping
cat /proc/self/uid_map
cat /proc/self/gid_map
```

### 3.3 Podman Networking Debugging

```bash
# Default rootless: pasta (NAT networking with no NAT — copies host IPs)
# Default rootful: netavark bridge (10.88.0.0/16)

# Check network backend
podman info | grep -E '(networkBackend|networkBackendPath)'

# If containers can't reach each other by name:
# 1. Verify they're on the same podman network
podman network ls
podman inspect <container> --format '{{.NetworkSettings.Networks}}'

# 2. Create a shared network
podman network create nas-network
podman run --network nas-network --name jellyfin ...
podman run --network nas-network --name nextcloud ...

# 3. Verify DNS-based service discovery
podman exec jellyfin ping nextcloud

# Port forwarding issues:
# Check that pasta/slirp4netns ports are correctly forwarded
ss -tlnp | grep <host-port>          # verify host is listening
podman port <container>              # list forwarded ports
podman logs <container> | grep -i port

# Firewall interference (firewalld / ufw)
sudo firewall-cmd --list-all
sudo iptables -L -n | grep podman
```

### 3.4 Volume Mounts — The NAS Nightmare

```bash
# Bind mount into container
podman run -v /pool/media:/media:z ...

# The :z and :Z flags are SELinux relabeling — CRITICAL if SELinux is Enforcing
# :z = shared across containers (most common for NAS)
# :Z = private to this container

# Debug volume mount issues:
podman inspect <container> | jq '.[0].Mounts'
podman exec <container> ls -la /media  # see what the container sees
podman exec <container> stat /media

# If /media is empty inside but has files on host:
# 1. Check SELinux context:
ls -Z /pool/media                  # should show container_file_t or svirt_sandbox_file_t
chcon -Rt container_file_t /pool/media   # fix SELinux label
# OR disable SELinux for container: --security-opt label=disable

# 2. Check that the FUSE mount (mergerfs) is propagatable
mount --bind /mnt/mergerfs /mnt/mergerfs   # ensure it's a proper mount point
podman run --rm -v /mnt/mergerfs:/media:shared alpine ls /media

# 3. For rootless: verify the user has access to the filesystem path
# mergerfs mounts owned by root won't be accessible to rootless containers
# Solution: use podman unshare to check, or run rootful containers
```

### 3.5 Podman+Systemd (Quadlet) Debugging

```bash
# Quadlet files live in:
# /etc/containers/systemd/ (system) or ~/.config/containers/systemd/ (user)

# Debug Quadlet-generated systemd units:
systemctl --user list-units | grep container
systemctl --user status <service>
journalctl --user -u <service>

# Common Quadlet issues:
# - File extension must be .container, .volume, .network, or .pod
# - Container name matching volume/network must be exact
# - After editing Quadlet files:
systemctl --user daemon-reload
```

### 3.6 Podman Secret Management

```bash
# If services can't authenticate (e.g., SMTP, DB):
podman secret ls
podman inspect <container> | jq '.[0].Secrets'

# Create secret
podman secret create mysecret /path/to/secret.txt

# Use in Quadlet:
# Secret=mysecret    (maps to /run/secrets/mysecret)
```

---

## 4. mergerfs + Podman Integration (Critical Edge Cases)

This is where most NAS failures live — FUSE mounts inside containers.

```bash
# PROBLEM: Container tries to stat/mount a path that goes through mergerfs
# mergerfs uses FUSE. Podman needs --security-opt to handle FUSE properly.

# Fix for rootful containers:
podman run --privileged ...                            # works but too broad
podman run --security-opt apparmor=unconfined ...      # if using AppArmor
podman run --security-opt seccomp=unconfined ...       # if seccomp blocks FUSE

# Better: add only the required syscalls
# --security-opt seccomp=/path/to/seccomp-fuse.json

# Fix for rootless containers:
# Rootless CANNOT mount FUSE filesystems inside the container.
# Instead, mount the mergerfs path BEFORE running the container:
mount /mnt/mergerfs                                  # mount on host
podman run -v /mnt/mergerfs:/media:rslave ...         # pass through bind mount

# If mergerfs is not yet mounted when podman starts (e.g., on boot):
# Use systemd mount ordering:
# [Unit]
# Requires=mergerfs.mount
# After=mergerfs.mount
# In the .container Quadlet file
```

### FUSE passthrough check

```bash
# Test if FUSE is accessible inside the container
podman run --rm -v /mnt/mergerfs:/data:rslave alpine:latest \
  sh -c "ls /data && touch /data/testwrite && rm /data/testwrite && echo FUSE_OK"
```

---

## 5. Jellyfin Debugging

### 5.1 Quick Health Check

```bash
# Service status
systemctl status jellyfin
podman ps | grep jellyfin

# Check if it's serving
curl -s http://localhost:8096 | head -5

# Library paths accessible?
ls -la /path/to/media              # on host
podman exec jellyfin ls -la /media # inside container (for containerized install)
```

### 5.2 Transcoding Diagnostics

```bash
# Check ffmpeg availability
podman exec jellyfin which ffmpeg
podman exec jellyfin ffmpeg -version

# VAAPI / hardware transcoding check (Intel QSV or AMD VAAPI)
podman exec jellyfin vainfo                   # VAAPI info
podman exec jellyfin ls -la /dev/dri          # render nodes

# If /dev/dri is empty inside container:
# --device /dev/dri:/dev/dri  (add to podman run)
# Or in Quadlet: Device=/dev/dri

# Transcoding log location (inside container):
podman exec jellyfin cat /config/logs/ffmpeg-transcode-*.log
# On host for native install: /var/log/jellyfin/ffmpeg-transcode-*.log

# Test transcode manually:
podman exec jellyfin ffmpeg -i /media/test.mkv \
  -c:v libx264 -preset fast -b:v 8M -c:a aac \
  -f mp4 /dev/null -y 2>&1 | tail -20

# Common failure: "Failed to decode" — corrupt media or codec not supported
```

### 5.3 Library Scanning Issues

```bash
# Force library scan via API
curl -X POST "http://localhost:8096/Library/Refresh" \
  -H "X-MediaBrowser-Token: <api-key>"

# Check scan logs for errors
podman exec jellyfin cat /config/logs/log_*.log | grep -i error

# Common library issues:
# 1. NFO files corrupted — delete them, rescan
# 2. File naming not matching Jellyfin conventions
#    Movie: /movies/Movie Name (2024)/Movie Name (2024).mkv
#    TV:   /tv/Show Name/Season 01/Show Name S01E01.mkv
# 3. Permissions — Jellyfin user must be able to read all files
```

### 5.4 Hardware Acceleration

```bash
# Intel QuickSync
# Required: /dev/dri render nodes passed to container
podman exec jellyfin ls /dev/dri/render*

# In Jellyfin dashboard:
# Playback → Transcoding → Hardware Acceleration: Intel QuickSync (QSV)

# Check VAAPI device is available:
podman exec jellyfin vainfo

# If VAAPI fails with "No available hardware decoder":
# - Install intel-media-va-driver (not i965) on host for modern Intel
# - For 12th-gen+: apt install intel-media-va-driver-non-free

# NVIDIA NVENC
podman run --device nvidia.com/gpu=all ...

# Check GPU is visible:
podman exec jellyfin nvidia-smi
```

### 5.5 Inotify Watch Limit (Large Libraries)

```bash
# If Jellyfin shows "Error in Directory watcher" or
# mergerfs + Jellyfin real-time monitoring fails:
# The limit is on the HOST, not the container

# Check current limit:
cat /proc/sys/fs/inotify/max_user_watches

# Increase:
echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.d/99-inotify.conf
sudo sysctl -p

# For Podman: inotify must be set on the HOST, not inside container
```

---

## 6. Nextcloud Debugging

### 6.1 Quick Health Check

```bash
# Web server (Apache/Nginx/Caddy)
systemctl status nginx
curl -sI http://localhost | grep -E '(HTTP|Server)'

# PHP-FPM
systemctl status php8.3-fpm
systemctl status php8.2-fpm

# Database
systemctl status postgresql    # or mariadb, mysql
psql -U nextcloud -d nextcloud -c "SELECT version();"

# Redis
redis-cli ping                 # should return PONG
```

### 6.2 Containerized Nextcloud (Podman)

```bash
# Check all containers
podman ps | grep -E '(nextcloud|redis|mariadb|postgres|db)'

# Network connectivity between containers
podman exec nextcloud ping redis
podman exec nextcloud ping database

# Check Nextcloud config for correct DB host
podman exec nextcloud occ config:system:get dbhost
podman exec nextcloud occ config:system:get dbname
podman exec nextcloud occ config:system:get dbuser

# Verify Redis is configured
podman exec nextcloud occ config:system:get memcache.local
podman exec nextcloud occ config:system:get redis host
```

### 6.3 Common Nextcloud Failures

#### "Internal Server Error" / 500

```bash
# 1. Check Nextcloud logs
podman exec nextcloud cat /var/www/html/data/nextcloud.log | jq '.'
# Or for bare-metal: tail /var/log/nextcloud/nextcloud.log

# 2. Check PHP error logs
podman exec nextcloud tail /var/log/php/error.log
# Or: journalctl -u php*-fpm

# 3. Check web server error logs
journalctl -u nginx | grep 'error'
tail /var/log/nginx/error.log

# 4. Run Nextcloud occ for diagnostics
podman exec --user www-data nextcloud php occ status
podman exec --user www-data nextcloud php occ check
podman exec --user www-data nextcloud php occ security:certificates
```

#### Sync fails / files not updating

```bash
# 1. Check file locking
podman exec nextcloud occ config:system:get filelocking.enabled
# Should be "true" if using Redis or DB for locking

# 2. Check if transactionallocking is set correctly
# If using Samba as filestore backing:
# filelocking.enabled must use Redis, NOT DB-based locking
# Redis: filelocking.enabled → true, memcache.locking → \OC\Memcache\Redis

# 3. Verify .ocdata marker exists
ls -la /path/to/nextcloud/data/<user>/files/.ocdata

# 4. Check for stale file locks (Redis)
redis-cli keys 'LOCK:*'
redis-cli -n 0 keys '*oc*'
```

#### Background jobs not running

```bash
# Check cron mode
podman exec nextcloud occ config:app:get core backgroundjobs_mode
# Should be "cron" for production

# If set to "cron", verify system cron or Kubernetes CronJob is running
# For Podman Quadlet:
systemctl --user list-timers | grep nextcloud
cat ~/.config/containers/systemd/nextcloud-cron.container

# Manual trigger for testing:
podman exec --user www-data nextcloud php cron.php
```

### 6.4 Performance & Caching

```bash
# Verify Redis/memcache is working
podman exec nextcloud occ memcache:increment "test" 1
redis-cli monitor &

# Check for slow queries
# PostgreSQL:
podman exec database psql -U nextcloud -c "
  SELECT query, calls, total_exec_time, rows
  FROM pg_stat_statements
  ORDER BY total_exec_time DESC LIMIT 10;"

# MySQL:
podman exec database mysql -e "SHOW FULL PROCESSLIST;" nextcloud

# Check Apache/PHP children
# If using PHP-FPM:
podman exec nextcloud ps aux | grep php-fpm
podman exec nextcloud cat /usr/local/etc/php-fpm.d/www.conf | grep pm.max_children
```

### 6.5 Nextcloud + mergerfs Integration

```bash
# PROBLEM: Nextcloud detects file changes via inotify + .ocdata marker.
# If the mergerfs policy causes a file to "move" between branches,
# Nextcloud sees it as deleted+recreated, not modified.

# Fix:
# 1. Use a creation policy that minimizes branch flip-flop:
#    category.create=epff (existing path, first found)
#    category.create=msp (most free space, existing path first)

# 2. Disable Nextcloud's filesystem integrity checks if mergerfs is swapping files
#    config.php: 'integrity.check.disabled' => true (use cautiously!)

# 3. For the data directory specifically, put it on a single disk
#    NOT through mergerfs — use a bind mount to a specific branch
```

---

## 7. Cross-Service Integration Debugging

### 7.1 Full-Stack Triage — The "File Disappeared" Case

When a file written through Samba on a mergerfs mount and served by Jellyfin/Nextcloud disappears:

```bash
# 1. Which layer lost it?
# Check Samba
smbstatus -L                    # any locks on it?

# Check mergerfs — find which branch
getfattr -n user.mergerfs.branch /mnt/merged/path/to/file 2>/dev/null

# Check disks directly
for d in /mnt/disk{1,2,3}; do
  find "$d" -path "*/path/to/file" 2>/dev/null && echo "Found on: $d"
done

# 2. Check SnapRAID if used
snapraid status                  # any mismatch?

# 3. Check if Podman volume mapping is wrong
podman inspect jellyfin | jq '.[0].Mounts[] | select(.Destination=="*/media*")'

# 4. Check Nextcloud filecache
podman exec nextcloud occ files:scan --path "/<user>/files/path"
podman exec nextcloud occ files:check-cache
```

### 7.2 Permission Cascade Debugging

```bash
# Full permission trace from client to disk:
# Client → Samba → HostFS → mergerfs → Physical Disk

# 1. SMB user mapping
pdbedit -L -v <smbuser>         # SMB → Unix user map
id <smbuser>                    # Unix user UID/GID

# 2. Samba force user
testparm -s | grep "force user"
testparm -s | grep "force group"

# 3. Filesystem ACLs for the share path
namei -l /pool/media            # trace perms up to root
getfacl /pool/media             # ACLs including default
getfacl /pool/media/movies

# 4. mergerfs branch perms
for d in /mnt/disk{1,2,3}; do
  echo "=== $d ==="
  getfacl "$d/media/movies" 2>/dev/null
done

# 5. Podman volume mapping (if writing from container)
podman exec jellyfin id         # uid inside container
# Map to: podman inspect jellyfin | jq '.[0].HostConfig.BindMounts'
```

### 7.3 Performance Cascades — "Why is my stream buffering?"

```bash
# Systematic bandwidth check:
# 1. HDD read speed (direct)
hdparm -t /dev/sda

# 2. mergerfs read speed
dd if=/mnt/mergerfs/media/test.bin of=/dev/null bs=1M count=1024

# 3. Samba read speed (from another machine)
# On Windows client:
# robocopy \\server\share\test.bin NUL /E /NJH /NJS

# 4. Network bottleneck
iperf3 -c <server-ip>           # server: iperf3 -s

# 5. Container overhead
podman exec jellyfin iperf3 -c <other-container>

# 6. Transcoding bottleneck
# If CPU is pegged: htop | grep ffmpeg
# If IO wait high: iostat -x 1 5
# If direct IO: check Samba strict locking / oplocks
```

---

## 8. Diagnostic Scripts

Reference implementations in `scripts/` directory (one level up from this SKILL.md).

### 8.1 NAS-Health-Check Script

```bash
#!/bin/bash
# nas-health-check.sh — dump all NAS stack layer status in one pass
set -Eeuo pipefail

echo "=== STORAGE ==="
df -h | grep -E '(mergerfs|/mnt/disk|/pool)'
mount | grep -E '(mergerfs|fuse)'
echo "mergerfs branches:"
getfattr -d /mnt/mergerfs 2>/dev/null | grep branch || echo "  (no xattr)"
echo "disk health:"
for d in /dev/sd[a-z]; do
  sudo smartctl -H "$d" 2>/dev/null | grep -E '(SMART|PASSED|FAILED)' || true
done

echo "=== SHARES ==="
smbstatus -S 2>/dev/null || echo "  smbd not running"
testparm -s -q && echo "  smb.conf: valid" || echo "  smb.conf: INVALID"

echo "=== CONTAINERS ==="
podman ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
podman network ls

echo "=== JELLYFIN ==="
curl -so /dev/null -w "  HTTP %{http_code}\n" http://localhost:8096 || echo "  Jellyfin not responding"

echo "=== NEXTCLOUD ==="
curl -so /dev/null -w "  HTTP %{http_code}\n" http://localhost || echo "  Nextcloud not responding"

echo "=== LOG ERRORS (last 50 lines) ==="
journalctl -u smbd -n 10 --no-pager 2>/dev/null | grep -i error || true
journalctl --user -xeu podman -n 10 --no-pager 2>/dev/null | grep -i error || true
```

### 8.2 FUSE → Podman Compatibility Check

```bash
#!/bin/bash
# fuse-podman-check.sh — verify mergerfs is accessible from Podman

MERGERFS_MOUNT="${1:-/mnt/mergerfs}"
TEST_FILE=".fuse_test_$(date +%s)"

echo "=== FUSE → Podman Compatibility Check ==="
echo "mergerfs mount: $MERGERFS_MOUNT"

# 1. Direct write test
echo -n "1. Direct write: "
touch "$MERGERFS_MOUNT/$TEST_FILE" 2>/dev/null && echo "OK" || echo "FAIL"

# 2. Podman rootful
echo -n "2. Podman (rootful) write: "
sudo podman run --rm -v "$MERGERFS_MOUNT:/data:z" alpine touch "/data/$TEST_FILE" 2>/dev/null && echo "OK" || echo "FAIL"

# 3. Podman rootless (current user)
echo -n "3. Podman (rootless) write: "
podman run --rm -v "$MERGERFS_MOUNT:/data:U" alpine touch "/data/$TEST_FILE" 2>/dev/null && echo "OK" || echo "FAIL"

# 4. Podman rootless + keep-id
echo -n "4. Podman (rootless+keep-id) write: "
podman run --rm --userns=keep-id -v "$MERGERFS_MOUNT:/data:U" alpine touch "/data/$TEST_FILE" 2>/dev/null && echo "OK" || echo "FAIL"

# Cleanup all test files
find "$MERGERFS_MOUNT" -name ".fuse_test_*" -delete 2>/dev/null
echo "=== Done ==="
```

### 8.3 Cross-Service Permission Trace

```bash
#!/bin/bash
# perm-trace.sh — trace permissions across the full stack

FILE="${1:-.}"
SMB_USER="${2:-smbuser}"

echo "=== Full Permission Trace for: $FILE ==="
echo ""

echo "--- POSIX Trace ---"
namei -l "$FILE"

echo ""
echo "--- ACLs ---"
getfacl "$FILE" 2>/dev/null || echo "  (no ACL support)"

echo ""
echo "--- Samba User Mapping ---"
id "$SMB_USER" 2>/dev/null && pdbedit -L -v "$SMB_USER" 2>/dev/null | grep -E '(Unix|NT)' || echo "  smbuser not found"

echo ""
echo "--- mergerfs Branch ---"
getfattr -n user.mergerfs.branch "$FILE" 2>/dev/null || echo "  (not under mergerfs or xattrs unavailable)"

echo ""
echo "--- Container Access ---"
CONTAINERS=$(podman ps --format '{{.Names}}')
for c in $CONTAINERS; do
  podman inspect "$c" 2>/dev/null | jq --arg f "$FILE" '.[0].Mounts[] | select(.Source == $f or (.Source | IN($f)))' 2>/dev/null || true
done
```

---

## 9. Mem0 Learning Integration

After resolving each failure type, store the signature and fix:

```bash
# Store the resolved case pattern in your memory:
# /mem0-add type=resolved_bugs
#   error_signature="FUSE: mergerfs + rootless podman permission denied"
#   root_cause="UID namespace mismatch in --userns mapping"
#   resolution="Use --userns=keep-id or chown files to container user UID"
#   tags=["nas","mergerfs","podman","rootless"]
```

### Failure Signatures to Register

| Error Pattern | Register As |
|--------------|-------------|
| `smbstatus shows locked file on mergerfs` | `anti_pattern: smb+mergerfs stale lock` |
| `Jellyfin can't find /dev/dri in container` | `anti_pattern: missing device passthrough` |
| `Nextcloud: "File not found" after mergerfs write` | `anti_pattern: mergerfs branch flip causing stateless` |
| `Podman rootless "permission denied" on bind mount` | `anti_pattern: rootless UID mismatch` |
| `Samba "NT_STATUS_ACCESS_DENIED" with correct credentials` | `anti_pattern: SMB permission vs POSIX ACL conflict` |

---

## 10. Tool Reference

| Tool | Purpose | Key Flags |
|------|---------|-----------|
| `smbstatus` | Samba connection & lock status | `-S` (shares), `-L` (locks), `-p` (process pool) |
| `testparm` | Validate smb.conf | `-s` (silent), `-v` (verbose) |
| `nmblookup` | NetBIOS name resolution | `-S` (by name), `-A` (by IP) |
| `podman inspect` | Deep container metadata | `--format '{{.Mounts}}'`, `{{.NetworkSettings}}` |
| `podman unshare` | Check container user perspective | (no flags — run as current user) |
| `podman network` | Network management | `ls`, `inspect`, `create`, `reload` |
| `getfattr` | Read mergerfs branch xattr | `-n user.mergerfs.branch` |
| `mergerfs.ctl` | Runtime mergerfs control | (mount path) |
| `mergerfs.fsck` | Check mergerfs consistency | (mount path) |
| `jq` | Parse container JSON | `.Mounts`, `.NetworkSettings` |
| `occ` | Nextcloud CLI | `status`, `check`, `files:scan` |
| `redis-cli` | Redis/Nextcloud cache | `monitor`, `keys`, `ping` |

---

## Quick-Start: 5-Minute Triage

When a NAS user says "X isn't working," run this in order:

```bash
# 1. Layer 0 — Storage
df -h | grep -E '(mergerfs|disk|pool)'          # any full?
mount | grep mergerfs && echo "mergerfs OK"      # FUSE up?
cat /sys/fs/fuse/connections/*/waiting           # any stuck ops?

# 2. Layer 1 — Shares
systemctl is-active smbd && echo "smbd OK"
smbstatus -S | head -10                          # active connections?

# 3. Layer 2 — Containers
podman ps --format "table {{.Names}}\t{{.Status}}"
podman healthcheck run <failing-container>       # if defined

# 4. Layer 3 — Applications
curl -so /dev/null -w "Jellyfin: %{http_code}\n" http://localhost:8096
curl -so /dev/null -w "Nextcloud: %{http_code}\n" http://localhost

# 5. Layer 4 — Logs
journalctl -u smbd -n 10 --no-pager | grep -i error
podman logs --tail 10 <container> | grep -i error
```
