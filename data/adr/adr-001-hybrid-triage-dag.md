# ADR-001: Hybrid Triage-DAG Pattern for Multi-Agent Orchestration

**Status:** active  
**Date:** 2026-07-15  
**Category:** architecture  

## Context

Research across 5 multi-agent orchestration frameworks (OpenAI Swarm, LangGraph, CrewAI, AutoGen, Semantic Kernel) found strengths and weaknesses in each. All require external dependencies (Python SDKs, API keys) incompatible with our zero-external-dependency constraint. The research is documented in `data/orchestration-research.json`.

Key findings:
- LangGraph's DAG-based state passing provides the most robust control flow
- Swarm's triage router pattern is the simplest delegation mechanism
- AutoGen's agent-as-tool pattern maps directly to OpenCode's `task` tool
- No framework supports parallel execution as well as our native concurrent `task` tool calls
- State management is the hardest problem — LangGraph's shared-state approach is best

## Decision

Implement a **Hybrid Triage-DAG** pattern combining:

1. **Triage Router** — a lightweight routing script (PowerShell or Python) that parses task intent and builds a JSON state object
2. **DAG Pipeline** — explicit directed acyclic graph with nodes as subagent dispatches and edges as data dependencies
3. **State-as-JSON** — each subagent receives a JSON state file path, reads its input slice, writes its output slice
4. **Agent-as-Tool** — OpenCode's `task` tool serves as the agent invocation primitive

The coordinator script maintains the state file and controls DAG execution via topological ordering. DAG definitions are JSON files conforming to `data/dag-schemas/dag-definition-v1.json`.

## Consequences

Positive:
- Zero external dependencies (no pip install, no API keys for orchestration)
- Explicit state passing — every node's inputs and outputs are inspectable JSON files
- Pipeline composability — DAG definitions can be nested, chained, and versioned
- Parallel execution is natural — independent nodes run concurrently
- Compatible with OpenCode's existing `task` tool and skill system

Negative:
- JSON state files require serialization/deserialization overhead
- No built-in checkpoint/resume (unlike LangGraph) — must be implemented manually
- DAG definition files need schema validation
- No native human-in-the-loop interrupts (must use verification gate separately)

## Alternatives Considered

1. **Pure Swarm pattern** — simpler but no parallel execution or DAG topology
2. **Pure LangGraph pattern** — most feature-rich but requires LangChain dependency
3. **Role-based Crews** — intuitive team metaphor but unpredictable autonomous behavior
