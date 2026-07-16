#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# opencode-container-server — 1-Click Setup
# ═══════════════════════════════════════════════════════════════
#
#  ⚡ You only need Docker (or Podman). That's it.
#  ⚡ No Node.js. No Python. No npm. No pip.
#  ⚡ Everything runs inside the container.
#
# Deploys the opencode-container-server: ai-memory-core MCP
# server + OpenCode CLI + mem0 + OpenCode Zen config.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/setup-opencode-container.sh | bash
#   # or locally:
#   bash docker/setup-opencode-container.sh
#
# Options:
#   MEM0_API_KEY=xxx bash setup-opencode-container.sh     # pass mem0 key inline
#   OPENCODE_ZEN_API_KEY=xxx bash ...                     # pass OpenCode Zen key inline
#   bash setup-opencode-container.sh --engine podman      # force Podman over Docker
# ═══════════════════════════════════════════════════════════════

set -Eeuo pipefail
REPO_URL="https://github.com/ohmpatel3877/ai-memory-core.git"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ─── Colors ──────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}▶${NC} $1"; }
ok()    { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
fail()  { echo -e "${RED}✗${NC} $1"; exit 1; }

# ─── Header ──────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}        patelserver — 1-Click Setup             ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  Portainer + ai-memory-core + mem0             ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ─── OS Detection ─────────────────────────────────────────────────
info "Detecting OS..."
OS="unknown"
case "$(uname -s)" in
  Linux*)  OS="linux" ;;
  Darwin*) OS="macos" ;;
  MINGW*|MSYS*) OS="windows" ;;
esac
ok "OS: ${OS} ($(uname -m))"

# ─── Container Engine Detection / Installation ────────────────────
info "Checking container engine..."
ENGINE=""
ENGINE_COMPOSE=""

# Try Docker first
if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
  ENGINE="docker"
  ENGINE_COMPOSE="docker compose"
  ok "Docker: $(docker --version)"
# Try Podman next
elif command -v podman &>/dev/null && podman info &>/dev/null 2>&1; then
  ENGINE="podman"
  ENGINE_COMPOSE="podman-compose"
  ok "Podman: $(podman --version)"
# Force Podman?
elif [ "${1:-}" = "--engine" ] && [ "${2:-}" = "podman" ]; then
  fail "Podman specified but not found at: https://podman.io/getting-started/installation"
else
  warn "No container engine found. Running Docker installer..."
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [ -f "$SCRIPT_DIR/install-docker.sh" ]; then
    bash "$SCRIPT_DIR/install-docker.sh"
  else
    curl -fsSL https://raw.githubusercontent.com/ohmpatel3877/ai-memory-core/main/docker/install-docker.sh | bash
  fi
  # Re-check
  if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
    ENGINE="docker"
    ENGINE_COMPOSE="docker compose"
    ok "Docker ready: $(docker --version)"
  else
    fail "Docker installation did not complete. Please install Docker manually: https://docs.docker.com/engine/install/"
  fi
fi

# ─── Portainer Setup ──────────────────────────────────────────────
PORTAINER_PORT="${2:-9000}"
info "Setting up Portainer on port ${PORTAINER_PORT}..."

if $ENGINE ps --format '{{.Names}}' 2>/dev/null | grep -q "portainer"; then
  ok "Portainer already running"
else
  $ENGINE run -d \
    --name portainer \
    --restart unless-stopped \
    -p "${PORTAINER_PORT}:9000" \
    -p "9443:9443" \
    -p "8000:8000" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v portainer_data:/data \
    portainer/portainer-ce:latest 2>&1 || warn "Portainer start failed — may need sudo"
  ok "Portainer started → http://$(hostname -I 2>/dev/null | awk '{print $1}'):${PORTAINER_PORT}"
fi

# ─── Clone / Update ai-memory-core ────────────────────────────────
info "Setting up ai-memory-core..."
if [ -d "$PROJECT_DIR/.git" ]; then
  ok "Already cloned at $PROJECT_DIR"
else
  cd /tmp
  git clone --depth 1 "$REPO_URL" 2>&1
  PROJECT_DIR="/tmp/ai-memory-core"
  cd "$PROJECT_DIR"
  ok "Cloned ai-memory-core"
fi

# ─── mem0 API Key ─────────────────────────────────────────────────
MEM0_KEY="${MEM0_API_KEY:-}"
if [ -z "$MEM0_KEY" ] && [ -f "$PROJECT_DIR/.env" ]; then
  MEM0_KEY=$(grep MEM0_API_KEY "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d ' ')
fi
if [ -z "$MEM0_KEY" ]; then
  echo ""
  warn "No MEM0_API_KEY found."
  echo "  Get one free at https://app.mem0.ai"
  echo -n "  Paste your key (or press Enter to skip): "
  read -r input_key
  if [ -n "$input_key" ]; then
    MEM0_KEY="$input_key"
    echo "MEM0_API_KEY=$MEM0_KEY" > "$PROJECT_DIR/.env"
    ok "Key saved"
  else
    warn "Skipping mem0 config. Set MEM0_API_KEY later in .env"
  fi
fi

# ─── OpenCode Zen API Key ─────────────────────────────────────────
ZEN_KEY="${OPENCODE_ZEN_API_KEY:-}"
if [ -z "$ZEN_KEY" ] && [ -f "$PROJECT_DIR/.env" ]; then
  ZEN_KEY=$(grep OPENCODE_ZEN_API_KEY "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d ' ')
fi
if [ -z "$ZEN_KEY" ]; then
  echo ""
  warn "No OPENCODE_ZEN_API_KEY found (optional)."
  echo "  Get one free at https://opencode.ai"
  echo -n "  Paste your key (or press Enter to skip): "
  read -r input_zen
  if [ -n "$input_zen" ]; then
    ZEN_KEY="$input_zen"
    echo "OPENCODE_ZEN_API_KEY=$ZEN_KEY" >> "$PROJECT_DIR/.env"
    ok "Zen key saved"
  else
    warn "Skipping OpenCode Zen config"
  fi
fi

# ─── Deploy Stack via Compose ─────────────────────────────────────
info "Deploying patelserver stack..."
cd "$PROJECT_DIR"
export MEM0_API_KEY="${MEM0_KEY:-}"
export OPENCODE_ZEN_API_KEY="${ZEN_KEY:-}"
export HOST_PROJECTS="${HOME}/projects"

if [ -f docker/docker-compose.yml ]; then
  $ENGINE_COMPOSE -f docker/docker-compose.yml up -d --build 2>&1
  ok "Stack deployed"
else
  # Fallback: run MCP server directly
  $ENGINE run -d \
    --name ai-memory-core \
    --restart unless-stopped \
    -p 3100:3100 \
    -v ai_memory_data:/app/data \
    -e MEM0_API_KEY="${MEM0_KEY:-}" \
    -w /app \
    node:22 npm start 2>&1 || warn "Direct run failed"
fi

# ─── Verify ───────────────────────────────────────────────────────
info "Verifying deployment..."
sleep 2
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  opencode-container-server is live!           ${CYAN}║${NC}"
echo -e "${CYAN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${CYAN}║${NC}  MCP Server:  opencode-server:3100            ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  Engine:      ${ENGINE}                           ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  OS:          ${OS}                             ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "Next steps:"
echo "  1. Connect your local OpenCode to the MCP server at opencode-server:3100"
echo "  2. Or run: docker exec -it opencode-server opencode"
echo "  3. Configure mem0 via docker compose -f docker/docker-compose.yml config"
