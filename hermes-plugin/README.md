# ai-memory-core Hermes Plugin

Memory provider for Hermes Agent — sandboxed, structured, permission-gated.

## Features

- **3-tier permission model** — read/write/mutate gating (unique in the MCP ecosystem)
- **Hybrid search** — BM25 + vector + cross-encoder reranking
- **Lifecycle hooks** — auto-surfacing, session persistence, decision extraction
- **Structured registries** — errors, decisions, goals, commitments
- **Zero GPU** — runs on CPU, no API keys needed

## Installation

```bash
# Clone the repo
git clone https://github.com/ohmpatel3877/ai-memory-core.git ~/ai-memory-core

# Symlink the plugin
ln -s ~/ai-memory-core/hermes-plugin ~/.hermes/plugins/ai-memory-core

# Enable in Hermes
hermes plugins enable ai-memory-core
hermes memory setup
```

## Tools

| Tool | Description |
|------|-------------|
| `aime_retrieve` | Hybrid search + cross-encoder reranking |
| `aime_search` | Quick BM25 keyword search |
| `aime_decisions` | Architecture decision lookup |
| `aime_status` | Provider health + stats |
| `aime_observe` | Log observations (auto-pushes to decision registry) |

## Configuration

Set via `hermes memory setup` or environment:

| Env Var | Default | Description |
|---------|---------|-------------|
| `AI_MEMORY_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `AI_MEMORY_RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder for reranking |

## Comparison

| Feature | ai-memory-core | ClawMem |
|---------|---------------|---------|
| Permission model | ✅ 3-tier | ❌ None |
| Hybrid search | ✅ BM25 + vector + reranker | ✅ BM25 + vector + graph |
| Structured registries | ✅ Error, decision, goal | ❌ FTS5 only |
| Zero GPU | ✅ CPU only | ❌ 4-16 GB VRAM |
| Python-native | ✅ | ❌ Bun/TypeScript |
