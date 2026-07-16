# ADR-002: Identity/Persona Persistence via mem0 Distillation

**Status:** active  
**Date:** 2026-07-15  
**Category:** architecture  

## Context

mem0 stores user preferences, anti-patterns, and task learnings but has no mechanism for maintaining a consistent persona across sessions. Each session starts with a blank identity unless explicitly loaded via memory search. This leads to inconsistent behavior — the agent may act formal in one session and casual in another, or forget established principles.

The identity-manager.py script exists but operates standalone, not wired into the session startup flow.

## Decision

Distill identity from mem0 profiles at session start using a three-phase approach:

1. **Consolidation phase** — `scripts/identity-manager.py --consolidate` reads all mem0 memories and profile files, extracts traits (from `user_preferences`), principles (from `architecture_decisions`), behavioral patterns (from `anti_patterns`), and knowledge boundaries
2. **Storage phase** — the structured identity is written to `.memory/identity/current-identity.json` with version tracking and evolution history
3. **Injection phase** — `identity-manager.py --render` produces a markdown session prompt fragment that gets injected at session start

The identity evolves over time — each consolidation bumps the patch version and logs changes to `data/identity-evolution-log.json`.

## Consequences

Positive:
- Consistent persona across sessions — traits, principles, and patterns persist
- Self-improving — identity strengthens as more memories accumulate
- Full audit trail — evolution log provides transparency into how identity changes

Negative:
- Slightly longer session init (consolidation reads all memories)
- Cold-start problem — first consolidation has limited data
- Identity drift possible if conflicting preferences accumulate without resolution

## Alternatives Considered

1. **Manual persona definition** — static but doesn't evolve with user patterns
2. **Full mem0 context injection** — too noisy, no structured abstraction
3. **No identity persistence** — current behavior, leads to inconsistency
