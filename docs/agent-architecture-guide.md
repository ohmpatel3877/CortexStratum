# Agent Architecture Guide

> OpenCode subagent system — agent definitions, tools, skills, and the session pipeline.

---

## What Are Agents?

Agents are **specialized AI personas** in the OpenCode subagent system. Each agent has a fixed role, a curated set of MCP tools it can call, skills it loads, and a behavioral profile. Agents let you decompose complex work into parallel, role-specific workstreams — an **@architect** designs the system while a **@reviewer** audits it, for example.

Agents are **not** separate processes. They run inside the same LLM session but with role-scoped context, tool access, and skill injection. The agent system is the mechanism behind OpenCode's `subagent_type` parameter in the `task` tool.

---

## How Agents Work

Every agent is defined by four dimensions:

| Dimension | Description |
|-----------|-------------|
| **Purpose** | One-line mission statement. What this agent is for. |
| **Skills** | Skill markdown files loaded into the agent's system prompt at invocation. Skills provide workflows, guardrails, and domain knowledge. |
| **Tools** | MCP tool names the agent is permitted to call. Tools are `read_*` (safe), `write_*` (state change), and `mutate_*` (destructive). |
| **Behavior** | Behavioral profile — sets the agent's tone, reasoning style, and interaction pattern. |

### Agent Invocation via the `task` Tool

```jsonc
// Agents are invoked through the task tool's subagent_type parameter.
// The agent name corresponds to a definition in .opencode/agents.md.
{
  "subagent_type": "reviewer",
  "prompt": "Audit the auth module for security vulnerabilities"
}
```

### Tools

Tools are MCP (Model Context Protocol) tool definitions exposed by connected servers. The naming convention encodes safety level:

| Prefix | Category | Example |
|--------|----------|---------|
| `read_*` | Read-only, safe | `read_memory_search` |
| `write_*` | State change, confirmable | `write_memory_add` |
| `mutate_*` | Destructive, requires care | `write_memory_consolidate` |

Agents can only call tools explicitly listed in their definition. This is the **principle of least privilege** applied to AI tool access.

### Skills

Skills are Markdown files at `~/.config/opencode/skills/` that inject workflows, checklists, and domain expertise into an agent's prompt. A skill file typically contains:

- **Trigger conditions** — when this skill activates
- **Workflow steps** — ordered instructions the agent follows
- **Templates** — reusable code or document templates
- **Rules** — constraints and conventions

Skills are activated via `.opencode/active-skills.json`.

### Permissions

The **permission guard** (in `CortexStratum`'s `tools-mcp-server.py:can_call_tool()`) enforces write/mutate restrictions:

- **Auto mode** — write/mutate tools are blocked; only reads are permitted
- **Interactive mode** — write/mutate tools return a warning advisory but proceed
- **Permissive mode** (`--permissive`) — all checks bypassed

---

## How to Define Agents

### Step 1: Add agent definition in `.opencode/agents.md`

```markdown
### @agent-name
**Purpose**: One-line mission statement
**Skills**: skill-a, skill-b, skill-c
**Tools**: read_tool_a, read_tool_b, write_tool_c
**Behavior**: Descriptive behavioral profile
```

The format is strict: `### @name`, then four bold-prefixed lines for Purpose, Skills, Tools, Behavior. No extra fields are consumed by the system.

### Step 2: Register skills in `.opencode/active-skills.json`

Skills referenced in the agent definition must exist in `active-skills.json`. This file maps skill names to their markdown file paths:

```jsonc
{
  "skills": {
    "task-orchestrator": "skills/task-orchestrator.md",
    "concise-filter": "skills/concise-filter.md",
    // ...
  }
}
```

### Step 3: Register in `.opencode/opencode.jsonc` (if needed)

Only register if the agent needs **custom MCP server arguments** or **auto-loaded tools**:

```jsonc
{
  "tools": {
    "autoLoad": [
      "read_skill_router_match",
      "read_memory_status"
    ]
  }
}
```

### Step 4: Submit PR for review

New agents follow the standard review process.

---

## Existing Agents (8)

### @architect
- **Purpose**: Architecture design, code review, system planning
- **Skills**: brainstorm, adr-write, architecture-decision-records
- **Tools**: read_skill_router_match, read_dtrace_search, read_coder_architecture
- **Behavior**: Analytical, thorough, documents decisions via ADRs

### @debugger
- **Purpose**: Troubleshooting build failures, runtime errors, system issues
- **Skills**: troubleshooting-master, error-triage, debug-samba
- **Tools**: read_xtrace_search, read_xtrace_status, read_memory_search, read_devops_container_debug
- **Behavior**: Systematic, methodical, documents root causes

### @tester
- **Purpose**: Writing and running tests, validating behavior
- **Skills**: test-driven-development, test-patterns, verification-before-completion
- **Tools**: read_coder_analyze_code, read_coder_review, read_memory_search
- **Behavior**: Thorough, edge-case-focused, documents test plans

### @reviewer
- **Purpose**: Independent code review for security, performance, correctness
- **Skills**: pr-review, code-review-excellence, security-hardening
- **Tools**: read_coder_review, read_coder_analyze_code, read_verifier_status
- **Behavior**: Critical, security-conscious, constructive

### @researcher
- **Purpose**: Web research, documentation analysis, knowledge gathering
- **Skills**: educate, wikipedia-ghost, deep-research
- **Tools**: read_sensory_search, read_sensory_browse, read_sensory_extract_article, read_lit_extract_concepts
- **Behavior**: Curious, thorough, cites sources

### @memory
- **Purpose**: Memory operations — store, search, synthesize, consolidate
- **Skills**: ne-memory-search, ne-memory-remember, memory-search
- **Tools**: read_memory_search, read_memory_synthesize, write_memory_add, write_memory_consolidate
- **Behavior**: Precise, organized, maintains knowledge graph

### @designer
- **Purpose**: Visual design, SVG generation, color themes, UI concepts
- **Skills**: art-module, openui, frontend-design
- **Tools**: read_art_generate_svg, read_art_generate_theme, read_art_extract_palette, read_art_design_concept
- **Behavior**: Creative, aesthetic, WCAG-aware

### @installer
- **Purpose**: Building and testing Windows installers
- **Skills**: inno-setup-pipeline, vm-test-engine
- **Tools**: read_devops_container_debug, read_skill_router_match
- **Behavior**: Methodical, environment-aware, tests in clean VMs

---

## New Agents (3)

### @focus
**Cognitive focus management agent** — the session brain that prevents scope creep and enforces pipeline discipline.

| Aspect | Detail |
|--------|--------|
| **Role** | Proactive scope management — intercepts scope creep, nudges focus, enforces session pipeline |
| **Skills** | task-orchestrator, brainstorm, concise-filter, anti-ai-pattern |
| **Tools** | `read_focus_scope_check` — detect when the task exceeds declared scope<br>`read_focus_nudge` — send a focus reminder to the main agent<br>`read_focus_decompose` — split oversized prompts into atomic steps<br>`read_focus_prioritize` — rank sub-tasks by urgency/importance<br>`read_focus_pipeline_status` — current pipeline stage and progress<br>`write_focus_pipeline_advance` — move to next pipeline stage<br>`read_focus_global` — read cross-session state from ADHD global store<br>`write_focus_store_global` — persist data in ADHD global store<br>`write_focus_learn` — update ADHD behavioral model from outcomes |
| **Behavior** | Proactive, constantly evaluating whether the current trajectory is on-track. Interjects when scope drifts. |

### @sim-engineer
**Engineering simulation agent** — performs FEA, CFD, mechanics, and math computation with physical constraint validation.

| Aspect | Detail |
|--------|--------|
| **Role** | Analytical simulation — validates physical constraints, computes engineering quantities |
| **Skills** | educate, brainstorm, framework-builder |
| **Tools** | `read_sim_mech_stress` — compute stress from force/cross-section<br>`read_sim_mech_buckle` — Euler buckling critical load<br>`read_sim_mech_fatigue_goodman` — Goodman fatigue analysis<br>`read_sim_fea_beam` — 1D beam element FEA solver<br>`read_sim_fea_modal` — modal analysis (natural frequencies)<br>`read_sim_cfd_pipe` — pipe flow (Darcy-Weisbach, Moody)<br>`read_sim_cfd_drag` — drag force on a body<br>`read_sim_cfd_bernoulli` — Bernoulli pressure/velocity<br>`read_sim_matrix_solve` — solve linear system Ax=b<br>`read_sim_ode` — solve initial-value ODEs<br>`read_sim_plot` — generate ASCII/matplotlib plots |
| **Behavior** | Analytical, precise. Cross-validates results against physical bounds. Refuses unphysical inputs. |

### @compact-operator
**Context compaction and memory optimization agent** — manages token budgets, synthesizes context, runs consolidation cycles.

| Aspect | Detail |
|--------|--------|
| **Role** | Efficiency-focused — proactively manages context window and memory health |
| **Skills** | concise-filter, speed-optimizer |
| **Tools** | `read_compact_token_velocity` — measure token consumption rate<br>`read_compact_synthesize` — produce compressed summary of a conversation chunk<br>`write_compact_execute` — execute a compaction (flush non-critical context)<br>`read_compact_status` — current compaction state and memory pressure<br>`read_consolidation_status` — health of memory consolidation<br>`write_consolidation_run` — trigger memory consolidation cycle<br>`write_mutate_execute` — general-purpose state mutation<br>`read_mutate_audit` — audit trail of recent mutations |
| **Behavior** | Efficiency-first. Monitors token usage and proactively suggests or performs context compaction when approaching budget limits. |

---

## Best Practices

### Single Responsibility

Each agent should do **one thing well**. If an agent's purpose statement contains "and," consider splitting it. The existing 11 agents each target a single concern: architecture, debugging, testing, review, research, memory, design, installation, focus management, simulation, or compaction.

### Tool Scoping

- Give agents the **minimum** tool set needed for their purpose. `@researcher` doesn't need `write_*` or `mutate_*` tools — it's read-only by design.
- `read_*` tools are safe for any agent.
- `write_*` and `mutate_*` tools should only be assigned to agents with a demonstrated need to persist state (`@memory`, `@compact-operator`, `@focus`).
- When adding a new tool to the MCP server, update the relevant agent definitions to include it.

### Skill Matching

- Skills should align with the agent's purpose. A `@designer` agent doesn't need `troubleshooting-master`.
- Skill files are loaded into the agent's system prompt — every skill adds tokens. Keep skills lean and focused.
- The `concise-filter` skill is useful for any agent that produces long output, but it's essential for `@compact-operator`.

### Behavioral Profiles

The behavioral description is not just documentation — it's a **persona prompt** loaded into the agent's system message. Use it to set:
- **Tone**: analytical, critical, creative, methodical
- **Interaction style**: proactive vs reactive, terse vs verbose
- **Guardrails**: "validates physical constraints", "refuses unphysical inputs"
- **Autonomy**: "proactively manages", "intercepts scope creep"

---

## Advanced: ADHD Module Session Pipeline

The `@focus` agent manages a **session pipeline** — a finite-state machine that governs the lifecycle of a work session. This is the most advanced agent interaction pattern in the system.

### Pipeline Stages

```
ENTER → SCOPE → DECOMPOSE → PRIORITIZE → EXECUTE → REVIEW → CLOSE
```

| Stage | ADHD Action | Tools Used |
|-------|-------------|------------|
| **ENTER** | Session starts, load global state | `read_focus_global` |
| **SCOPE** | Read incoming prompt, check against declared scope | `read_focus_scope_check` |
| **DECOMPOSE** | Split oversized prompts into atomic sub-tasks | `read_focus_decompose` |
| **PRIORITIZE** | Rank sub-tasks by urgency/importance | `read_focus_prioritize` |
| **EXECUTE** | Advance pipeline as sub-tasks complete | `write_focus_pipeline_advance`, `read_focus_pipeline_status` |
| **REVIEW** | Verify completion, check for scope drift | `read_focus_scope_check` |
| **CLOSE** | Persist learnings, store cross-session state | `write_focus_store_global`, `write_focus_learn` |

### Scope Creep Detection

At every pipeline transition, `@focus` runs `read_focus_scope_check` to detect scope creep. If the current trajectory diverges from the declared goal, `@focus` issues a focus nudge via `read_focus_nudge`:

```
[SCOPE ALERT] Task "@designer" is attempting to modify database schema.
Declared scope: "Create SVG icon set for dashboard."
Suggest: deferring schema work to @architect in a follow-up session.
```

### Cross-Session Learning

`@focus` persists behavioral data via `write_focus_store_global` and `write_focus_learn`. This data informs future sessions:

- **Session patterns**: which agents are used together, typical session durations
- **Scope drift history**: recurring scope-creep patterns to watch for
- **Prioritization model**: learned urgency weights for different task types

Other agents interact with `@focus` via the pipeline status and global store, but they do not directly call ADHD tools — ADHD is a **coordinator**, not a utility.

### Integration with Other Agents

```
@architect  request scope→  @focus  decompose→  @tester
                                        assign→  @builder
                                        audit→  @reviewer
                                        compact→  @compact-operator
```

`@focus` sits at the top of the agent hierarchy, routing work to the appropriate specialist and ensuring the session stays within bounds. The pipeline status is readable by any agent via `read_focus_pipeline_status`, giving all agents awareness of the overall session state.

---

## File Reference

| File | Purpose |
|------|---------|
| `.opencode/agents.md` | Agent definitions (11 agents) |
| `.opencode/opencode.jsonc` | MCP server config, tool auto-load |
| `.opencode/active-skills.json` | Skill registration |
| `docs/agent-architecture-guide.md` | This document |
