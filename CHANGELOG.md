# Changelog

## [1.2.0] — 2026-07-16

### Added
- debug-samba: 10 new Debian debugging sections (9.1–9.10)
  - Debian OS health check, apt/package management
  - Systemd service debugging
  - Network debugging (ifupdown, netplan, nftables)
  - Kernel & filesystem (FUSE, inotify, I/O scheduler)
  - WSL2 integration (systemd, port forwarding, DrvFs)
  - Samba package management on Debian
  - Podman on Debian (subuid, overlayfs, AppArmor)
  - System recovery and chroot rescue
  - Debian failure signatures for mem0

### Changed
- Skill expanded from 1030 to 1375 lines
- Triage flow now starts with Layer -1: Debian OS health

### Docs
- VERSION file added (1.2.0)
