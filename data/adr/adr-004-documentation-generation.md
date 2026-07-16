# ADR-004: Regex-Based Documentation Generator

**Status:** active  
**Date:** 2026-07-15  
**Category:** process  

## Context

The ai-memory-core project has 45+ scripts, 68 MCP tools (across tools-mcp-server.py), and a growing DAG pipeline system. Documentation is manually maintained and frequently falls out of sync with the actual code. New scripts and tools are added without corresponding docs updates.

Key documentation challenges:
- Script docstrings follow varying formats (Google-style, reStructuredText, plain)
- MCP tool definitions are spread across tools-mcp-server.py
- DAG definition schemas exist as JSON schema files but no usage docs
- No single discoverability entry point for the full API surface

## Decision

Implement a **regex-based documentation generator** (`scripts/doc-generator.py`) that:

1. **Script scanner** — scans `scripts/*.py` and `scripts/*.ps1` for docstrings/comments using pattern matching:
   - Python: `"""..."""` at module level and function level
   - PowerShell: `<# ... #>` block comments at script level
   - Extracts: script name, description, usage, parameters, examples
2. **MCP tool scanner** — parses `scripts/tools-mcp-server.py` for `@tool` decorator patterns and extracts tool name, description, parameters
3. **DAG scanner** — reads `data/dag-definitions/*.json` and produces pipeline documentation
4. **Schema scanner** — reads `data/dag-schemas/*.json` and documents the contract interfaces
5. **Output** — generates `docs/api-reference.md` with organized sections

The generator is idempotent and fast (~2 seconds for full scan). It does not require parsing the AST — regex patterns are sufficient given our code conventions.

## Consequences

Positive:
- Documentation stays in sync with code (generated on-demand)
- Zero dependencies beyond Python stdlib
- Fast execution enables generation as pre-commit hook
- Consistent format across all script types

Negative:
- Regex can miss edge cases (multi-line docstrings, unusual formatting)
- No semantic understanding — cannot infer intent, only extract what's written
- Generated docs lack narrative flow compared to hand-written guides
- Requires docstrings to follow discoverable patterns — scripts without docstrings are invisible

## Alternatives Considered

1. **Sphinx with autodoc** — full Python AST parsing, but requires Sphinx dependency and doesn't handle PowerShell
2. **Manual documentation** — most flexible but always falls out of sync
3. **TypeScript/JSdoc style** — not applicable to Python/PowerShell codebase
4. **AI-generated documentation** — could hallucinate, not deterministic
