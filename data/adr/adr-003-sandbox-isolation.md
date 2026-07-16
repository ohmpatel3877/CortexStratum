# ADR-003: Temp-Directory Sandbox for Code Execution

**Status:** active  
**Date:** 2026-07-15  
**Category:** architecture  

## Context

The system needs the ability to execute untrusted or isolated code snippets (Python, PowerShell, shell) in a contained environment. Docker would provide strong isolation but adds a heavy dependency — not all environments have Docker installed, and container startup latency (1-3 seconds) is prohibitive for quick code checks.

The sandbox-manager.py script exists with temp-directory isolation but operates independently, not wired into the orchestration pipeline.

## Decision

Implement a **temp-directory based sandbox** with static safety checks:

1. **Isolation** — each execution gets a unique temp directory under `%TEMP%/opencode/sandbox/<uuid>/`
2. **Safety** — pre-execution static analysis scans code against blocklist patterns (os.system, subprocess, eval, file writes, network sockets) with weighted risk scoring
3. **Timeouts** — subprocess execution with threading.Timer for hard kill on timeout
4. **Cleanup** — temp directories are removed after execution unless --keep-files is set
5. **Logging** — every execution is logged to `data/sandbox-log.json` with code hash, duration, risk score

No Docker dependency. The safety analysis catches common dangerous patterns but does not provide true sandbox isolation — it is a safety screen, not a security boundary.

## Consequences

Positive:
- Fast startup (milliseconds, no container overhead)
- Zero dependencies beyond Python stdlib
- Cross-platform (Windows, macOS, Linux)
- Executions are auditable via sandbox log

Negative:
- No network isolation (intentional — some tasks need HTTP calls)
- Static analysis can be bypassed (obfuscated code, encoded strings)
- No resource limits (CPU, memory) beyond timeout
- Not suitable for untrusted third-party code

## Alternatives Considered

1. **Docker containers** — strongest isolation but heavy dependency and slow startup
2. **Subprocess with restricted tokens (Windows)** — complex, Windows-only
3. **Pyodide/WASM** — Python-only, no shell or PowerShell support
4. **No sandbox** — current behavior, no isolation at all
