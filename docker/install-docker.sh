#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# install-docker.sh — Install Docker on any OS (if not present)
# ─────────────────────────────────────────────────────────────────────
# Detects OS, installs Docker using the official method, verifies it.
# Safe to run on systems that already have Docker.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/ohmpatel3877/CortexStratum/main/docker/install-docker.sh | bash
#   # or:
#   bash docker/install-docker.sh
# ─────────────────────────────────────────────────────────────────────

set -Eeuo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}▶${NC} $1"; }
ok()    { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
fail()  { echo -e "${RED}✗${NC} $1"; exit 1; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}   Docker Installer — opencode-container-server ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ─── Detect OS ─────────────────────────────────────────────────────
OS="$(uname -s)"
ARCH="$(uname -m)"
info "Detected: $OS $ARCH"

# ─── Check if Docker already works ────────────────────────────────
if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
  ok "Docker already installed and running ($(docker --version))"
  exit 0
fi

# ─── Docker exists but not running (usually Linux rootless) ───────
if command -v docker &>/dev/null; then
  warn "Docker binary found but daemon not running. Attempting to start..."
  if systemctl start docker 2>/dev/null; then
    ok "Docker started via systemctl"
    exit 0
  elif sudo dockerd &>/dev/null &; then
    sleep 3
    ok "Docker daemon started"
    exit 0
  else
    warn "Could not start Docker. Trying to reinstall..."
  fi
fi

# ─── Install per OS ────────────────────────────────────────────────
case "$OS" in
  Linux)
    info "Installing Docker via official script..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "${USER}" || true
    sudo systemctl enable docker 2>/dev/null || true
    sudo systemctl start docker 2>/dev/null || true
    ;;

  Darwin)
    info "Installing Docker Desktop for Mac..."
    if command -v brew &>/dev/null; then
      warn "Trying Homebrew method first..."
      brew install --cask docker 2>/dev/null && ok "Docker installed via Homebrew" || {
        warn "Homebrew failed. Downloading Docker Desktop directly..."
        case "$ARCH" in
          arm64) URL="https://desktop.docker.com/mac/main/arm64/Docker.dmg" ;;
          *)     URL="https://desktop.docker.com/mac/main/amd64/Docker.dmg" ;;
        esac
        curl -fsSL "$URL" -o /tmp/Docker.dmg
        sudo hdiutil attach /tmp/Docker.dmg -quiet
        sudo cp -R "/Volumes/Docker/Docker.app" /Applications
        sudo hdiutil detach /Volumes/Docker -quiet
      }
    else
      case "$ARCH" in
        arm64) URL="https://desktop.docker.com/mac/main/arm64/Docker.dmg" ;;
        *)     URL="https://desktop.docker.com/mac/main/amd64/Docker.dmg" ;;
      esac
      info "Downloading Docker Desktop from $URL..."
      curl -fsSL "$URL" -o /tmp/Docker.dmg
      sudo hdiutil attach /tmp/Docker.dmg -quiet
      sudo cp -R "/Volumes/Docker/Docker.app" /Applications
      sudo hdiutil detach /Volumes/Docker -quiet
    fi
    warn "Docker Desktop installed to /Applications. Launch it manually to complete setup."
    open /Applications/Docker.app
    info "Waiting for Docker to start (this may take a minute)..."
    for i in $(seq 1 30); do
      docker info &>/dev/null && break
      sleep 2
    done
    ;;

  *)
    fail "Unsupported OS: $OS. Install Docker manually: https://docs.docker.com/engine/install/"
    ;;
esac

# ─── Verify ────────────────────────────────────────────────────────
sleep 2
if docker info &>/dev/null; then
  ok "Docker installed: $(docker --version)"
  ok "Docker Compose: $(docker compose version 2>/dev/null || echo 'bundled')"
else
  warn "Docker installed but not running. You may need to:"
  warn "  - Log out and back in (Linux group change)"
  warn "  - Launch Docker Desktop (Mac)"
  warn "  - Run: sudo systemctl start docker"
  warn "Then re-run this setup."
fi
