"""
ai-memory-core — Hermes Agent MemoryProvider Plugin.

Registers as a Hermes memory provider with sandboxed read/write/mutate
permission tiers. Provides BM25 search, vector/hybrid search,
cross-encoder reranking, lifecycle hooks, and structured registries.

Installation:
  1. Clone or symlink this directory to ~/.hermes/plugins/ai-memory-core/
  2. Run: hermes plugins enable ai-memory-core
  3. Run: hermes memory setup
"""

from .provider import AimeProvider


def register(ctx):
    """Hermes plugin entry point. Called by the Hermes plugin loader."""
    provider = AimeProvider()
    ctx.register_memory_provider(provider)
