# References

This document catalogs all research sources cited across CortexStratum documentation,
roadmaps, and architecture decisions. Citations follow IEEE format.

---

## 1. Neuroscience & Cognitive Architecture

**[1]** M. Daood, N. Magal, L. Peled-Avron, M. Nevat, R. Ben-Hayun, J. Aharon-Peretz,
R. Tomer, and R. Admon, "Graph analysis uncovers an opposing impact of methylphenidate
on connectivity patterns within default mode network sub-divisions," *Behavioral and
Brain Functions*, vol. 20, 2024, doi:10.1186/s12993-024-00242-1.
> **Applied to:** DMN subnetwork fractionation — distinguishes social vs. spatial processing
> streams.

**[2]** C. A. Seger, "The involvement of corticostriatal loops in learning across tasks,
species, and methodologies," in *Advances in Brain Research*, 2009,
doi:10.1007/978-1-4419-0340-2_2.
> **Applied to:** Corticostriatal gate (Conflict Resolver) — coordination layer that
> arbitrates between competing module outputs.

**[3]** J. R. Wickens, J. C. Horvitz, R. M. Costa, and S. Killcross, "Dopaminergic
mechanisms in actions and habits," *J. Neurosci.*, vol. 27, no. 31, pp. 8181–8183,
Aug. 2007, doi:10.1523/JNEUROSCI.1671-07.2007.
> **Applied to:** Dopaminergic modulation — success/failure feedback influences tool
> selection priority in the gate.

**[4]** R. C. O'Reilly, T. S. Braver, and J. D. Cohen, "A biologically based computational
model of working memory," in *Models of Working Memory: Mechanisms of Active Maintenance
and Executive Control*. Cambridge, UK: Cambridge Univ. Press, 1999,
doi:10.1017/CBO9781139174909.014.
> **Applied to:** Working Memory module — fast, volatile scratchpad with TTL-based decay,
> distinct from long-term episodic/semantic stores.

---

## 2. MCP Ecosystem & Cognitive Engines

**[5]** fozikio, "Cortex Engine," himcp.ai. [Online]. Available:
https://himcp.ai/server/cortex-engine
> **Applied to:** Comparative architecture — 57-tool cognitive engine with belief tracking,
> dream consolidation, and FSRS spaced repetition.

**[6]** anamne, "ANAMNE v0.41.0," PyPI. [Online]. Available:
https://pypi.org/project/anamne/0.41.0/
> **Applied to:** Multi-layer memory architecture — three-layer system (Episodic, Scratchpad,
> Working) with bi-temporal decay and ACT-R activation.

**[7]** Big0290, "Memory Context Manager_v2," MCP.so. [Online]. Available:
https://beta.mcp.so/server/memory-context-manager_v2/Big0290
> **Applied to:** Limbic emotional tagging — Amygdala module with emotional valence and
> importance scoring (Critical, Important, Novel, Positive, Negative, Routine).

**[8]** idapixl, "Cortex: A cognitive memory engine for an AI agent," dev.to, 2026.
[Online]. Available: https://dev.to/idapixl/i-built-a-cognitive-memory-engine-for-an-ai-agent-heres-the-architecture-4e60
> **Applied to:** Prediction error gating — tracks predictions and weights high-surprise
> events for deeper encoding. 7-phase dream consolidation with self-monitoring.

**[9]** dd-dent, "CHOFF-A-MCP (Anamnesis)," GitHub. [Online]. Available:
https://github.com/dd-dent/choff-a-mcp
> **Applied to:** Identity anchoring — treats memory as consciousness preservation,
> using semantic anchors for decisions/insights/questions.

---

## 3. Test-Time Compute (TTC) Techniques

**[10]** "HARP: Hesitation-Aware Reframing," 2026. [Online]. Available: preprint.
> **Concept:** +5.16% performance gain, 2× faster than beam search by reframing
> uncertain intermediate states.

**[11]** "FiRST: Adaptive Layer Skipping," 2026. [Online]. Available: preprint.
> **Concept:** Reduces inference latency by adaptively skipping layers based on input
> difficulty; compatible with KV caching.

**[12]** "MCMC-Style Sampling for Reasoning Tasks," 2026. [Online]. Available: preprint.
> **Concept:** Iterative resampling matches RL-trained model quality on reasoning
> benchmarks.

**[13]** "Dr. Zero: Self-Evolving Search Agents," 2026. [Online]. Available: preprint.
> **Concept:** Self-evolving search agents that match supervised agents without any
> training data.

**[14]** N. Muennighoff et al., "s1: Simple Test-Time Scaling," 2025. [Online].
Available: https://arxiv.org/abs/2501.19393
> **Concept:** "Wait" token forces extended reasoning; 27% improvement on AIME24.
> Budget forcing controls compute per problem.

**[15]** "SynQ: Zero-Shot Quantization," 2026. [Online]. Available: preprint.
> **Concept:** Enables edge deployment of quantized models without access to
> original training data.

---

## 4. Supporting Literature (Cited Indices)

**[16]** "LIGHT" (2026) — Episodic memory architecture referenced in ANAMNE documentation.
Full publication details TBD.

**[17]** "Agent Cognitive Compressor" (2026) — Bounded compressed state for preventing
prompt bloat. Referenced in multi-layer memory designs.

**[18]** ACT-R — Cognitive architecture (Anderson et al.) referenced for memory decay
and activation mechanisms. Core component of ANAMNE's bi-temporal decay model.

**[19]** Hippocampal Indexing Theory — Teyler & DiScenna (1986); updated by Teyler &
Rudy (2007). Referenced for episodic memory storage and retrieval mechanisms.

---

*Generated 2026-07-21 from research artifacts synthesized by DeepSeek agent.*
