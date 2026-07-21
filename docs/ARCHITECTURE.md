# CortexStratum Architecture

**Version:** 0.6.0-dev | **Tools:** 225 (full) / **~87** (core default)
**Date:** 2026-07-21 | **Stdio-only MCP server**

## Dynamic Module Registry

Not all 225 tools are exposed by default. The server uses prefix-based filtering:

- **Core (always on, ~95 tools):** memory, MLM, limbic, WM, gate, compute_alloc, compute_exec, DMN, verifier, DAG, hooks, traces, goals, commitment, audit, compact, workstream, agent, skill, tools, phase, consolidation, pedagogy, DB, regex, conversion, module registry, VQ compression, async pool, observability, sleep, plugin engine, structured log, auth/RBAC, connector, lineage
- **Domain (opt-in, ~114 tools):** sensory, audio, coder, devops, gamedev, art, literature, sim_*, cad, electrical, mutation, plumber

Switch with `write_cortex_activemodules(modules=["read_sensory_", "read_coder_"])` or view current state by omitting `modules`.

## Dispatch Flow

```
handle_tool_call(name, args)
  → pre_verify (JSON Schema + drift detection via conflict_resolver)
  → module dispatch (prefix-routed to 20+ modules)
  → skill_ctx injection (post-processing on tool output)
  → middleware post-hooks fire (engine/mid.py)
  → result_queue.put(("result", result))
```

## Engine Modules

| Module | Lines | Tools | Prefix | Purpose |
|--------|-------|-------|--------|---------|
| `sensory-module.py` | 1204 | 13+ | `read_sensory_*` | Web fetch, scrape, browser, API, extract |
| `coder-module.py` | 3473 | 6 | `read_coder_*` | Code analysis + generation |
| `game-dev-module.py` | 3172 | 6 | `read_gamedev_*` | Game design, mechanics, levels |
| `audio-module.py` | 1172 | 7 | `read_audio_*` | Audio analysis, conversion, generation |
| `sim-math-module.py` | 906 | 19 | `read_sim_math_*` | Math computation (18+ tools) |
| `sim-mechanics-module.py` | 519 | 7 | `read_sim_mech_*` | Mechanical simulation |
| `sim-cfd-module.py` | 265 | 5 | `read_sim_cfd_*` | CFD simulation |
| `sim-fea-module.py` | 221 | 5 | `read_sim_fea_*` | FEA simulation |
| `art-module.py` | 432 | 4 | `read_art_*` | Art generation + design |
| `literature-module.py` | 559 | 3 | `read_lit_*` | Literary analysis |
| `devops-module.py` | 1500 | 5 | `read_devops_*` | Docker, compose, network configs |
| `utility-module.py` | 518 | 6+ | `read_convert_*`, `read_regex_*` | Format conversion, regex |
| `compact-module.py` | 428 | 3 | `read_compact_*`, `write_compact_*` | Context compression |
| `pedagogy-module.py` | 147 | 3 | `read_pedagogy_*`, `write_pedagogy_*` | Adaptive learning |
| `plumber-module.py` | 281 | 3 | `read_plumber_*`, `write_plumber_*` | Pipe/trace inspection |
| `suffix_decode_module.py` | ~270 | 4 | `read_suffix_*`, `mutate_suffix_*` | TTC Phase 2: n-gram next-tool prediction |
| `prm_module.py` | ~200 | 4 | `read_prm_*`, `write_prm_*`, `mutate_prm_*` | TTC Phase 3: process reward model (step scores) |
| `beam_search_module.py` | ~210 | 4 | `read_search_*` | TTC Phase 4: beam search + best-of-N over PRM |
| `ttc_train_module.py` | ~190 | 2 | `read_ttc_*` | TTC Phase 5: extract resolved cases to corpus |
| `mutation-module.py` | 357 | ? | — | Code mutation |
| **New this session** | | | | |
| `working_memory_module.py` | 397 | 5 | `read_wm_*`, `write_wm_*`, `mutate_wm_*` | Volatile PFC scratchpad (TTL decay, LRU eviction) |
| `conflict_resolver.py` | 436 | 3 | `read_gate_*`, `write_gate_*`, `mutate_gate_*` | Verifier gate (halt/override/incremental/rollback) |
| `compute_alloc_module.py` | 336 | 3 | `read_focus_compute_*`, `read_focus_allocate_*`, `read_focus_difficulty_*` | Heuristic difficulty + budget allocation |
| `limbic_module.py` | 530 | 6 | `read_limbic_*`, `write_limbic_*`, `mutate_limbic_*` | Emotional tagging + auto-reinforcement loop |
| `compute_exec_module.py` | 331 | 1 | `write_compute_execute` | Sandboxed Python execution (restricted builtins) |
| `daydream_module.py` | 560+ | 4 | `read_dmn_*`, `write_dmn_*`, `mutate_dmn_*` | DMN daydreaming — background consolidation, insight generation, auto-promote |
| `sleep_module.py` | ~300 | 2 | `write_cortex_sleep`, `read_cortex_sleep_status` | Sleep orchestrator — DMN→VQ→MLM→persist pipeline for pre-refresh "lights out" |
| `async_pool.py` | ~200 | 2 | `read_cortex_pool_status`, `write_cortex_pool_resize` | ThreadPoolExecutor manager — replaces unbounded threads, runtime resize, status monitoring |
| `observability.py` | ~270 | 2 | `read_cortex_metrics`, `write_cortex_metrics_reset` | Real-time tool call metrics, latency histograms, error rates |
| `vector_quantizer.py` | ~300 | — | (utility) | Tag codebook, content dedup, score binning for storage-efficient memory |
| `multi_layer_memory.py` | 561 | 6 | `read_mlm_*`, `write_mlm_*`, `mutate_mlm_*` | 3-tier memory (episodic/semantic/working) |
| `plugin_engine.py` | ~300 | 3 | `read_plugin_*`, `write_plugin_*` | Dynamic plugin loading + hot-reload via mtime polling |
| `log_module.py` | ~280 | 3 | `read_log_*`, `mutate_log_level` | JSON-line structured logging per session, level filtering, search |
| `auth_module.py` | ~550 | 10 | `write_oauth_*`, `read_oauth_*`, `write_rbac_*`, `write_aes_*` | OAuth2 client, RBAC role management, AES-GCM encryption |
| `connector_module.py` | ~150 | 2 | `write_connector_request`, `read_connector_status` | HTTP/S REST connector for external API calls |
| `lineage_module.py` | ~280 | 3 | `read_lineage_*`, `write_lineage_track` | Data lineage tracking + quality scoring (access × reinforcement × recency) |
| `mid.py` | ~200 | — | — | Middleware pipeline (pre/post hook registry, server hook registration) |

## Middleware Pipeline (`engine/mid.py`)

```
register_post(name, fn)  — add a post-hook
register_pre(name, fn)   — add a pre-hook (short-circuits on first non-None return)
register_server_hooks(...) — register server-side hooks at startup
run_pre(name, args)      — fire all pre-hooks (called from execute_tool_async)
run_post(name, args, result) — fire all post-hooks (called from execute_tool_async)
set_limbic_getter(fn)    — register limbic reference at server startup
```

**Currently registered:**
- `limbic_reinforce` — auto-reinforces limbic tags based on tool call outcome
- `skill_context` — injects skill guidance into tool output
- `trace_auto_log` — logs errors to trace system
- `memory_consolidate` — triggers MLM consolidation after memory writes
- `phase_transition` — records phase changes to the DTrace system

**To add a new hook:**
1. Define `_my_hook(name, args, result)` in `mid.py`
2. Call `register_post("my_hook", _my_hook)` at module level
3. Hook fires automatically after every tool dispatch

**Server startup registration:**
```python
# In tools-mcp-server.py __main__:
from engine.mid import set_limbic_getter
from engine.limbic_module import _get_limbic
set_limbic_getter(_get_limbic)
```

## Limbic Auto-Reinforce Pattern

Every tool call → middleware fires → limbic inspects result for success/failure → tags the tool name with valence.

- Success → positive valence + reinforcement counter
- Error → negative valence + retry suggestion
- Middleware does this automatically; modules don't need manual reinforce() calls

## Key Architectural Decisions

1. **Middleware-first** — All dispatch hooks go through `engine/mid.py` pipeline, not patched into `execute_tool_async` one-off. Retroactively fixed.
2. **Module lazy-loading** — Modules import via `_get_module(path)` at call-time, not at server startup. Keeps boot fast.
3. **Prefix-based dispatch** — Tool names encode their module: `read_wm_*` → Working Memory, `mutate_limbic_*` → Limbic.
4. **No external deps** — 100% Python stdlib. Sandboxed exec blocks non-stdlib imports.
5. **Threading vs subprocess** — Current sandbox uses threading for timeout (leaks daemon threads on infinite loops). Future: subprocess-based isolation.

## Drift Integrity

- `scripts/check-tool-counts.py --ci` — verifies count matches all docs
- `scripts/check-tool-counts.py --fix` — auto-updates stale counts in all files
- `data/tool-inventory.json` — canonical runtime snapshot (176 tools)
- `known_stale` list tracks historical counts to prevent missed updates

## Tool Categories

```
read (142): sensory, coder, gamedev, audio, sim_math, sim_mech, sim_cfd, sim_fea,
            art, lit, devops, utility, compact, pedagogy, plumber, wm, gate, limbic,
            compute, dag, db, dtrace, hooks, memory, agent, focus, goal_registry,
            audit, consolidation, commitment, phase, skill, tools, verifier, xtrace
write (24): compact, compute, dag, db, dtrace, focus, gate, goal_registry, hooks,
            limbic, memory, pedagogy, plumber, verifier, wm, xtrace
mutate (10): audit, commitment, consolidation, focus, gate, limbic, sensory, verify, wm
```
