# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
**prior to 1.0.0**: minor versions (0.x.0) can include breaking changes.

## Current Milestone: v0.3.0 — Polish & Stability

**Target**: v1.0.0 after 2-3 more milestones (installer hardening, full test coverage, production docs)

### [0.3.0] — 2026-07-16

#### Added
- **Installer polish**: "Launch OpenCode" and "Open verification terminal" checkboxes at end of Inno Setup install
- **CLI flags**: `--help`, `--version`, `--list-tools`, `--permissive`, `--debug` for `tools-mcp-server.py`
- **Permissive mode**: `--permissive` flag bypasses all permission checks for trusted environments
- **Memory consolidation improvements**:
  - Confidence-based text selection (merges keep higher-confidence entry)
  - Source priority ranking (code_preference > user_preference > system > task_learning > manual > test)
  - `dry_run` parameter to preview merges without modifying data
  - Detailed per-merge similarity report
- **Skill router expanded**: From 30→52 trigger rules covering Kubernetes, database, payment, CI/CD, monitoring, Docker, Terraform, accessibility, legal, Excel, game dev, audio, devops, computer vision, project management
- **Skill router fallback**: 3-level fallback (env var → user config file → built-in defaults)
- **User config support**: `~/.opencode/skill-router-overrides.json` for custom skill overrides
- **CI pipeline**: `.github/workflows/ci.yml` — 5-stage CI (syntax check, core tests, memory tests, skill validation, installer build)
- **OpenCode agents**: `.opencode/agents.md` — 8 specialized agents with tailored skills and tools
- **Wiki content**: 8 wiki pages (Home, Getting Started, Permission Model, Memory System, MCP Tools, Build Pipeline, Skill Router, Troubleshooting)
- **New tests**:
  - `test-skill-pipeline.py`: 157 tests across 5 suites (skill validation, router structure, E2E matching, dud detection, tool inventory)
  - `test-smoke-server.py`: 8 quick health checks for the MCP server
- **Documentation**:
  - `docs/memory-store-schema.md`: Complete memory store JSON schema reference
  - `docs/issue-backlog.md`: 8 issues documented for GitHub

#### Fixed
- `test-mcp-server.py`: Corrected 8 tool name mismatches (now 10/10 passing)
- `_get_module()` factory: Added proper error handling (try/except with user-friendly messages + FileNotFoundError)
- README permission model now documents all 3 modes accurately

#### Changed
- Version bumped from 0.2.0 to 0.3.0
- `can_call_tool()` restructured with explicit 4-level hierarchy (permissive > auto > interactive > unknown tool)
- Skill router version bumped from 1 to 2 with new schema fields (fallback, user_config_path)
- All project files version-aligned to 0.3.0 (VERSION, ISS, package.json, opencode.json, plugin.json)

---

### [0.2.0] — 2026-07-16

#### Added
- debug-samba: 10 new Debian debugging sections (9.1–9.10)
  - Debian OS health check, apt/package management
  - Systemd service debugging
  - Network debugging (ifupdown, netplan, nftables)
  - Kernel & filesystem (FUSE, inotify, I/O scheduler)
  - WSL2 integration (systemd, port forwarding, DrvFs)
  - Samba package management on Debian
  - Podman on Debian (subuid, overlayfs, AppArmor)
  - System recovery and chroot rescue
  - Debian failure signatures for error registry

#### Changed
- Skill expanded from 1030 to 1375 lines
- Triage flow now starts with Layer -1: Debian OS health

---

### [0.1.0] — 2026-07-15

#### Added
- Initial MCP server (68 tools, permission guard, module loader)
- NE-Memory BM25 engine with synonym expansion and fuzzy matching
- Trace system: error registry, decision registry, goal registry, commitment checker
- Verifier middleware with strict/advisory modes, security scanning, renudge signals
- 7 multi-modal modules: Sensory (Playwright), Coder, Audio, Art, DevOps, Game Dev, Literature
- Skill router with 30 trigger rules
- Inno Setup installer with component selection
- Safety pipeline: prompt injection detection, PII redaction, provenance
- Task analyzer and orchestrator for parallel subagent workflows
- Inline documentation and README with examples
- VERSION file and CHANGELOG established

## Upcoming Milestones

| Milestone | Target | Focus |
|-----------|--------|-------|
| v0.4.0 | TBD | Installer hardening (VM testing, code signing, silent install) |
| v0.5.0 | TBD | Full test coverage (module unit tests, >90%) |
| v0.6.0 | TBD | Production docs (API reference, deployment guide, troubleshooting) |
| v1.0.0 | TBD | Stable release — all modules tested, documented, and hardened |
