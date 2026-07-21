#!/usr/bin/env bash
# CortexStratum - Unified installer (Linux/macOS)
# =================================================
# Usage:
#   bash install.sh                    # Native Python install
#   bash install.sh --docker           # Containerized (Docker)
#   bash install.sh --full             # Include optional pip deps
#   bash install.sh --harness cursor   # Register for Cursor

set -Eeuo pipefail

HARNESS="${HARNESS:-opencode}"
DOCKER=false
FULL=false
FORCE=false
NOVERIFY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --docker| -d) DOCKER=true ;;
        --full| -f)   FULL=true ;;
        --force)      FORCE=true ;;
        --no-verify)  NOVERIFY=true ;;
        --harness)    HARNESS="$2"; shift ;;
        --help|-h)
            echo "CortexStratum installer"
            echo "  --docker       Containerized (Docker) install"
            echo "  --full         Install all optional pip deps"
            echo "  --force        Overwrite existing configs"
            echo "  --no-verify    Skip smoke test"
            echo "  --harness X    Target harness: opencode|claude-code|cursor|all|none"
            exit 0 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
    shift
done

echo "============================================"
echo "  CortexStratum - 1-Click Setup"
echo "============================================"
echo ""

# ─── Detect OS ────────────────────────────────────────────
IS_MAC=false
[[ "$(uname)" == "Darwin" ]] && IS_MAC=true

# ─── DOCKER MODE ──────────────────────────────────────────
if $DOCKER; then
    echo "Step 1/3 - Checking Docker..."
    if ! command -v docker &>/dev/null; then
        if $IS_MAC; then
            echo "  Install Docker: https://docs.docker.com/desktop/install/mac-install/"
        else
            echo "  Install Docker: https://docs.docker.com/engine/install/"
        fi
        echo "  Then re-run this installer."
        exit 1
    fi
    echo "  Docker: $(docker --version)"

    echo ""
    echo "Step 2/3 - Locating CortexStratum..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$SCRIPT_DIR/scripts/tools-mcp-server.py" ]]; then
        REPO_ROOT="$SCRIPT_DIR"
    elif [[ -f "$PWD/scripts/tools-mcp-server.py" ]]; then
        REPO_ROOT="$PWD"
    else
        REPO_ROOT="$HOME/github/CortexStratum"
        if [[ ! -f "$REPO_ROOT/scripts/tools-mcp-server.py" ]]; then
            echo "  Downloading..."
            mkdir -p "$HOME/github"
            git clone https://github.com/ohmpatel3877/CortexStratum.git "$REPO_ROOT" 2>/dev/null || {
                curl -sL https://github.com/ohmpatel3877/CortexStratum/archive/refs/heads/main.zip -o /tmp/CortexStratum.zip
                unzip -qo /tmp/CortexStratum.zip -d /tmp/
                mkdir -p "$REPO_ROOT"
                cp -r /tmp/CortexStratum-main/* "$REPO_ROOT/"
                rm -rf /tmp/CortexStratum*
            }
        fi
    fi
    echo "  Repo: $REPO_ROOT"

    echo ""
    echo "Step 3/3 - Building container..."
    cd "$REPO_ROOT"
    docker compose -f docker/docker-compose.yml up -d --build || {
        echo "  BUILD FAILED. Is Docker running?"; exit 1; }

    echo ""
    echo "============================================"
    echo "  DOCKER INSTALL COMPLETE"
    echo "============================================"
    echo ""
    echo "  Add to your MCP client config:"
    echo '  { "mcpServers": { "CortexStratum": {'
    echo '      "command": "docker",'
    echo '      "args": ["exec", "-i", "opencode-server",'
    echo '               "python3", "/app/scripts/tools-mcp-server.py"]'
    echo '  } } }'
    exit 0
fi

# ─── NATIVE PYTHON MODE ───────────────────────────────────

# Step 1: Python
echo "Step 1/5 - Checking Python..."
PY=""
PY_VER=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1)
        if [[ $ver =~ Python\ ([0-9]+\.[0-9]+) ]]; then
            PY="$cmd"
            PY_VER="${BASH_REMATCH[1]}"
            break
        fi
    fi
done

if [[ -z "$PY" ]]; then
    echo "  Python 3.10+ is required."
    if $IS_MAC; then
        echo "  Install: brew install python"
    else
        echo "  Install: sudo apt install python3 python3-pip  (or your distro's equivalent)"
    fi
    exit 1
fi

major=$(echo "$PY_VER" | cut -d. -f1)
minor=$(echo "$PY_VER" | cut -d. -f2)
if [[ "$major" -lt 3 ]] || { [[ "$major" -eq 3 ]] && [[ "$minor" -lt 10 ]]; }; then
    echo "  ERROR: Python 3.10+ required (found $PY_VER)."
    exit 1
fi
echo "  Python $PY_VER: OK"

# Step 2: Clone / locate repo
echo ""
echo "Step 2/5 - Locating CortexStratum..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/scripts/tools-mcp-server.py" ]]; then
    REPO_ROOT="$SCRIPT_DIR"
    echo "  Found at: $REPO_ROOT"
elif [[ -f "$PWD/scripts/tools-mcp-server.py" ]]; then
    REPO_ROOT="$PWD"
    echo "  Found at: $REPO_ROOT"
else
    REPO_ROOT="$HOME/github/CortexStratum"
    if [[ -f "$REPO_ROOT/scripts/tools-mcp-server.py" ]]; then
        echo "  Already cloned at: $REPO_ROOT"
        cd "$REPO_ROOT" && git pull --ff-only 2>/dev/null && echo "  Updated." || true
    else
        echo "  Downloading to $REPO_ROOT ..."
        mkdir -p "$HOME/github"
        git clone https://github.com/ohmpatel3877/CortexStratum.git "$REPO_ROOT" 2>/dev/null || {
            echo "  Git not available. Downloading zip..."
            curl -sL https://github.com/ohmpatel3877/CortexStratum/archive/refs/heads/main.zip -o /tmp/CortexStratum.zip
            mkdir -p /tmp/CortexStratum-extract
            unzip -qo /tmp/CortexStratum.zip -d /tmp/CortexStratum-extract
            mkdir -p "$REPO_ROOT"
            cp -r /tmp/CortexStratum-extract/CortexStratum-main/* "$REPO_ROOT/"
            rm -rf /tmp/CortexStratum*
        }
        echo "  Downloaded."
    fi
fi

# Step 3: Optional pip dependencies
echo ""
echo "Step 3/5 - Python dependencies..."
if $FULL; then
    cd "$REPO_ROOT"
    $PY -m pip install -r requirements-full.txt 2>/dev/null && \
        echo "  Optional dependencies installed." || \
        echo "  Optional install had warnings (core works without)."
    if $PY -c "import playwright" 2>/dev/null; then
        echo "  Playwright already installed."
    elif $FULL; then
        $PY -m playwright install firefox 2>/dev/null && \
            echo "  Playwright browser installed." || true
    fi
else
    echo "  Core runs on stdlib (no pip needed). Use --full for optional extras."
fi

# Step 4: Register MCP server
if [[ "$HARNESS" != "none" ]]; then
    echo ""
    echo "Step 4/5 - Registering MCP server..."
    MCP_ENTRY='{
      "name": "CortexStratum",
      "description": "115-tool MCP server: SQLite+FTS5 memory, trace, skill routing, multi-modal AI",
      "command": "'$PY'",
      "args": ["'$REPO_ROOT'/scripts/tools-mcp-server.py"],
      "env": {}
    }'
    write_mcp_config() {
        local path="$1"
        mkdir -p "$(dirname "$path")"
        if [[ -f "$path" ]]; then
            # Simple append into mcpServers (jq would be cleaner but not guaranteed)
            python3 -c "
import json, sys
with open('$path') as f: c = json.load(f)
c.setdefault('mcpServers', {})['CortexStratum'] = $MCP_ENTRY
with open('$path', 'w') as f: json.dump(c, f, indent=2)
" 2>/dev/null || echo "  Warning: could not update $path"
        else
            cat > "$path" <<'JSONEOF'
{
  "mcpServers": {
    "CortexStratum": {
      "name": "CortexStratum",
      "description": "115-tool MCP server: SQLite+FTS5 memory, trace, skill routing, multi-modal AI",
      "command": "'$PY'",
      "args": ["'$REPO_ROOT'/scripts/tools-mcp-server.py"],
      "env": {}
    }
  }
}
JSONEOF
        fi
        echo "  Registered in: $path"
    }

    case "$HARNESS" in
        opencode|all)
            write_mcp_config "$REPO_ROOT/opencode.json" ;;
    esac
    case "$HARNESS" in
        claude-code|all)
            cat > "$REPO_ROOT/CLAUDE.md" <<EOF
# Claude Code - CortexStratum MCP Server

<mcpserver>
{
  "name": "CortexStratum",
  "description": "115-tool MCP server for memory, tracing, and orchestration",
  "command": "$PY",
  "args": ["$REPO_ROOT/scripts/tools-mcp-server.py"],
  "working_dir": "$REPO_ROOT"
}
</mcpserver>
EOF
            echo "  Registered in: CLAUDE.md" ;;
    esac
fi

# Step 5: Link skills
echo ""
echo "Step 5/5 - Linking skills..."
OC_SKILLS="${HOME}/.config/opencode/skills"
SKILLS_DIR="$REPO_ROOT/skills"
if [[ -d "$SKILLS_DIR" ]]; then
    mkdir -p "$OC_SKILLS"
    linked=0
    for dir in "$SKILLS_DIR"/*/; do
        name=$(basename "$dir")
        target="$OC_SKILLS/$name"
        if [[ ! -e "$target" ]]; then
            ln -sf "$dir" "$target" 2>/dev/null && linked=$((linked+1)) || true
        fi
    done
    echo "  $linked skills linked."
fi

# Verify
if ! $NOVERIFY; then
    echo ""
    echo "Running smoke test..."
    cd "$REPO_ROOT"
    $PY scripts/test-smoke-server.py && \
        echo "  Server smoke test passed." || \
        echo "  Smoke test had issues (server may need dependencies)."
fi

# Summary
echo ""
echo "============================================"
echo "  INSTALL COMPLETE"
echo "============================================"
echo ""
echo "  Repo:   $REPO_ROOT"
echo "  Python: $PY $PY_VER"
echo "  Server: $REPO_ROOT/scripts/tools-mcp-server.py"
echo ""
echo "  To start: python $REPO_ROOT/scripts/tools-mcp-server.py"
echo "  To test:  python $REPO_ROOT/scripts/test-smoke-server.py"
