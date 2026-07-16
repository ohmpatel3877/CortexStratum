# Project Milestones

## Pre-1.0 Roadmap

| Milestone | Version | Status | Focus |
|-----------|---------|--------|-------|
| Foundation | v0.1.0 | ✅ Done | Core MCP server, memory engine, 7 modules, skill router v1 |
| Expansion | v0.2.0 | ✅ Done | Debug-samba expansion, Debian coverage, recurring error detection |
| Polish & Stability | **v0.3.0** | ✅ Done | Installer polish, permission model, 52-rule router, CI pipeline, agents, wiki |
| Installer Hardening | v0.4.0 | 🔜 Next | VM testing, code signing, silent install, clean-room validation |
| Full Test Coverage | v0.5.0 | ⏳ Planned | Module unit tests, >90% coverage, integration tests |
| Production Docs | v0.6.0 | ⏳ Planned | API reference, deployment guide, troubleshooting, architecture docs |
| **Stable Release** | **v1.0.0** | 🎯 Target | All modules tested, documented, hardened |

## GitHub Milestones (to create via `gh`)

Once `gh auth login` is completed, run:

```powershell
gh api repos/ohmpatel3877/ai-memory-core/milestones --field title="v0.4.0 — Installer Hardening" --field description="VM testing pipeline, code signing, silent install, clean-room validation" --field due_on="2026-08-16T00:00:00Z"
gh api repos/ohmpatel3877/ai-memory-core/milestones --field title="v0.5.0 — Full Test Coverage" --field description="Module unit tests, 90%+ coverage, integration tests for all 12 modules" --field due_on="2026-09-16T00:00:00Z"
gh api repos/ohmpatel3877/ai-memory-core/milestones --field title="v0.6.0 — Production Docs" --field description="API reference, deployment guide, troubleshooting, architecture documentation" --field due_on="2026-10-16T00:00:00Z"
gh api repos/ohmpatel3877/ai-memory-core/milestones --field title="v1.0.0 — Stable Release" --field description="All modules tested, documented, and hardened. Production-ready." --field due_on="2026-12-16T00:00:00Z"
```

## Creating Issues from Backlog

After auth, create issues linked to milestones:

```powershell
# Issue 1: Installer polish
gh issue create --title "Installer — Add 'Run OpenCode' checkbox and CLI flags" --label enhancement --milestone "v0.3.0" --body "$(cat docs/issue-backlog.md | sed -n '/## Issue 1/,/## Issue 2/p' | head -n -2)"
```

The full issue templates are in `docs/issue-backlog.md`.
