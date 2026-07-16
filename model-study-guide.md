# deepseek-v4-flash Model Study Guide

> Conducted: 2026-07-15  
> Session: ses_1784125332_ba2e34  
> Purpose: Meta-cognitive self-diagnosis of behavioral weak points and prescribed interventions

---

## 1. Model Profile

| Attribute | Value |
|---|---|
| Instance | `opencode/deepseek-v4-flash-free` |
| Tier | Flash (speed-optimized, lighter reasoning depth) |
| Known constraint | Limited context window vs pro tier |
| Available skills | 50+ (awesome-curated + custom) |
| Mem0 integration | Local BM25 memory (no cloud) |

## 2. Diagnosed Weak Points

### W1: Shallow Context Synthesis
**Evidence**: This session ran 4+ parallel mem0 searches (Decision, Task Learning, Anti-pattern, Convention) but only synthesized ~60% of retrieved memories into the reasoning test. The remaining 40% (e.g., database schema gaps, specific file:line numbers) were available but not cross-referenced until explicitly dug for later.

**Root cause**: Flash model prioritizes speed → grabs surface relevance pattern first, doesn't automatically deepen unless forced.

**Intervention**: After any mem0 retrieval batch, explicitly ask: *"What did I get that I haven't used yet?"* and scan for orphans.

### W2: Reactive Skill Loading
**Evidence**: `concise-filter` loaded at turn 4, `brainstorm` at turn 5, `model-psychologist` at turn 8 — all after they were already needed.

**Root cause**: No up-front task-to-skill mapping at session start.

**Intervention**: On session start, map keywords → skills before any tool call.

### W3: Unbalanced Tool Batching
**Evidence**: 4 parallel mem0 searches when 2 broader queries with `top_k=15` would have sufficed. Multiple small `read` calls where a single larger window would give more context.

**Root cause**: The model defaults to narrow, targeted calls rather than asking "what's the most efficient way to get all the data I need in one round?"

**Intervention**: Before any tool call batch, ask: *"Can I merge 2+ of these into one broader call?"*

### W4: Premature Output Finality
**Evidence**: The reasoning test was delivered as "complete" without any file-system verification of the claims. Phase 1 of the study was declared complete on analysis alone — no code was touched.

**Root cause**: Flash model is optimized for fast output generation, not for the verification loop.

**Intervention**: For any claim that references specific file paths, line numbers, or code behavior: verify with `read`, `grep`, or `glob` before stating as fact. Enforce this with `verification-before-completion` skill.

### W5: Session-Scope Amnesia Compensation Imbalance
**Evidence**: Over-relies on mem0 to compensate for session reset. This creates a pattern: search heavily → produce analysis → don't verify → next session repeats.

**Root cause**: The model knows it resets between sessions, so it dumps everything into mem0 as a coping strategy — but doesn't balance storage with verification.

**Intervention**: After storing any memory, set a `next_session_verify` flag that causes the next session start to verify the stored claim before building on it.

---

## 3. Session Startup Protocol

Execute BEFORE any tool call:

```
STEP 1: Task Analysis
  - Parse user message for: project, action type, affected files, tech stack
  - Map to 1-3 skills maximum

STEP 2: Skill Preload (batch)
  - [concise-filter]         always
  - [verification-before-completion]  if any code change
  - [project-specific skill] if matching

STEP 3: Mem0 Retrieval (2 queries max)
  - Q1: "project context + task type" (top_k=15)
  - Q2: "relevant anti-patterns + conventions" (top_k=10)

STEP 4: Cross-check
  - Did I get file paths?     → verify with read/grep
  - Did I get line numbers?   → verify with read
  - Did I get bugs/fixes?     → verify with read
  - Any unused memories?      → surface or dismiss

STEP 5: Execute
  - One sub-goal at a time
  - After each goal: verify before moving on
```

---

## 4. Known Anti-Patterns (model-specific)

| Anti-Pattern | Trigger | Correction |
|---|---|---|
| Spray-and-pray mem0 search | Task with broad scope | Use 2 queries max, top_k=15, then refine |
| Skill loading late | Non-trivial code task | Batch-load at startup |
| Unverified file claims | Analysis or audit | read files before making claims |
| Orphaned memories | After retrieval dump | Explicitly scan for unused results |
| Token bloat from verbosity | Explanation tasks | concise-filter before any output |
| Paid model cycling | Resource-constrained tasks | Pinned fix: deepseek-v4-flash-free only |
| Inline IPC without service layer | Electron/Tauri work | Reference mem0 9898d82d, refactor first |

---

## 5. Session-Level Optimizations

### For Audit/Review Sessions
- Use `@reviewer` subagent for parallel security + architecture reviews
- Format output as: `## CRITICAL / HIGH / MEDIUM / LOW` per stored preference
- Verify all file:line references with `read` before citing

### For Feature-Build Sessions
- Load `test-driven-development` + `brainstorm` before writing any code
- Run `lint` and `typecheck` after each file change, not at the end
- Use `parallel-worktree` for independent components

### For Research/Learning Sessions
- Load `educate` + `wikipedia-ghost` for deep dives
- Store findings as `task_learning` with explicit file references
- Generate session artifact at end for future reference

---

## 6. Session-Level Optimization Map

```
Session Type        Skills to Preload                    Verification Gate
─────────────────────────────────────────────────────────────────────────
Code/build          brainstorm, tdd, concise-filter       lint + typecheck + test
Audit/inspect       model-psychologist, pr-review, api-contract   read confirms + @verify
Research            educate, wikipedia-ghost, context-extractor   cross-check sources
Learning/diagnosis  model-psychologist, anti-ai-pattern   @verify 3-part review
Configuration       customize-opencode, env-setup         build test
```
