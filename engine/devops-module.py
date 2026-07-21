#!/usr/bin/env python3
"""
DevOps/Container Module — AI DevOps expert for Podman, Docker, permissions,
Samba, mergerfs, networking, and containerized development workflows.

Architecture:
  Each function is a pure handler: dict in -> dict out.
  Pure Python stdlib only — no external API calls, no dependencies beyond stdlib.
  Registered as MCP tools via tools-mcp-server.py. Accessible via /devops command.
"""

import json
import re
from datetime import datetime, timezone

# ===========================================================================
# Embedded Knowledge Base
# ===========================================================================

PODMAN_VS_DOCKER = {
    "podman": {
        "architecture": "Daemonless, rootless by default, forks for each container",
        "daemon": "None — no background daemon required",
        "rootless": "Native — maps container UID 0 to host user UID via subuid/subgid",
        "compose": "Use podman-compose (pip install podman-compose) or podman play kube",
        "socket": "Optional: podman.socket for Docker API compatibility",
        "systemd": "podman generate systemd for native service units",
        "selinux": "Requires :Z or :z suffix on volume mounts for relabeling",
        "macos_windows": "podman machine init / start (VM-based)",
        "uid_mapping": "--userns=keep-id preserves host UID inside container",
        "networking": "Rootless uses slirp4netns or pasta; podman network create for custom",
    },
    "docker": {
        "architecture": "Client-server — dockerd daemon manages all containers",
        "daemon": "dockerd runs as root, socket at /var/run/docker.sock",
        "rootless": "Experimental rootless mode (dockerd-rootless-setuptool.sh)",
        "compose": "docker compose (v2 plugin, built-in)",
        "socket": "/var/run/docker.sock — group membership = root access",
        "systemd": "dockerd runs as systemd service",
        "selinux": "Generally relabels automatically; :z/:Z still supported",
        "macos_windows": "Docker Desktop (VM-based with GUI)",
        "uid_mapping": "--user UID:GID for user switching inside container",
        "networking": "bridge driver by default; overlay for Swarm",
    },
}

USERNS_MAPPING_KNOWLEDGE = {
    "subuid_format": "username:start_uid:range (e.g., ohmpa:100000:65536)",
    "subgid_format": "username:start_gid:range (e.g., ohmpa:100000:65536)",
    "mapping_rule": "Container UID N -> Host UID (subuid_start + N)",
    "podman_unshare": "Enter user namespace shell for debugging mounts/permissions",
    "common_commands": {
        "check_subuid": "cat /etc/subuid | grep $USER",
        "check_subgid": "cat /etc/subgid | grep $USER",
        "check_current_uid": "id -u",
        "check_newuidmap": "which newuidmap && ls -la $(which newuidmap)",
        "verify_mapping": "podman unshare cat /proc/self/uid_map",
    },
    "common_issues": {
        "volume_permission_denied": "Host files owned by UID different from container user",
        "subuid_not_configured": "Run: sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER",
        "newuidmap_missing": "Install uidmap package: sudo apt install uidmap (Debian/Ubuntu) or shadow-utils (RHEL)",
        "rootless_port_binding": "Ports < 1024 need auth or kernel tuning: sysctl net.ipv4.ip_unprivileged_port_start=80",
    },
}

SAMBA_KNOWLEDGE = {
    "smb_protocols": {
        "SMB1": "Deprecated, disabled by default since Samba 4.11 (ntlm auth = disabled)",
        "SMB2": "Minimum recommended, introduced with Samba 4.1",
        "SMB2_02": "Windows 8 / Server 2012 dialect",
        "SMB3": "Default in Samba 4.3+, supports encryption and multichannel",
        "SMB3_11": "Windows 10 / Server 2016+, preauth integrity, AES-256-GCM",
    },
    "vfs_objects": {
        "acl_xattr": "Extended ACL support stored in xattrs",
        "streams_xattr": "NTFS alternate data streams stored in xattrs",
        "fruit": "Enhanced macOS interoperability (Time Machine, resource forks)",
        "recycle": "Deleted files moved to .recycle directory per share",
        "shadow_copy2": "Expose ZFS/LVM snapshots as Previous Versions",
        "full_audit": "Log all SMB operations for auditing",
        "crossrename": "Allow server-side rename across directories",
        "catia": "Character mapping for macOS incompatible filenames",
    },
    "permission_model": {
        "create_mask": "Default: 0744 — permissions for new files",
        "directory_mask": "Default: 0755 — permissions for new directories",
        "force_user": "Force all file operations as a specific Unix user",
        "valid_users": "Comma-separated list of allowed users/groups",
        "inherit_permissions": "New files inherit parent directory permissions",
    },
    "macos_specific": {
        "vfs_fruit": "Enables Time Machine support, resource forks, Finder info",
        "veto_files": "Hide .DS_Store, ._* files: veto files = /.DS_Store/._*/.Trashes/",
        "spotlight": "Enable Spotlight searching: spotlight = yes (requires Tracker)",
        "ea_support": "Extended attribute support required for macOS: ea support = yes",
    },
}

MERGERFS_KNOWLEDGE = {
    "policies": {
        "epmfs": "Existing Path, Most Free Space — creates on drive with most free space where path already exists (default, best for media servers)",
        "ff": "First Found — returns first match; good for read-only archives",
        "newest": "Newest — picks file with most recent mtime",
        "mfs": "Most Free Space — creates on drive with most free space",
        "lfs": "Least Free Space — creates on drive with least free space; fill-em-up",
        "rand": "Random — pseudorandomly selects a branch",
        "epff": "Existing Path, First Found — existing path else first found",
        "eplfs": "Existing Path, Least Free Space",
    },
    "key_options": {
        "defaults": "allow_other,use_ino,cache.files=partial,dropcacheonclose=true,category.create=mfs",
        "minfreespace": "Minimum free space before branch is considered full (e.g., 10G, 50G)",
        "category.create": "Policy override for file creation only (e.g., mfs, lfs, rand)",
        "category.search": "Policy override for file search only (e.g., ff)",
        "cache.files": "Enable kernel dentry/inode caching: off, partial, full, auto",
        "dropcacheonclose": "Drop cached entries when file is closed (reduces stale cache with NFS/Samba)",
        "func.getattr": "Which branch used for stat/lookup: ff, newest",
        "func.symlink": "If target is outside pool, create relative symlink: true, false",
    },
    "common_setups": {
        "snapraid": "mergerfs pool on top of data disks + SnapRAID parity disk(s)",
        "media_server": "Pool across multiple drives, accessed by Plex/Jellyfin/Docker",
        "fstab_entry": "/mnt/disk* /mnt/pool fuse.mergerfs defaults,allow_other,use_ino,cache.files=partial,dropcacheonclose=true,category.create=mfs 0 0",
        "systemd_mount": "Create /etc/systemd/system/mnt-pool.mount with Type=fuse.mergerfs",
    },
}

CONTAINER_NETWORKING = {
    "docker_networks": {
        "bridge": "Default: NAT + port forwarding; containers communicate via docker0 bridge",
        "host": "Container shares host network namespace (no isolation)",
        "overlay": "Multi-host networking for Swarm; uses VXLAN",
        "macvlan": "Container gets own MAC, appears as physical device on LAN",
        "ipvlan": "Like macvlan but shares MAC; better for promiscuous-mode restrictions",
        "none": "No networking; container isolated",
    },
    "podman_networks": {
        "default": "Rootless: slirp4netns or pasta (NAT, no bridge); Root: CNI bridge",
        "pasta": "User-mode NAT, faster than slirp4netns, supports IPv6, default in Podman 5+",
        "bridge": "podman network create mynet then --network mynet",
        "host": "Same as Docker — best performance, no isolation",
    },
    "common_fixes": {
        "dns_failure": "Check /etc/resolv.conf inside container; try --dns 1.1.1.1",
        "port_conflict": "lsof -i :PORT or ss -tlnp | grep PORT",
        "container_cannot_reach_host": "Use host.docker.internal (Docker) or host.containers.internal (Podman)",
        "host_cannot_reach_container": "Check port publishing (-p HOST:CONTAINER) and firewall",
        "slow_dns": "Disable systemd-resolved stub listener or use --dns 8.8.8.8",
    },
}


# ===========================================================================
# Tool 1: devops_container_debug
# ===========================================================================


def container_debug(
    error_log: str, runtime: str = "podman", context: str = "standalone"
) -> dict:
    """
    Diagnose container issues from error logs.
    """
    error_log_lower = error_log.lower()
    diagnosis = []
    root_cause = ""
    solutions = []
    related_issues = []

    if runtime not in ("podman", "docker"):
        runtime = "podman"

    patterns = {
        "permission denied": {
            "root_cause": "UID/GID mismatch between container user and host file owner",
            "diagnosis": "Container process does not have permission to access the file or directory. In rootless containers, the container UID is mapped to a subuid range on the host.",
            "solutions": [
                {
                    "fix": "Use --userns=keep-id to map host UID into container",
                    "command": f"{runtime} run --userns=keep-id -v /host/path:/container/path ...",
                    "risk": "safe",
                },
                {
                    "fix": "Add :Z SELinux label to volume mount",
                    "command": f"{runtime} run -v /host/path:/container/path:Z ...",
                    "risk": "moderate",
                },
                {
                    "fix": "Chown the host directory to the container UID",
                    "command": "sudo chown -R CONTAINER_UID:CONTAINER_GID /host/path",
                    "risk": "safe",
                },
                {
                    "fix": "Run container as root (not recommended for production)",
                    "command": f"{runtime} run --user root ...",
                    "risk": "breaking",
                },
            ],
        },
        "cannot connect to daemon": {
            "root_cause": "Docker daemon not running or socket inaccessible",
            "diagnosis": "The Docker CLI cannot reach the Docker daemon socket. The dockerd process may not be running, or the user may not have permission to access /var/run/docker.sock.",
            "solutions": [
                {
                    "fix": "Start the Docker daemon",
                    "command": "sudo systemctl start docker && sudo systemctl enable docker",
                    "risk": "safe",
                },
                {
                    "fix": "Add user to docker group",
                    "command": "sudo usermod -aG docker $USER && newgrp docker",
                    "risk": "safe",
                },
                {
                    "fix": "Check daemon socket permissions",
                    "command": "ls -la /var/run/docker.sock",
                    "risk": "safe",
                },
                {
                    "fix": "Use podman instead (no daemon needed)",
                    "command": "alias docker=podman",
                    "risk": "safe",
                },
            ],
        },
        "no space left on device": {
            "root_cause": "Disk full or inode exhaustion — check overlay/container storage",
            "diagnosis": "Docker/Podman storage driver (overlay2) has run out of space. Check disk usage and prune unused images/volumes.",
            "solutions": [
                {
                    "fix": "Prune unused containers, images, and volumes",
                    "command": f"{runtime} system prune -a --volumes -f",
                    "risk": "breaking",
                },
                {
                    "fix": "Check overlay/container storage usage",
                    "command": f"{runtime} system df",
                    "risk": "safe",
                },
                {
                    "fix": "Check host disk usage",
                    "command": "df -h /var/lib/docker 2>/dev/null || df -h ~/.local/share/containers",
                    "risk": "safe",
                },
            ],
        },
        "port is already allocated": {
            "root_cause": "Port conflict — another process or container is using the port",
            "diagnosis": "The requested host port is already bound by another process or container.",
            "solutions": [
                {
                    "fix": "Find the process using the port",
                    "command": "lsof -i :PORT 2>/dev/null || ss -tlnp | grep :PORT",
                    "risk": "safe",
                },
                {
                    "fix": "Remove the conflicting container",
                    "command": f"{runtime} rm -f CONTAINER_NAME",
                    "risk": "breaking",
                },
                {
                    "fix": "Use a different host port",
                    "command": f"{runtime} run -p ALTERNATE_PORT:CONTAINER_PORT ...",
                    "risk": "safe",
                },
            ],
        },
        "no matching manifest": {
            "root_cause": "Platform architecture mismatch (e.g., pulling amd64 image on arm64)",
            "diagnosis": "The container image does not support the host CPU architecture.",
            "solutions": [
                {
                    "fix": "Specify architecture explicitly",
                    "command": f"{runtime} pull --platform linux/arm64 IMAGE",
                    "risk": "safe",
                },
                {
                    "fix": "Use emulation (QEMU) for cross-platform",
                    "command": "docker run --platform linux/amd64 ... (requires QEMU binfmt)",
                    "risk": "moderate",
                },
            ],
        },
        "exec format error": {
            "root_cause": "Binary architecture mismatch between image and host CPU",
            "diagnosis": "Trying to run an amd64 binary on arm64 or vice versa without emulation.",
            "solutions": [
                {
                    "fix": "Enable QEMU binfmt multi-platform support",
                    "command": "docker run --privileged --rm tonistiigi/binfmt --install all",
                    "risk": "safe",
                },
                {
                    "fix": "Build multi-arch image",
                    "command": "docker buildx build --platform linux/amd64,linux/arm64 ...",
                    "risk": "safe",
                },
            ],
        },
        "container name already in use": {
            "root_cause": "A container with the chosen name already exists (stopped or running)",
            "diagnosis": "Container names must be unique. Remove the old container or use a different name.",
            "solutions": [
                {
                    "fix": "Remove the old container",
                    "command": f"{runtime} rm CONTAINER_NAME",
                    "risk": "breaking",
                },
                {
                    "fix": "Auto-remove on exit",
                    "command": f"{runtime} run --rm --name CONTAINER_NAME ...",
                    "risk": "safe",
                },
            ],
        },
        "unknown flag": {
            "fix": "Check runtime compatibility — some flags are Docker-specific (e.g., --gpus requires nvidia-container-toolkit). Podman equivalents may differ.",
            "command": f"{runtime} --help | grep -i FLAG",
            "risk": "safe",
        },
        "oci runtime error": {
            "root_cause": "Container runtime (runc/crun) encountered a low-level error",
            "diagnosis": "The OCI runtime failed to create/start the container. Common causes: missing cgroups v2, AppArmor/SELinux blocking, or kernel incompatibility.",
            "solutions": [
                {
                    "fix": "Check cgroups version",
                    "command": "stat -fc %T /sys/fs/cgroup/ && mount | grep cgroup",
                    "risk": "safe",
                },
                {
                    "fix": "Try a different runtime",
                    "command": f"{runtime} run --runtime crun ...  (or --runtime runc)",
                    "risk": "moderate",
                },
                {
                    "fix": "Check kernel logs",
                    "command": "sudo dmesg | tail -50",
                    "risk": "safe",
                },
            ],
        },
        "unauthorized": {
            "root_cause": "Registry authentication failed or image requires login",
            "diagnosis": "The container registry requires credentials. Login or check that the image exists.",
            "solutions": [
                {
                    "fix": "Login to the registry",
                    "command": f"{runtime} login REGISTRY_URL",
                    "risk": "safe",
                },
                {
                    "fix": "Check image exists and is spelled correctly",
                    "command": f"{runtime} search IMAGE_NAME",
                    "risk": "safe",
                },
            ],
        },
    }

    matched = False
    for pattern_key, info in patterns.items():
        if pattern_key in error_log_lower:
            matched = True
            diagnosis.append(info.get("diagnosis", ""))
            root_cause = info.get("root_cause", "")
            if isinstance(info, dict):
                solutions.extend(info.get("solutions", []))
                if "related_issues" in info:
                    related_issues.extend(info["related_issues"])

    if not matched:
        if (
            "error" in error_log_lower
            or "failed" in error_log_lower
            or "exit code" in error_log_lower
        ):
            guess_rc = "Unknown container error — review the log for the specific error message"
            guess_sol = [
                {
                    "fix": "Get container logs for more details",
                    "command": f"{runtime} logs CONTAINER_ID",
                    "risk": "safe",
                },
                {
                    "fix": "Inspect the container state",
                    "command": f"{runtime} inspect CONTAINER_ID",
                    "risk": "safe",
                },
                {
                    "fix": "Check container exit code",
                    "command": f"{runtime} ps -a --filter 'status=exited'",
                    "risk": "safe",
                },
            ]
        else:
            guess_rc = "Unable to determine root cause from the log — check the full container output"
            guess_sol = [
                {
                    "fix": "Run container with verbose/debug logging",
                    "command": f"{runtime} run --log-level debug ...",
                    "risk": "safe",
                },
            ]
        root_cause = guess_rc
        solutions = guess_sol

    runtime_tips = []
    if runtime == "podman":
        runtime_tips = [
            "Podman is daemonless — no dockerd required",
            "Rootless mode: check /etc/subuid and /etc/subgid for UID mappings",
            "Use podman machine on macOS/Windows for VM setup",
        ]
    elif runtime == "docker":
        runtime_tips = [
            "Ensure dockerd is running: sudo systemctl status docker",
            "docker group membership needed for non-root usage",
            "Docker Desktop on macOS/Windows manages the VM automatically",
        ]

    if context == "compose":
        compose_tip = "Check compose logs: docker compose logs SERVICE_NAME"
        related_issues.append(compose_tip)
    elif context == "kubernetes":
        kube_tip = "For K8s: kubectl describe pod POD_NAME | kubectl logs POD_NAME"
        related_issues.append(kube_tip)
    elif context == "ci":
        ci_tip = "CI tip: Ensure docker/socket is available in the runner and the service container started"
        related_issues.append(ci_tip)

    return {
        "diagnosis": "\n".join(diagnosis)
        or "No specific pattern matched — review raw error output",
        "root_cause": root_cause,
        "solutions": solutions,
        "related_issues": related_issues,
        "runtime_tips": runtime_tips,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


# ===========================================================================
# Tool 2: devops_permissions_analyze
# ===========================================================================


def permissions_analyze(
    mount_path: str,
    container_user: str = "",
    host_user: str = "",
    error_symptom: str = "permission_denied",
) -> dict:
    """
    Analyze permission/usernamespace issues for container mounts.
    """
    container_uid = 1000
    container_gid = 1000
    host_uid = 1000
    host_gid = 1000

    if container_user:
        parts = container_user.split(":")
        try:
            container_uid = int(parts[0])
        except ValueError:
            container_uid = 1000
        if len(parts) > 1:
            try:
                container_gid = int(parts[1])
            except ValueError:
                container_gid = container_uid

    if host_user:
        parts = host_user.split(":")
        try:
            host_uid = int(parts[0])
        except ValueError:
            host_uid = 1000
        if len(parts) > 1:
            try:
                host_gid = int(parts[1])
            except ValueError:
                host_gid = host_uid

    offset = host_uid - container_uid
    nesting_depth = 1

    namespace_mapping = {
        "container_uid": container_uid,
        "container_gid": container_gid,
        "host_uid": host_uid,
        "host_gid": host_gid,
        "offset": offset,
        "nesting_depth": nesting_depth,
    }

    analysis = ""
    solutions = []
    permanent_fix = ""

    if container_uid == host_uid:
        analysis = (
            "Container UID and host UID match — no remapping needed at the userns level. "
            "If permission is still denied, check: (a) file ownership on the host at the mount "
            "path, (b) SELinux context on the host, (c) AppArmor profile blocks, "
            "(d) the mount itself is read-only."
        )
        solutions = [
            {
                "approach": "Check host file ownership",
                "explanation": "Verify the directory and files are actually owned by the listed host UID",
                "command": f"ls -la {mount_path} | head -20",
            },
            {
                "approach": "Check SELinux context",
                "explanation": "SELinux may block the container from accessing files even with correct UID",
                "command": f"ls -lZ {mount_path}",
            },
            {
                "approach": "Add SELinux :Z relabel",
                "explanation": "For private volumes, :Z relabels for a single container",
                "command": f"podman run -v {mount_path}:/data:Z ...",
            },
            {
                "approach": "Add SELinux :z relabel",
                "explanation": "For shared volumes across containers, :z shares the label",
                "command": f"podman run -v {mount_path}:/data:z ...",
            },
        ]
        permanent_fix = "Ensure host directories are chown'd to the correct user, and verify no SELinux denials exist"

    elif offset > 0 and offset < 65536:
        analysis = (
            f"Container UID {container_uid} needs to be mapped to host UID {host_uid} (offset {offset}). "
            "Rootless Podman handles this automatically via /etc/subuid. "
            "For Docker, use --user flag or user namespace remapping."
        )
        solutions = [
            {
                "approach": "Use --userns=keep-id (Podman)",
                "explanation": "Maps your host UID into the container, preserving ownership on mounts",
                "command": f"podman run --userns=keep-id -v {mount_path}:/data ...",
            },
            {
                "approach": "Add subuid mapping if missing",
                "explanation": "Configure subordinate UID range for your user",
                "command": f"sudo usermod --add-subuids {host_uid - container_uid}-{host_uid - container_uid + 65535} --add-subgids {host_gid - container_gid}-{host_gid - container_gid + 65535} $USER",
            },
            {
                "approach": "Use Docker --user flag",
                "explanation": "Run container as the host UID:GID",
                "command": f"docker run --user {host_uid}:{host_gid} -v {mount_path}:/data ...",
            },
            {
                "approach": "Create matching user in Dockerfile",
                "explanation": "Create a user with the host UID inside the image",
                "command": f"RUN groupadd -g {host_gid} appgroup && useradd -u {host_uid} -g {host_gid} appuser",
            },
        ]
        permanent_fix = (
            f"Persistently map host UID {host_uid} to container UID {container_uid} by (a) verifying "
            "/etc/subuid entries, (b) using --userns=keep-id in Podman or --user in Docker, "
            "or (c) building a Dockerfile with matching UID/GID."
        )
    else:
        analysis = (
            f"Large UID offset detected ({offset}). This is typical for rootless Podman where "
            f"subuid ranges start at high UIDs (e.g., 100000+). Container UID {container_uid} maps "
            f"to host UID {host_uid}."
        )

    if error_symptom == "selinux_block":
        analysis += " SELinux is blocking access. Check audit log: sudo ausearch -m avc -ts recent"
        solutions.append(
            {
                "approach": "Check SELinux audit log",
                "explanation": "View recent SELinux denials related to your mount",
                "command": "sudo ausearch -m avc -ts recent | grep -i container",
            }
        )
        solutions.append(
            {
                "approach": "Create SELinux policy module",
                "explanation": "Create a custom SELinux policy to allow container access",
                "command": "sudo ausearch -m avc -ts recent | audit2allow -M container_mount && sudo semodule -i container_mount.pp",
            }
        )
    elif error_symptom == "ownership_wrong":
        analysis += " File ownership on the host doesn't match expected container user."
        solutions.append(
            {
                "approach": "Chown the mount directory",
                "explanation": "Change ownership to match the container user",
                "command": f"sudo chown -R {host_uid}:{host_gid} {mount_path}",
            }
        )

    return {
        "analysis": analysis,
        "namespace_mapping": namespace_mapping,
        "solutions": solutions,
        "permanent_fix": permanent_fix,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


# ===========================================================================
# Tool 3: devops_compose_generator
# ===========================================================================


def compose_generator(
    services: list, networks: list | None = None, runtime: str = "docker"
) -> dict:
    """
    Generate Docker Compose or Podman Compose YAML content.
    """
    if networks is None:
        networks = []
    if not isinstance(services, list) or len(services) == 0:
        return {"error": "At least one service definition required"}

    lines = []

    for svc in services:
        name = svc.get("name", "service")
        image = svc.get("image", "alpine:latest")
        ports = svc.get("ports", [])
        volumes = svc.get("volumes", [])
        environment = svc.get("environment", {})
        depends = svc.get("depends_on", [])
        restart = svc.get("restart", "unless-stopped")
        command = svc.get("command", "")
        entrypoint = svc.get("entrypoint", "")
        env_file = svc.get("env_file", "")
        networks_svc = svc.get("networks", [])
        labels = svc.get("labels", {})
        healthcheck = svc.get("healthcheck", {})

        lines.append(f"  {name}:")
        lines.append(f"    image: {image}")

        if command:
            lines.append(f"    command: {command}")
        if entrypoint:
            lines.append(f"    entrypoint: {entrypoint}")
        if restart:
            lines.append(f"    restart: {restart}")

        if ports:
            lines.append("    ports:")
            for p in ports:
                lines.append(f"      - {p}")

        if volumes:
            lines.append("    volumes:")
            for v in volumes:
                lines.append(f"      - {v}")

        if environment:
            lines.append("    environment:")
            for k, v2 in environment.items():
                lines.append(f"      {k}: {v2}")

        if env_file:
            lines.append(f"    env_file: {env_file}")

        if depends:
            lines.append("    depends_on:")
            for d in depends:
                if isinstance(d, dict):
                    lines.append(f"      {d.get('service', '')}:")
                    if d.get("condition"):
                        lines.append(f"        condition: {d['condition']}")
                else:
                    lines.append(f"      - {d}")

        if networks_svc:
            lines.append("    networks:")
            for net in networks_svc:
                lines.append(f"      - {net}")

        if labels:
            lines.append("    labels:")
            for lk, lv in labels.items():
                lines.append(f'      {lk}: "{lv}"')

        if healthcheck:
            lines.append("    healthcheck:")
            test_cmd = healthcheck.get(
                "test", "curl -f http://localhost:3000 || exit 1"
            )
            lines.append(f'      test: ["CMD", "{test_cmd}"]')
            if healthcheck.get("interval"):
                lines.append(f"      interval: {healthcheck['interval']}")
            if healthcheck.get("timeout"):
                lines.append(f"      timeout: {healthcheck['timeout']}")
            if healthcheck.get("retries"):
                lines.append(f"      retries: {healthcheck['retries']}")

        lines.append("")

    compose_yaml = "\n".join(lines).rstrip()
    notes = []
    podman_considerations = []

    if runtime == "podman":
        podman_considerations = [
            "Install podman-compose: pip install podman-compose",
            "Run with: podman-compose up -d",
            "Add :Z suffix to volume paths for SELinux: ./data:/var/lib/mysql:Z",
            "Rootless: check /etc/subuid for UID mapping",
            "Use podman generate kube for Kubernetes-style deployment",
        ]
        notes.append(
            "Generated for Podman Compose — use podman-compose instead of docker-compose"
        )
    else:
        notes.append(
            "Generated for Docker Compose — use 'docker compose up -d' to start"
        )
        notes.append(
            "For multi-env: docker compose -f compose.yaml -f compose.prod.yaml up"
        )
        podman_considerations = [
            'To convert to Podman: replace "docker compose" with "podman-compose"',
            "Add :Z to volume mounts for SELinux compliance",
        ]

    if networks:
        notes.append(
            f"Networks defined: {', '.join(networks)} — ensure external creation if needed"
        )

    return {
        "compose_yaml": compose_yaml,
        "notes": notes,
        "podman_considerations": podman_considerations,
        "runtime": runtime,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ===========================================================================
# Tool 4: devops_samba_config
# ===========================================================================


def samba_config(
    share_name: str,
    path: str,
    users: list | None = None,
    guest_ok: bool = False,
    read_only: bool = False,
    special_flags: list | None = None,
) -> dict:
    """
    Generate Samba/SMB share configurations.
    """
    if users is None:
        users = []
    if special_flags is None:
        special_flags = []

    share_section = f"[{share_name}]\n"
    share_section += f"  path = {path}\n"

    if special_flags:
        share_section += f"  vfs objects = {' '.join(special_flags)}\n"

    share_section += "  browseable = yes\n"
    share_section += f"  read only = {'yes' if read_only else 'no'}\n"
    share_section += f"  guest ok = {'yes' if guest_ok else 'no'}\n"

    if not guest_ok and users:
        share_section += f"  valid users = {' '.join(users)}\n"

    share_section += "  create mask = 0664\n"
    share_section += "  directory mask = 0775\n"

    if guest_ok and not read_only:
        share_section += "  force user = nobody\n"

    if "fruit" in " ".join(special_flags).lower() or "time_machine" in special_flags:
        share_section += "  fruit:time machine = yes\n"
        share_section += "  fruit:aapl = yes\n"

    if "recycle" in special_flags:
        share_section += "  recycle:repository = .recycle/%U\n"
        share_section += "  recycle:keeptree = yes\n"
        share_section += "  recycle:versions = yes\n"

    setup_commands = []
    for user in users:
        setup_commands.append(f"sudo smbpasswd -a {user}")
    setup_commands.append("sudo systemctl restart smbd")
    setup_commands.append(
        "sudo systemctl restart nmbd  # if NetBIOS name resolution needed"
    )

    permissions_guide = (
        f"Ensure the share directory exists and has correct permissions:\n"
        f"  sudo mkdir -p {path}\n"
        f"  sudo chown -R root:users {path}\n"
        f"  sudo chmod -R 2775 {path}  # setgid ensures group inheritance\n"
    )

    troubleshooting = {
        "macos": (
            "Connect via Finder: Go > Connect to Server > smb://SERVER_IP/SHARE_NAME\n"
            "If Time Machine: check 'fruit:time machine = yes' is set\n"
            "For icon/DS_Store issues: add 'veto files = /.DS_Store/._*/.Trashes/'\n"
        ),
        "windows": (
            "Map network drive: \\\\SERVER_IP\\SHARE_NAME\n"
            "Enable SMB1/CIFS client if needed: Control Panel > Programs > Turn Windows features on or off\n"
            "Check credential manager for stale credentials\n"
        ),
        "linux": (
            "Mount with: sudo mount -t cifs //SERVER_IP/SHARE_NAME /mnt/point -o username=USER,uid=$(id -u),gid=$(id -g)\n"
            "For fstab entry: //SERVER/SHARE /mnt cifs credentials=/etc/samba/creds,uid=1000,gid=1000,iocharset=utf8 0 0\n"
        ),
    }

    return {
        "smb_conf": share_section.strip(),
        "global_settings_hint": (
            "[global]\n"
            "  server string = %h server (Samba)\n"
            "  server role = standalone server\n"
            "  obey pam restrictions = yes\n"
            "  unix password sync = yes\n"
            "  passwd program = /usr/bin/passwd %u\n"
            "  passwd chat = *Enter\\snew\\s*\\spassword:* %n\\n *Retype\\snew\\s*\\spassword:* %n\\n *password\\supdated\\ssuccessfully* .\n"
            "  pam password change = yes\n"
            "  map to guest = bad user\n"
            "  min protocol = SMB2\n"
            "  log file = /var/log/samba/log.%m\n"
            "  max log size = 1000\n"
            "  dns proxy = no\n"
        ),
        "setup_commands": setup_commands,
        "permissions_guide": permissions_guide,
        "troubleshooting": troubleshooting,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ===========================================================================
# Tool 5: devops_mergerfs_setup
# ===========================================================================


def mergerfs_setup(
    source_paths: list,
    mount_point: str,
    policy: str = "epmfs",
    options: dict | None = None,
) -> dict:
    """
    Configure mergerfs for pooling drives.
    """
    if options is None:
        options = {}

    if not isinstance(source_paths, list) or len(source_paths) < 2:
        return {"error": "At least 2 source paths required for pooling"}

    if policy not in MERGERFS_KNOWLEDGE["policies"]:
        policy = "epmfs"

    policy_explanations = {
        "epmfs": "Existing Path, Most Free Space — writes to the drive with the most free space where the target path already exists (best for media servers)",
        "ff": "First Found — picks the first branch that has the file; good for read-focused archives",
        "newest": "Newest — returns the file with the most recent modification time across branches",
        "mfs": "Most Free Space — always writes to the drive with the most free space, regardless of existing path",
        "lfs": "Least Free Space — fills up one drive before moving to the next (fill-em-up strategy)",
        "rand": "Random — picks a branch pseudorandomly",
    }

    source_str = ":".join(source_paths)

    opt_parts = [
        "defaults,allow_other,use_ino",
        f"policy={policy}",
        f"minfreespace={options.get('min_free_space', '10G')}",
    ]

    if options.get("cache_read"):
        opt_parts.append("cache.files=partial")
    else:
        opt_parts.append("cache.files=off")

    opt_parts.append("dropcacheonclose=true")
    opt_parts.append(f"category.create={options.get('create_policy', 'mfs')}")

    if options.get("symlinkify"):
        opt_parts.append("symlinkify=true")

    options_str = ",".join(opt_parts)
    mount_command = f"sudo mergerfs -o {options_str} {source_str} {mount_point}"
    fstab_entry = f"{source_str} {mount_point} fuse.mergerfs {options_str} 0 0"

    systemd_mount = (
        f"[Unit]\n"
        f"Description=MergerFS pool at {mount_point}\n"
        f"RequiresMountsFor={' '.join(source_paths)}\n"
        f"After={' '.join(source_paths)}\n"
        f"\n"
        f"[Mount]\n"
        f"What={source_str}\n"
        f"Where={mount_point}\n"
        f"Type=fuse.mergerfs\n"
        f"Options={options_str}\n"
        f"\n"
        f"[Install]\n"
        f"WantedBy=multi-user.target\n"
    )

    verification = f"df -h {mount_point} && mergerfs.fsck {mount_point}"

    optimization_tips = [
        "Use dropcacheonclose=true when exporting via NFS/Samba to avoid stale file handles",
        "Set category.create=mfs to spread writes across drives for even wear",
        "Consider category.search=ff for faster reads when file locations are predictable",
        "Use minfreespace to prevent drives from filling completely (recommend 10-50G)",
        "Add symlinkify=true only if you need relative symlinks that escape the pool",
        "For SnapRAID + mergerfs: set create policy to mfs on data disks, parity on separate drive",
    ]

    return {
        "fstab_entry": fstab_entry,
        "mount_command": mount_command,
        "systemd_mount_unit": systemd_mount,
        "explanation": {
            "policy": policy_explanations.get(policy, "Unknown policy"),
            "source_paths": source_paths,
            "mount_point": mount_point,
            "total_branches": len(source_paths),
        },
        "verification": verification,
        "optimization_tips": optimization_tips,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ===========================================================================
# Tool 6: devops_dockerfile_analyze
# ===========================================================================


def dockerfile_analyze(dockerfile: str) -> dict:
    """
    Analyze and optimize Dockerfiles.
    """
    lines = dockerfile.strip().split("\n")
    issues = []
    optimizations = []
    security_notes = []
    stages = []

    has_multistage = False
    copy_all_found = False
    install_saw = False
    user_found = False
    expose_found = False
    healthcheck_found = False
    specific_copy_found = False
    apt_clean_found = False
    npm_ci_found = False
    from_image = ""
    from_count = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        lower = stripped.lower()

        if lower.startswith("from "):
            from_count += 1
            parts = stripped.split()
            if len(parts) >= 2:
                from_image = parts[1]
            if from_count > 1:
                has_multistage = True
                stages.append({"line": i, "stage": from_count, "image": from_image})

        if re.match(r"copy\s+\.\s+\.", lower) and not specific_copy_found:
            copy_all_found = True
            if i > 1:
                prev_line = lines[i - 2].strip().lower() if i >= 2 else ""
                if "package" not in prev_line and "lock" not in prev_line:
                    issues.append(
                        {
                            "line": i,
                            "severity": "warning",
                            "message": "COPY . . copies entire build context including node_modules, .git, and sensitive files",
                            "fix": "COPY package*.json ./ && RUN npm ci --production && COPY src/ ./src/",
                        }
                    )

        if re.match(r"copy\s+package", lower) or re.match(r"copy.*\.json", lower):
            specific_copy_found = True

        if re.search(r"(apt-get|apk|yum|dnf)\s+install", lower):
            install_saw = True
            if (
                "clean" not in lower
                and "rm -rf" not in lower
                and "no-cache" not in lower
            ):
                issues.append(
                    {
                        "line": i,
                        "severity": "info",
                        "message": "Package manager install without cleanup — increases layer size",
                        "fix": "RUN apt-get update && apt-get install -y --no-install-recommends PKG && rm -rf /var/lib/apt/lists/*",
                    }
                )

        if (
            re.search(r"apt-get\s+(clean|autoremove)", lower)
            or "rm -rf /var/lib/apt/lists" in lower
        ):
            apt_clean_found = True

        if lower.startswith("user "):
            user_found = True

        if lower.startswith("expose "):
            expose_found = True

        if lower.startswith("healthcheck "):
            healthcheck_found = True

        if "npm install" in lower and "ci" not in lower:
            issues.append(
                {
                    "line": i,
                    "severity": "warning",
                    "message": "npm install in Docker may produce inconsistent builds",
                    "fix": "Use 'npm ci' for deterministic builds with package-lock.json",
                }
            )

        if "npm ci" in lower:
            npm_ci_found = True

        if "chown" in lower and ":" in lower.split("chown", 1)[-1].split()[0]:
            user_found = True

    if from_count == 1 and not has_multistage:
        optimizations.append(
            {
                "technique": "Multi-stage build",
                "savings": "~200-800MB",
                "example": (
                    "# Stage 1: Build\n"
                    "FROM node:20 AS builder\n"
                    "WORKDIR /app\n"
                    "COPY package*.json ./\n"
                    "RUN npm ci\n"
                    "COPY src/ ./src/\n"
                    "RUN npm run build\n\n"
                    "# Stage 2: Production\n"
                    "FROM node:20-slim\n"
                    "WORKDIR /app\n"
                    "COPY --from=builder /app/dist ./dist\n"
                    "COPY --from=builder /app/node_modules ./node_modules\n"
                    'CMD ["node", "dist/index.js"]'
                ),
            }
        )

    if not user_found:
        security_notes.append(
            "Container runs as root by default — add 'USER 1000:1000' or 'USER node' for security"
        )

    if install_saw and not apt_clean_found:
        security_notes.append(
            "Package cache not cleaned — use rm -rf /var/lib/apt/lists/* to reduce image size"
        )

    if not expose_found and "app" in dockerfile.lower():
        optimizations.append(
            {
                "technique": "Add EXPOSE for documentation",
                "savings": "None (documentation only)",
                "example": "EXPOSE 3000",
            }
        )

    if not healthcheck_found and (
        "web" in dockerfile.lower() or "server" in dockerfile.lower()
    ):
        optimizations.append(
            {
                "technique": "Add HEALTHCHECK",
                "savings": "Enables orchestration-aware restart policies",
                "example": "HEALTHCHECK --interval=30s --timeout=3s CMD curl -f http://localhost:3000/health || exit 1",
            }
        )

    overall_assessment = {
        "multi_stage": has_multistage,
        "non_root_user": user_found,
        "health_check": healthcheck_found,
        "explicit_expose": expose_found,
        "security_score": "good" if user_found else "needs_improvement",
    }

    return {
        "issues": issues,
        "optimizations": optimizations,
        "security_notes": security_notes,
        "overall_assessment": overall_assessment,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


# ===========================================================================
# Tool 7: devops_network_troubleshoot
# ===========================================================================


def network_troubleshoot(symptom: str) -> dict:
    """
    Diagnose container networking issues.
    """
    symptom_lower = symptom.lower().replace(" ", "_")

    diagnostics = {
        "cannot_reach_host": {
            "diagnosis": "Container cannot reach an external host or the host machine. Usually DNS, routing, or network isolation issue.",
            "commands_to_run": [
                "docker network inspect bridge  (or podman network inspect podman)",
                "iptables -L -n -t nat | grep DOCKER  (check NAT rules)",
                "ping 8.8.8.8  (test external connectivity without DNS)",
                "ping HOST_IP  (test host reachability)",
                "nslookup google.com  (test DNS resolution)",
            ],
            "common_fixes": [
                "For Docker: use host.docker.internal to reach host from container",
                "For Podman: use host.containers.internal or --network host",
                "Check firewall: ufw status, firewalld-cmd --list-all",
                "Ensure IP forwarding: sysctl net.ipv4.ip_forward=1",
                "Docker DNS: containers use 127.0.0.11 for internal DNS",
            ],
        },
        "dns_failure": {
            "diagnosis": "Container DNS resolution is failing. Common with rootless Podman (slirp4netns) or custom network configs.",
            "commands_to_run": [
                "cat /etc/resolv.conf",
                "cat /etc/resolv.conf  (inside container: docker exec CONTAINER cat /etc/resolv.conf)",
                "systemd-resolve --status  (if systemd-resolved)",
                "docker network inspect bridge | grep -A5 IPAM",
            ],
            "common_fixes": [
                "Use explicit DNS server: docker run --dns 8.8.8.8 --dns 1.1.1.1 ...",
                "Disable systemd-resolved stub listener (DNSSEC issues with Docker)",
                "Podman rootless: try --dns 8.8.8.8 explicitly",
                "Check /etc/hosts inside container for overrides",
                "For custom networks: docker network create --subnet=... --dns=8.8.8.8 mynet",
            ],
        },
        "port_conflict": {
            "diagnosis": "Requested port is already bound by another process or container.",
            "commands_to_run": [
                "ss -tlnp | grep :PORT  (or netstat -tlnp)",
                "lsof -i :PORT",
                "docker ps --filter 'publish=PORT'",
                "podman ps --filter 'publish=PORT'",
            ],
            "common_fixes": [
                "Kill the conflicting process: sudo kill $(lsof -t -i:PORT)",
                "Remove conflicting container: docker rm -f CONTAINER_NAME",
                "Use a different host port: -p ALTERNATIVE:CONTAINER",
                "Check for zombie processes holding ports: ps aux | grep PORT",
            ],
        },
        "bridge_not_working": {
            "diagnosis": "Bridge network not functioning — containers on the same bridge network cannot communicate.",
            "commands_to_run": [
                "docker network ls",
                "docker network inspect bridge",
                "iptables -L -n FORWARD",
                "sysctl net.bridge.bridge-nf-call-iptables",
            ],
            "common_fixes": [
                "Ensure bridge-nf-call-iptables is set: sysctl -w net.bridge.bridge-nf-call-iptables=1",
                "Check Docker's iptables rules: iptables -L DOCKER-ISOLATION-STAGE-1",
                "Restart Docker daemon: sudo systemctl restart docker",
                "Create a user-defined bridge: docker network create --driver bridge mynet",
                "Avoid using the default bridge for container communication",
            ],
        },
        "host_network_unavailable": {
            "diagnosis": "--network host is not working or behaving unexpectedly.",
            "commands_to_run": [
                "ip addr show",
                "ip route show",
                "cat /etc/resolv.conf",
                "docker run --rm --network host alpine ip addr",
            ],
            "common_fixes": [
                "Host networking is not available on Docker Desktop (macOS/Windows)",
                "Use --network host only on Linux; on macOS/Windows use port publishing",
                "Podman rootless: host networking requires --network host (may need slirp4netns)",
                "Check kernel allows network namespace sharing",
            ],
        },
    }

    matched = None
    for key, info in diagnostics.items():
        if key in symptom_lower:
            matched = info
            break

    if not matched:
        matched = diagnostics["cannot_reach_host"]
        matched["diagnosis"] = (
            f"Symptom '{symptom}' not specifically recognized. General network diagnostics below:"
        )

    podman_specific = {
        "rootless_networking": "Rootless Podman uses slirp4netns (default) or pasta for networking — no bridge device needed",
        "port_forwarding": "podman run -p 8080:8080 works rootless with pasta (Podman 5+); slirp4netns also supports port forwarding",
        "custom_networks": "podman network create mynet && podman run --network mynet ...",
        "dns_note": "Podman 5+ uses Aardvark DNS for name resolution on custom networks; podman run --dns 8.8.8.8 if needed",
    }

    return {
        "diagnosis": matched["diagnosis"],
        "commands_to_run": matched["commands_to_run"],
        "common_fixes": matched["common_fixes"],
        "podman_specific": podman_specific,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


# ===========================================================================
# MCP Tool Definitions
# ===========================================================================

DEVOP_TOOLS = [
    {
        "name": "devops_container_debug",
        "description": "Diagnose container issues (Podman/Docker) from error logs. Identifies permission issues, daemon errors, port conflicts, arch mismatches, and more.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "error_log": {
                    "type": "string",
                    "description": "The error log or message to analyze",
                },
                "runtime": {
                    "type": "string",
                    "enum": ["podman", "docker"],
                    "default": "podman",
                },
                "context": {
                    "type": "string",
                    "enum": ["compose", "kubernetes", "standalone", "ci"],
                    "default": "standalone",
                },
            },
            "required": ["error_log"],
        },
    },
    {
        "name": "devops_permissions_analyze",
        "description": "Analyze permission/usernamespace issues in container mounts. Diagnoses UID/GID mismatches, SELinux blocks, and namespace mapping problems.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mount_path": {
                    "type": "string",
                    "description": "Path being mounted into the container (e.g., /data/media)",
                },
                "container_user": {
                    "type": "string",
                    "description": "UID:GID inside the container (e.g., 1000:1000)",
                },
                "host_user": {
                    "type": "string",
                    "description": "UID:GID on the host (e.g., 1001:1001)",
                },
                "error_symptom": {
                    "type": "string",
                    "enum": ["permission_denied", "ownership_wrong", "selinux_block"],
                    "default": "permission_denied",
                },
            },
            "required": ["mount_path"],
        },
    },
    {
        "name": "devops_compose_generator",
        "description": "Generate Docker Compose or Podman Compose YAML from service definitions. Supports ports, volumes, environment, healthchecks, depends_on, and networks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "services": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "image": {"type": "string"},
                            "ports": {"type": "array", "items": {"type": "string"}},
                            "volumes": {"type": "array", "items": {"type": "string"}},
                            "environment": {"type": "object"},
                            "depends_on": {"type": "array"},
                            "restart": {"type": "string"},
                            "command": {"type": "string"},
                            "entrypoint": {"type": "string"},
                            "env_file": {"type": "string"},
                            "networks": {"type": "array", "items": {"type": "string"}},
                            "labels": {"type": "object"},
                            "healthcheck": {"type": "object"},
                        },
                    },
                },
                "networks": {"type": "array", "items": {"type": "string"}},
                "runtime": {
                    "type": "string",
                    "enum": ["docker", "podman"],
                    "default": "docker",
                },
            },
            "required": ["services"],
        },
    },
    {
        "name": "devops_samba_config",
        "description": "Generate Samba/SMB share configurations with troubleshooting guides for macOS, Windows, and Linux clients.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "share_name": {
                    "type": "string",
                    "description": "Name of the SMB share",
                },
                "path": {
                    "type": "string",
                    "description": "Absolute path to the share directory",
                },
                "users": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of valid users for the share",
                },
                "guest_ok": {"type": "boolean", "default": False},
                "read_only": {"type": "boolean", "default": False},
                "special_flags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "VFS objects: vfs_fruit, time_machine, recycle, shadow_copy2, etc.",
                },
            },
            "required": ["share_name", "path"],
        },
    },
    {
        "name": "devops_mergerfs_setup",
        "description": "Configure mergerfs for pooling multiple drives into a single mount point. Includes policies, fstab/systemd entries, and optimization tips.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Source drive paths to pool",
                },
                "mount_point": {
                    "type": "string",
                    "description": "Target mount point for the pool",
                },
                "policy": {
                    "type": "string",
                    "enum": ["epmfs", "ff", "newest", "mfs", "lfs", "rand"],
                    "default": "epmfs",
                },
                "options": {
                    "type": "object",
                    "properties": {
                        "min_free_space": {"type": "string", "default": "10G"},
                        "cache_read": {"type": "boolean", "default": True},
                    },
                },
            },
            "required": ["source_paths", "mount_point"],
        },
    },
    {
        "name": "devops_dockerfile_analyze",
        "description": "Analyze Dockerfiles for optimizations, security issues, and best practices. Identifies missing multi-stage builds, root-user issues, layer inefficiencies, and more.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dockerfile": {
                    "type": "string",
                    "description": "Raw Dockerfile content to analyze",
                },
            },
            "required": ["dockerfile"],
        },
    },
    {
        "name": "devops_network_troubleshoot",
        "description": "Diagnose container networking issues: DNS failures, port conflicts, bridge problems, host networking, and container-to-host communication.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symptom": {
                    "type": "string",
                    "enum": [
                        "cannot_reach_host",
                        "dns_failure",
                        "port_conflict",
                        "bridge_not_working",
                        "host_network_unavailable",
                    ],
                },
            },
            "required": ["symptom"],
        },
    },
]


# ===========================================================================
# Tool Dispatcher
# ===========================================================================


def devops_handle_tool_call(name: str, args: dict) -> dict:
    """Dispatch MCP tool call to the appropriate handler function."""
    dispatch = {
        "devops_container_debug": lambda a: container_debug(
            a["error_log"],
            a.get("runtime", "podman"),
            a.get("context", "standalone"),
        ),
        "devops_permissions_analyze": lambda a: permissions_analyze(
            a.get("mount_path", ""),
            a.get("container_user", ""),
            a.get("host_user", ""),
            a.get("error_symptom", "permission_denied"),
        ),
        "devops_compose_generator": lambda a: compose_generator(
            a["services"],
            a.get("networks", []),
            a.get("runtime", "docker"),
        ),
        "devops_samba_config": lambda a: samba_config(
            a["share_name"],
            a["path"],
            a.get("users", []),
            a.get("guest_ok", False),
            a.get("read_only", False),
            a.get("special_flags", []),
        ),
        "devops_mergerfs_setup": lambda a: mergerfs_setup(
            a["source_paths"],
            a["mount_point"],
            a.get("policy", "epmfs"),
            a.get("options", {}),
        ),
        "devops_dockerfile_analyze": lambda a: dockerfile_analyze(
            a["dockerfile"],
        ),
        "devops_network_troubleshoot": lambda a: network_troubleshoot(
            a["symptom"],
        ),
    }
    handler = dispatch.get(name)
    if handler:
        return handler(args)
    return {"status": "error", "error": f"Unknown tool: {name}"}


# ===========================================================================
# CLI Entrypoint
# ===========================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python devops-module.py <tool_name> <json_args>")
        print("Available tools:", ", ".join(t["name"] for t in DEVOP_TOOLS))
        sys.exit(1)

    tool_name = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    result = devops_handle_tool_call(tool_name, args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
