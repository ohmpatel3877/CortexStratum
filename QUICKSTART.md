# Quick Start Guide

Get CortexStratum running in under 2 minutes.

## Prerequisites

- **Python 3.10+** — [Download](https://python.org)
- **Git** — [Download](https://git-scm.com)

## Step 1: Clone

```bash
git clone https://github.com/ohmpatel3877/CortexStratum.git
cd CortexStratum
```

## Step 2: Install Dependencies

Core system needs **zero** pip packages — it's all stdlib:

```bash
# Core only (no pip needed — everything works immediately)
python scripts/tools-mcp-server.py --version
```

Optional modules for web browsing, audio, and OCR:

```bash
# Full installation (all optional features)
pip install -r requirements-full.txt

# Or install only what you need:
pip install playwright beautifulsoup4 trafilatura pdfplumber  # browsing
playwright install firefox                                     # browser engine
```

## Step 3: Start the Server

```bash
# Interactive mode (default — write/mutate tools show warnings)
python scripts/tools-mcp-server.py

# Permissive mode (all tools allowed, no checks)
python scripts/tools-mcp-server.py --permissive

# Debug mode (verbose logging)
python scripts/tools-mcp-server.py --debug
```

## Step 4: Connect OpenCode

Add to your `opencode.json`:

```json
{
  "mcpServers": {
    "CortexStratum": {
      "command": "python",
      "args": ["scripts/tools-mcp-server.py"]
    }
  }
}
```

Or use the permissive variant to bypass permission checks:

```json
{
  "mcpServers": {
    "CortexStratum": {
      "command": "python",
      "args": ["scripts/tools-mcp-server.py", "--permissive"]
    }
  }
}
```

## Step 5: Verify

Open a new terminal and run:

```bash
# Check version
python scripts/tools-mcp-server.py --version

# List all 122 tools
python scripts/tools-mcp-server.py --list-tools

# Run the test suite
python scripts/test-mcp-server.py
```

## Windows Installer (Alternative)

Download the installer from [GitHub Releases](https://github.com/ohmpatel3877/CortexStratum/releases):

```
opencode-container-server-setup.exe
```

This installs Docker Desktop + the MCP server container with one click.

## What's Next?

- [ARCHITECTURE.md](ARCHITECTURE.md) — System design and permission model
- [COMMANDS.md](COMMANDS.md) — All CLI commands
- [BUILD.md](BUILD.md) — Building from source
- [DEPENDENCIES.md](DEPENDENCIES.md) — Full dependency reference
