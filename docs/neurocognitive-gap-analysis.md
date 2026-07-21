# Neurocognitive Gap Analysis

**Status:** Research · **Target:** v0.6.x–v0.8.0
**Source:** Cortical architecture audit comparing current modules against known brain structures and functions.

## Current Model

CortexStratum maps modules to brain regions (Prefrontal Cortex for focus, Hippocampus for memory, etc.) but misses several major neural systems. This document catalogs the gaps and prioritizes them by implementation impact.

---

## Gap 1: Working Memory (PFC) — HIGH IMPACT

**What's missing:** A dedicated, fast-access store that holds current session context and auto-flushes. The brain's PFC maintains information "online" for immediate manipulation — it's not long-term memory but the scratchpad you actively think with.

**Current state:** CortexStratum has no separation between what you're actively working on and what you've stored. The `read_focus_*` tools touch this space but don't implement a distinct working memory buffer with automatic decay.

**Proposed module:** `engine/working-memory-module.py`
- Small, fast-access store (in-memory dict, ~50KB limit)
- Automatic TTL-based decay (items expire after N tool calls or N seconds)
- Session-scoped (auto-flushed on server restart)
- Tools: `read_wm_status`, `read_wm_recall`, `write_wm_store`, `mutate_wm_clear`

---

## Gap 2: Corticostriatal Loop (Basal Ganglia gate) — HIGH IMPACT

**What's missing:** A coordination layer that resolves conflicts between competing module outputs before execution. In the brain, the striatum acts as a "gate" that selects which cortical command gets executed, preventing conflicting actions.

**Current state:** Tools are dispatched by name prefix matching in `handle_tool_call()`. If two tools could handle the same request, there's no arbitration layer — the first match wins by dispatch table order.

**Proposed module:** Add a gate layer to `scripts/tools-mcp-server.py` or new `engine/conflict-resolver-module.py`
- Tool suggestion/confidence scoring before execution
- Conflict detection between competing tool candidates
- Priority-based resolution (mutate > write > read for safety)
- Configurable arbitration strategies: always-first, highest-confidence, ask-LLM

---

## Gap 3: Default Mode Network Subnetworks — MEDIUM IMPACT

**What's missing:** The DMN isn't one monolithic idle network — it has subnetworks for social processing (people, users) and scene/spatial processing (places, project structures).

**Current state:** `compact-operator` tools handle idle-time processing but don't distinguish between social and spatial information. `write_compact_execute` runs the same compaction regardless of content type.

**Proposed module:** Extend `engine/compaction-module.py` or new `engine/dmn-module.py`
- Social memory: user preferences, collaboration patterns, communication history
- Spatial memory: project structure, file paths, code architecture maps
- Context-dependent recall priority during idle/background processing

---

## Gap 4: Multi-Layer Memory Architecture (ANAMNE-style) — MEDIUM IMPACT

**What's missing:** Real brains have distinct memory systems with different speeds and volatilities: episodic (Hippocampus), semantic (cortex), working (PFC). CortexStratum's memory is essentially one store with one retrieval mechanism.

**Current state:** `write_memory_add` and `read_memory_search` treat all memories the same. No distinction between "I just learned this" vs "this is a well-established fact."

**Proposed module:** Refactor `engine/memory_search.py` into a layered architecture
- Layer 1 (Working): In-memory, high-speed, auto-decay — current session context
- Layer 2 (Episodic): SQLite+FTS5, moderate speed — recent sessions, specific events
- Layer 3 (Semantic): BM25+consolidation, slower — learned facts, patterns
- Retrieval strategy: top-down, combine results with priority weighting

---

## Gap 5: Cortical Metadata (Layer/Column Model) — LOW IMPACT

**What's missing:** Real cortex has 6 layers with distinct cell types and connectivity. Modules mapped to brain regions don't have cytoarchitectural metadata.

**Proposed:** Add formal cortical metadata to each module definition
- Layer assignment (II/III vs IV vs V/VI)
- Cell type analog (pyramidal = output, stellate = input, fusiform = integration)
- Projection patterns (feedforward, feedback, lateral)

This is primarily documentation/augmentation of existing architecture rather than a new module.

---

## Gap 6: Limbic Emotional Tagging — MEDIUM IMPACT

**What's missing:** Memories in the brain aren't value-neutral — they carry emotional valence (positive/negative) and intensity that affects recall strength and behavioral response.

**Current state:** `write_memory_add` accepts a `tags` parameter but has no emotional/valance dimension. Reinforcement signals don't exist.

**Proposed module:** `engine/limbic-module.py`
- Emotional valance tagging (−1.0 to +1.0) on memory writes
- Intensity scoring (0.0 to 1.0) for recall strength bias
- Reinforcement learning hooks: positive/negative signals that adjust tool execution preferences
- Link to conflict resolver (Gap 2): `write_*` failures produce negative valance, reducing that tool's priority

---

## Implementation Priority

| Priority | Gap | Module | Effort | Impact |
|----------|-----|--------|--------|--------|
| **P0** | Gap 2 — Corticostriatal gate | Conflict resolver | Small | High — prevents tool conflicts |
| **P1** | Gap 1 — Working Memory | `working-memory-module.py` | Small | High — session context buffer |
| **P2** | Gap 6 — Limbic tagging | `limbic-module.py` | Medium | Medium — recall quality |
| **P3** | Gap 4 — Multi-layer memory | Refactor `memory_search.py` | Large | High — memory fidelity |
| **P4** | Gap 3 — DMN subnetworks | `dmn-module.py` | Large | Medium — background efficiency |
| **P5** | Gap 5 — Cortical metadata | Metadata augmentation | Small | Low — architectural clarity |

---

*Generated 2026-07-21 from neurocognitive audit.*
