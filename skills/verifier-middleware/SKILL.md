# Verifier Middleware

**Use when**: You need to check the verifier middleware state, apply a correction renudge, or clear a resolved renudge. The verifier sits between every tool call and the tool implementation — it pre-verifies inputs and post-verifies outputs.

**Do NOT use when**: Running the full verification gate (use `verification-before-completion`), debugging a specific tool error (use `error-triage`).

## Overview

The verifier middleware checks every tool call for:
- **Prompt injection** — detects jailbreak attempts and system prompt leaks
- **PII/sensitive data** — redacts credentials, tokens, keys before they reach tools
- **Provenance** — validates source attribution
- **Security** — blocks dangerous patterns

It runs in **advisory mode** by default (warns but doesn't block). In auto mode, it can reject tool calls that fail verification.

## MCP Tools

### `read_verifier_status`
Check current verifier state, active renudges, and violation counts.

**Example:**
```
Read the verifier status to check for any active renudges or violations.
```

### `write_verifier_renudge`
Apply a correction to the verifier's understanding. Use when the verifier flags something that's actually acceptable, or when you want to teach it a new pattern.

**Parameters:**
- `target` — what to correct (e.g., a tool name, a pattern)
- `correction` — the correction data (e.g., `{"pattern": "allowed_domain", "value": "example.com"}`)
- `strategy` — one of: `incremental` (default), `rollback`, `override`, `halt`

**Example:**
```
Apply a renudge to allow API calls to our internal domain.
```

### `write_verifier_clear_renudge`
Remove a previously applied renudge when it's no longer needed.

**Example:**
```
Clear the renudge for the internal API domain — no longer needed.
```

## Integration Points

- **Called automatically** by `handle_tool_call()` in `tools-mcp-server.py` (line 343) for every tool invocation
- **Test suite**: `python scripts/verifier_middleware.py` runs 15 tests
- **Skill router**: triggers on "verify", "validate", "check" keywords via `verification-before-completion`

## Common Workflows

### After a tool is rejected
```
1. read_verifier_status — check what was flagged
2. write_verifier_renudge — apply correction if false positive
3. Retry the original tool call
```

### Before completing a task
```
1. read_verifier_status — verify clean state
2. read_audit_status — check permission trail
3. Run the full verification gate (verification-before-completion skill)
```
