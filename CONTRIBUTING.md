# Contributing to CortexStratum

Thanks for your interest! This project is a neuroscience-inspired, zero-dependency MCP
server that gives coding agents persistent memory and multi-layer reasoning.

## How to Contribute

### Reporting Issues

Open a GitHub issue with:
- A clear title summarizing the problem
- Steps to reproduce
- Expected vs. actual behavior
- Environment details (OS, Python version, agent)

### Code Contributions

1. **Fork** the repository.
2. **Create a feature branch** (`git checkout -b feat/your-feature`).
3. **Make changes** following the guidelines below.
4. **Run the tests**:
   ```bash
   python scripts/test-mcp-server.py
   python scripts/test-smoke-server.py
   python scripts/test-skill-pipeline.py
   ```
5. **Check tool count integrity** (stale counts are a recurring problem):
   ```bash
   python scripts/check-tool-counts.py
   ```
6. **Submit a pull request.**

### Guidelines

#### Code Style
- Python stdlib only — no external dependencies unless absolutely necessary
- Follow existing patterns in `scripts/tools-mcp-server.py` (lazy module loading,
  `dry_run` support on write/mutate, MCP annotations)
- One top-level `TOOLS` entry per tool with `name`, `description`, `permission`,
  `annotations`, and `inputSchema`

#### Tool Naming
- `read_*` — information retrieval, no side effects
- `write_*` — creates/updates state, accepts `dry_run=true`
- `mutate_*` — destructive operations (delete, reset, prune), accepts `dry_run=true`

#### Documentation
- Update `AGENTS.md` when adding/changing tools
- Update `REFERENCES.md` when adding research-backed features
- Run `check-tool-counts.py` after any change to `TOOLS` in `tools-mcp-server.py`
- Regenerate `data/tool-inventory.json` after `TOOLS` changes

#### Versioning
- Update `VERSION` file and the docstring in `scripts/tools-mcp-server.py`
- Keep semantic versioning: `v0.MAJOR.MINOR-dev`

---

## References & Citations

CortexStratum's architecture is informed by neuroscience research and the MCP ecosystem.
All sources are cataloged in **[REFERENCES.md](REFERENCES.md)** with IEEE-formatted citations.

### How to cite this project in research

If you use CortexStratum in academic work, please cite:

```
O. Patel, "CortexStratum: A neuroscience-inspired MCP server for persistent agent memory
and multi-layer reasoning," v0.5.1-dev, 2026. [Online]. Available: https://github.com/ohmpatel3877/CortexStratum
```

### Adding new references

When adding a research-backed feature:

1. Add the full IEEE citation to `REFERENCES.md` under the appropriate section
2. Add a note in the feature's module docstring linking to the reference number
3. Reference the citation in code comments where the research directly informed an implementation decision

Example:
```python
# [2] Seger (2009) — Corticostriatal loops inform the gating mechanism below
```
