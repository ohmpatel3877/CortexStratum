#!/usr/bin/env bash
# 1-Click Install: cortex-stratum for OpenCode / Claude Code / Cursor
# ====================================================================
# Usage:
#   bash <(curl -s https://raw.githubusercontent.com/ohmpatel3877/cortex-stratum/main/plugin-tools/install.sh)
#   or from local:
#   bash plugin-tools/install-cortex-stratum.sh

set -Eeuo pipefail

HARNESS="${1:-opencode}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "╔══════════════════════════════════════════════════╗"
echo "║    cortex-stratum — 1-Click Installer           ║"
echo "║    $PROJECT_DIR"
echo "╚══════════════════════════════════════════════════╝"

# ─── Step 1: Validate ──────────────────────────────────────────
echo ""
echo "▶ Step 1/5: Validating environment..."

command -v node >/dev/null 2>&1 && echo "  ✓ Node.js $(node --version)" || { echo "  ✗ Node.js required"; exit 1; }
command -v python3 >/dev/null 2>&1 && echo "  ✓ Python $(python3 --version)" || { echo "  ✗ Python3 required"; exit 1; }

# ─── Step 2: Install npm deps ──────────────────────────────────
echo ""
echo "▶ Step 2/5: Installing npm dependencies..."
cd "$PROJECT_DIR"
npm install --silent 2>&1 && echo "  ✓ npm dependencies installed" || echo "  ⚠ npm install had warnings"

# ─── Step 3: mem0 API key ─────────────────────────────────────
echo ""
echo "▶ Step 3/5: Configuring mem0 API key..."
if [ ! -f .env ]; then
  if [ -n "${MEM0_API_KEY:-}" ]; then
    echo "MEM0_API_KEY=$MEM0_API_KEY" > .env
    echo "MEM0_PROJECT=cortex-stratum" >> .env
    echo "  ✓ API key set from environment"
  else
    echo "  ○ No MEM0_API_KEY set. Get one at https://app.mem0.ai"
    echo "    Then: echo 'MEM0_API_KEY=your-key' > .env"
  fi
else
  echo "  ✓ .env exists"
fi

# ─── Step 4: Register MCP server ───────────────────────────────
echo ""
echo "▶ Step 4/5: Registering MCP server..."

case "$HARNESS" in
  opencode)
    cat > opencode.json << 'JSONEOF'
{
  "$schema": "https://opencode.ai/config.json",
  "mcpServers": {
    "cortex-stratum": {
      "name": "cortex-stratum",
      "description": "68-tool MCP server: xTrace, DTrace, Skill Router, Verifier, Goal Registry, multi-module AI",
      "command": "python",
      "args": ["scripts/tools-mcp-server.py"],
      "env": {}
    }
  }
}
JSONEOF
    echo "  ✓ Registered in opencode.json"
    ;;
  claude-code)
    echo "  ✓ Claude Code: Add MCP to your CLAUDE.md"
    ;;
  *)
    echo "  ○ Harness '$HARNESS' not auto-configured. Manual setup required."
    ;;
esac

# ─── Step 5: Link skills ───────────────────────────────────────
echo ""
echo "▶ Step 5/5: Linking skills..."

OC_SKILLS="${HOME}/.config/opencode/skills"
if [ -d "$OC_SKILLS" ]; then
  for dir in "$PROJECT_DIR/skills"/*/; do
    name=$(basename "$dir")
    target="$OC_SKILLS/$name"
    if [ ! -e "$target" ]; then
      ln -sf "$dir" "$target"
      echo "  ✓ Linked skill: $name"
    else
      echo "  ○ Already exists: $name"
    fi
  done
else
  echo "  ○ OpenCode skills dir not found at $OC_SKILLS"
fi

# ─── Summary ────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Installation Complete                           ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Project: cortex-stratum"
echo "║  Harness: $HARNESS"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "Restart your AI coding harness to load the MCP server."
