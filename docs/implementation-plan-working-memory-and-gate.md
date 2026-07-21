# Implementation Plan: Working Memory Module

**Target:** v0.6.0 · **Effort:** Small (1-2 sessions) · **Priority:** P1

## Concept

A dedicated, fast-access scratchpad that holds the current session's active context.
Mirrors the PFC's ability to keep information "online" for immediate manipulation.
Auto-decays — items vanish after reaching TTL or being displaced by newer items.

## Module Spec

### File: `engine/working-memory-module.py`

### Data Model

```python
WorkingMemoryItem = {
    "key": str,          # Unique identifier within session
    "value": Any,        # The stored content (dict, string, list)
    "importance": float, # 0.0–1.0, affects decay speed
    "created_at": str,   # ISO timestamp
    "last_access": str,  # ISO timestamp
    "access_count": int, # Tracks how often this item is read
    "ttl_seconds": int,  # Time-to-live (default: 300 = 5 min)
}
```

### Storage

- **In-memory dict** (`{}`) — no persistence to disk
- Max capacity: **50 items** (configurable)
- Eviction policy: LRU-2D (Least Recently Used × Decay-aware)
- Auto-decay: `importance * 300` seconds baseline, items past TTL are purged on next access
- Full flush on server restart (session-scoped)

### Tools

#### `read_wm_status`
Returns current WM stats: item count, capacity, oldest item age, most active key.

#### `read_wm_recall(key: str)`
Fetch an item from working memory. Refreshes its `last_access` and `access_count`.
Returns null (not error) if key doesn't exist or has expired.

#### `write_wm_store(key: str, value: Any, importance: float = 0.5, ttl_seconds: int = 300)`
Store an item in working memory. Displaces oldest/lowest-importance item if at capacity.

#### `mutate_wm_clear(keep_keys: list[str] | None = None)`
Flush working memory. If `keep_keys` provided, only those survive (like a hard context reset).

#### `write_wm_importance(key: str, importance: float)`
Bump or lower an item's importance mid-session. Higher importance = slower decay.

### Integration Points

**In `tools-mcp-server.py`:**
- Add `working-memory-module` to lazy-loaded module factory (`_get_module`)
- Register 5 tools in `TOOLS` list
- Wire dispatch in `handle_tool_call()` for prefixes `read_wm_*`, `write_wm_*`, `mutate_wm_*`

**In existing modules:**
- **focus-module** → `read_focus_scope_check` can check WM for recent context before nudging
- **plumber-module** → `write_plumber_checkpoint` can also write a WM item (faster access than checkpoint file)
- **compact-module** → compaction can skip items still hot in WM (recent = not ready for condensation)
- **hooks-module** → `read_hooks_prefetch` can seed WM with key context on session start

### Constraints

- No disk I/O — pure in-memory
- Max 50 items — strict limit prevents WM from becoming just another memory store
- TTL-based decay enforced lazily (on access, not via background thread)
- Session-scoped: vanish on restart (this is by design — WM is volatile)

---

# Implementation Plan: Corticostriatal Gate (Conflict Resolver)

**Target:** v0.6.0 · **Effort:** Small (1 session) · **Priority:** P0

## Concept

A coordination layer that sits between the tool dispatch table and tool execution.
Resolves conflicts when multiple tools could handle a request or when modules
propose competing actions. Based on the cortico-striatal loop where the striatum
acts as a gate, selecting one cortical command while suppressing others.

## Module Spec

### File: `scripts/conflict-resolver.py` (or inline in `tools-mcp-server.py`)

### Core Logic

```python
class ConflictResolver:
    def __init__(self):
        self.strategy = "priority"  # priority | confidence | ask_module

    def resolve(self, candidates: list[ToolCandidate]) -> ToolCandidate:
        """
        Given competing tool candidates, pick one.
        Strategies:
          - priority: mutate > write > read (safety-first)
          - confidence: highest explicit confidence score
          - ask_module: defer to the module that proposed the highest-priority candidate
        """
        ...
```

### ToolCandidate Structure

```python
ToolCandidate = {
    "tool_name": str,
    "module": str,
    "confidence": float,    # 0.0–1.0, how sure the proposing module is
    "category": str,         # "read" | "write" | "mutate"
    "conflicts_with": list, # Tool names this conflicts with
    "rationale": str,        # Why this tool wants to handle it
}
```

### Conflict Detection Rules

| Situation | Resolution |
|-----------|-----------|
| Same module proposes 2+ tools | Pick highest confidence |
| Two modules propose write/mutate | Block both, return conflict warning |
| Read vs Write on same data set | Write wins (consistency) |
| Mutate vs. Write on same key | Mutate wins (destroy-or-modify takes priority) |
| Timeout: no resolution in 2s | Return "gate_error" with list of conflicting tools |

### Tools

No new MCP tools needed — the gate is an internal middleware layer.
But expose a diagnostic tool:

#### `read_gate_status`
Returns current conflict resolver state: strategy, recent conflicts, resolution history.

#### `write_gate_strategy(strategy: str)`
Switch resolution strategy at runtime: `priority`, `confidence`, `ask_module`.

### Integration Points

**In `handle_tool_call()` (tools-mcp-server.py):**
1. Before executing a tool, ask the gate: "can I run this?"
2. The gate checks current context (are we in a write transaction? is there a conflicting read?)
3. If conflict detected, either block with error or defer to strategy
4. Log all decisions to `read_gate_status` / error registry

**In modules proposing tools:**
- Module factory `_get_module(module_name)` can return confidence scores
- Sensory module with multiple data-fetching strategies could report which one it prefers
- Heavy modules (sim engines) can register expected resource usage

### Execution Flow (Before vs After)

**Before (current):**
```
request → prefix match → execute handler → return result
```

**After (with gate):**
```
request → collect candidates → Gate: resolve conflict → execute winner → log decision → return result
```

### Edge Cases

- **No conflict:** Gate acts as passthrough (zero overhead for single-candidate calls)
- **All candidates equal:** Default to `mutate > write > read` safety priority
- **Gate itself fails:** Fall through to original dispatch (fail-open not fail-closed)
- **Rapid-fire requests:** Gate caches recent resolutions for 500ms to avoid re-resolving identical conflicts

---

## Summary

| Module | Files to create/modify | New tools | Lines of code |
|--------|----------------------|-----------|---------------|
| Working Memory | `engine/working-memory-module.py` + TOOLS/dispatch | 5 | ~250 |
| Conflict Resolver | Inline in `tools-mcp-server.py` + `engine/conflict-resolver.py` | 2 diagnostic | ~150 |

Both modules together add **~7 new tools** to the TOOLS list (bringing total to ~165).
