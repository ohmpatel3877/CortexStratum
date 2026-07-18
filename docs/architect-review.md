# Senior Architect Review: CortexStratum

## Verdict: 4/10 — Technically impressive, architecturally confused.

---

## 1. Identity Crisis (Critical)

**The project doesn't know what it wants to be.**

| Layer | Tools | Lines | % of Codebase |
|-------|-------|-------|---------------|
| Core memory (actual purpose) | ~15 | ~2,800 | 12% |
| Simulation engines | 28 | ~2,500 | 11% |
| Cognitive pipeline (compact/mutate/focus) | 25 | ~2,800 | 12% |
| Agent skills (coder, gamedev, devops, audio, sensory, art, lit) | 49 | ~7,538 | 33% |
| Infrastructure/utilities | 26 | ~6,500 | 28% |
| Orchestrator/DAG | — | ~1,400 | 6% |

**Only 12% of the codebase serves the stated purpose.**  
The other 88% is a general-purpose AI tool SDK disguised as a memory server.

**Fix:** Split into 3 separate repositories:
- `cortexstratum-core` — memory, cognitive pipeline, focus (40 tools)
- `cortexstratum-sim` — mechanics, FEA, CFD, math (28 tools)
- `cortexstratum-agents` — coder, gamedev, devops, audio, sensory, art, lit (49 tools)

Each gets its own MCP server, its own dependency file, its own README.

---

## 2. Bloat: Unnecessary Features (Stupid)

These features add complexity with near-zero practical value:

### 2a. 5 Memory Search Variants (reduced to 1 merged, but old ones still exist)
**Why it's stupid:** `vector_search`, `hybrid_search`, `reranked_search` all require `sentence-transformers` which 90% of users won't install. BM25 alone handles 95% of use cases. The "graceful fallback" chain means hybrid and reranked silently degrade to BM25 anyway — so they're just BM25 with extra hops.

### 2b. ASCII Plot Generator
**Why it's stupid:** `read_sim_plot` generates ASCII art plots in terminal. In 2026, users pipe data to actual plotting tools. This was a cute demo, not a production feature.

### 2c. Music Theory Analyzer (audio module)
**Why it's stupid:** The audio module has `read_audio_music_theory` which analyzes note names and scales. It's 200 lines of music theory lookups in a memory server. There's no audio input — you type notes manually. This is a reference card, not a tool.

### 2d. Tone Generator
**Why it's stupid:** `read_audio_generate_tone` generates a mathematical tone description (frequency, amplitude). No actual sound output. It describes a sine wave. That's `math.sin()` with extra steps.

### 2e. Game Dev Monetization Guide
**Why it's stupid:** `read_gamedev_monetization` returns generic advice about ads and microtransactions. It's a static text template. There's no dynamic analysis. This is a blog post, not a tool.

### 2f. Literature Philosophy Analysis
**Why it's stupid:** `read_lit_analyze_philosophy` takes text and returns philosophy analysis. It's 50 lines of keyword matching against a list of philosophers. `read_lit_analyze_text` already does the same thing better by just looking at the text structure.

### 2g. DevOps Samba Config Generator
**Why it's stupid:** `read_devops_samba_config` generates a static Samba config template. Any user who needs Samba knows the format. This saves 0 keystrokes vs Google.

---

## 3. Low-ROI Features (Barely Add Performance)

### 3a. Cross-Encoder Reranker
200 lines of infrastructure for a model that almost no one will install. The `sentence-transformers` dependency alone is 400MB. The reranker adds another 200MB. For what: improving search result ranking from "good" to "slightly better" on 100-entry stores.

### 3b. Fuzzy Threshold Parameter
`read_memory_search` has a `fuzzy_threshold` parameter that does fuzzy matching via... BM25's built-in term overlap. It's not actually fuzzy. The parameter exists but the implementation is standard BM25.

### 3c. Position Parameter on Deflection
`read_sim_mech_deflection` has an optional `position` dict for off-center loads. The default (center load) covers 90% of use cases. The off-center formula doubles the code for 10% usage.

### 3d. Johnson Buckling Auto-Select
The merged `read_sim_mech_buckle` auto-selects Euler vs Johnson based on params. But Johnson requires `sigma_y`, `A`, and `r` — if you have those, you should be calling it explicitly. The auto-detect adds ambiguity.

---

## 4. Dependency Bloat

| Dependency | Size | Used By | Actually Needed? |
|------------|------|---------|------------------|
| playwright | ~400MB | sensory-module.py | No. Only 1 of 13 sensory tools needs it (browse). The rest use requests/bs4. |
| beautifulsoup4 | ~2MB | sensory-module.py | Yes, for HTML parsing |
| trafilatura | ~5MB | sensory-module.py | No. Article extraction is a simple readability clone. Could be 50 lines of stdlib. |
| pdfplumber | ~30MB | sensory-module.py | No. PDF extraction is niche. Should be optional. |
| Pillow | ~30MB | sensory-module.py | Yes, for image extraction |
| pytesseract | ~20MB | sensory-module.py | No. OCR in a memory server is absurd scope creep. |
| requests | ~1MB | sensory-module.py | Only for scrape. stdlib urllib works. |
| numpy | ~50MB | memory_search.py | No. Falls back gracefully. Only needed for vector search which nobody uses. |

**Total optional bloat: ~538MB** for features that 90% of users won't touch.

---

## 5. Architectural Gaps

### 5a. No Authentication
Zero auth. Any MCP client that connects can read/write all memory. The permission model works within OpenCode but there's no API key, no token, no user isolation.

### 5b. No Data Migration
The data format is JSON files. When the schema changes (and it has, multiple times), old data is silently incompatible. `memory_store.json` from v0.3.0 won't work with the current code. No migration path.

### 5c. No Query Performance Monitoring
3,500 lines of search infrastructure and zero query logging. No way to see which queries are slow, which fail, which return zero results.

### 5d. No Rate Limiting
The dry_run system prevents accidental mutations, but there's no protection against rapid-fire queries. A runaway agent can hammer the server with 1000 queries/second.

### 5e. No Health Endpoint
The MCP protocol has `ping` and `health`, but they return static "ok". No DB connection check, no disk space check, no memory usage.

### 5f. Event Sourcing / Audit Trail
The checkpoint/undo system exists but only for memory mutations. There's no global event log. You can't answer "what changed in the last hour?"

---

## 6. Code Quality Issues

### 6a. _load_json / _save_json Duplicated
Every module has its own copy of `_load_json` and `_save_json`. 15+ copies of the same 6-line function. Should be a shared utility.

### 6b. Magic Numbers
The focus module has hardcoded lists of "advanced_terms" and "basic_terms" for depth detection. These are opinionated and not configurable.

### 6c. Exception Swallowing
The `_load_json` pattern returns `{}` on any error. Corruption is silently ignored. A corrupted memory_store.json returns "empty" instead of "corrupted".

### 6d. No Typing
The entire codebase uses bare functions with no type hints. For a 15,000+ line project, this is unacceptable for maintainability.

### 6e. Test Coverage < 5%
The phase-verify-full.py tests 25 scenarios across 140 tools. That's 18% tool coverage with shallow assertions (mostly "doesn't crash").

---

## 7. Summary: What I'd Do

| Priority | Action | Impact | Effort |
|----------|--------|--------|--------|
| P0 | Split into 3 repos (core/sim/agents) | Fixes identity crisis | 1 week |
| P0 | Remove 17 deprecated tools | -12% code, cleaner API | 1 hour |
| P0 | Share _load_json/_save_json as utility | Reduces duplication | 30 min |
| P1 | Remove low-ROI features (plot, music, tone, monetization) | -1,500 lines | 2 hours |
| P1 | Add type hints to all public functions | Maintainability | 4 hours |
| P1 | Replace standalone 50-line utilities with references | -500 lines | 1 hour |
| P2 | Add auth layer | Security | 2 days |
| P2 | Add migration system | Data safety | 1 day |
| P2 | Add query logging | Debuggability | 4 hours |
| P3 | Externalize sensory/coder/gamedev | -7,500 lines from core | 1 week |
| P3 | Remove optional deps from core requirements | -538MB | 2 hours |

**Current trajectory:** 140 tools, 22,000+ lines, 26 domains.  
**Target trajectory:** 50 core tools, 5,000 lines, 3 domains (memory + cognitive + orchestration).
