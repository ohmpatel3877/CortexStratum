# Test-Time Compute (TTC) Integration Blueprint

**Status:** Research · **Target:** v0.7.x–v0.9.0
**Source:** Frontier techniques analysis (2026-07-21)

## Why This Matters

Frontier labs (OpenAI, DeepMind, Anthropic) are shifting from **pretraining compute**
to **test-time compute** — spending more inference resources on harder problems yields
better results than scaling model size, and costs zero additional GPU/model parameters.

| Metric | Value |
|--------|-------|
| Speedup via Speculative Decoding | 2–4× |
| 32B model surpasses 671B on SWE-bench | 46% |
| Additional GPU/model parameters required | **0** |

---

## Techniques & Integration Points

| Technique | Core Concept | CortexStratum Fit |
|-----------|-------------|-------------------|
| **Test-Time Compute Scaling** | Trade pretrain compute for inference compute | Focus/Compact/Mutate pipeline already manages reasoning flow; add budget allocation |
| **SuffixDecoding** | Suffix trees in CPU memory predict token continuations | Zero-GPU philosophy; accelerates repetitive tool-call patterns |
| **Process Reward Model (PRM)** | Score intermediate reasoning steps | Verifier middleware already detects drift; upgrade to step-level scores |
| **Beam Search + PRM** | Keep top-k partial solutions | DAG coordinator; add beam search variant |
| **Best-of-N Sampling** | Generate N, pick highest verifier score | Simple integration with existing verifier |
| **Internal TTC** | Train model on reasoning trajectories | Memory stores resolved cases as training data |
| **External TTC** | Apply compute at decision points | Focus module decomposes tasks; extend per sub-task |
| **Hybrid Speculative Decoding** | SuffixDecoding + EAGLE-style | Supports both compute-efficient and model-based speculation |

---

## Implementation Plan — 5 Phases

### Phase 1: Compute-Optimal Allocation (⚡ Minimal effort)
**Goal:** Estimate difficulty and allocate reasoning depth.
**New tools:** `read_focus_compute_budget`, `read_focus_allocate_depth`,
`read_focus_difficulty_estimate`
**Integration:** Extends existing Focus module. Requires minimal new code.

### Phase 2: SuffixDecoding Engine (⚡ High impact, zero-GPU)
**Goal:** Build suffix tree engine using CPU memory.
**New tools:** `read_suffix_predict`, `mutate_suffix_update`
**Impact:** 2–4× speedup on repetitive tool-call workflows.

### Phase 3: Process Reward Model (⚡ Extends verifier)
**Goal:** Score intermediate reasoning steps.
**New tools:** `write_prm_score_step`, `read_prm_status`, `mutate_prm_prune`
**Integration:** Extends verifier middleware.

### Phase 4: Beam Search with PRM (⚡ Search strategies)
**Goal:** Keep top-k partial solutions at each reasoning step.
**New tools:** `read_search_beam`, `read_search_best_of_n`
**Integration:** Modifies `write_dag_execute` to support beam search.

### Phase 5: Internal TTC Training (⚡ Distillation pipeline)
**Goal:** Extract resolved cases from procedural memory, format as reasoning trajectories.
**New tools:** `mutate_ttc_train`
**Integration:** Uses memory store as training data source.

---

## Key Research References

| Technique | Source | Key Result |
|-----------|--------|------------|
| HARP | Hesitation-Aware Reframing (2026) | +5.16% perf, 2× faster than beam search |
| FiRST | Adaptive Layer Skipping (2026) | Reduces latency, compatible with KV caching |
| MCMC Sampling | Iterative Resampling (2026) | Matches RL-trained models on reasoning tasks |
| Dr. Zero | Self-Evolving Search Agents (2026) | Matches supervised agents, zero training data |
| s1 | Budget Forcing — Muennighoff et al. (2025) | +27% on AIME24 via "wait" token |
| SynQ | Zero-Shot Quantization (2026) | Edge deployment without data access |

See [REFERENCES.md](../REFERENCES.md) for full IEEE citations.

---

## Recommended First Step

**Phase 1: Compute-Optimal Allocation.** Requires minimal new code and integrates
directly with the existing Focus module. You already have difficulty estimation via
`read_focus_decompose` and `read_focus_prioritize` — extend those to include compute
budget allocation.

After Phase 1, **Phase 2: SuffixDecoding** is the most impactful for the zero-dependency
philosophy. Adds 2–4× speedup on repetitive workflows without GPU or model weights.

---

*Generated 2026-07-21 from TTC research synthesis.*
