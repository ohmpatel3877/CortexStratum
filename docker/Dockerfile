# opencode-container-server — Self-Contained Build
# Works standalone: just need this file, no repo needed.
#   docker build -t opencode-server .
#   docker run -d --name opencode-server -p 3100:3100 opencode-server
#
# Security: runs as non-root 'appuser' with pinned versions.

FROM node:22-bookworm-slim

LABEL description="opencode-container-server — 68-tool MCP server + OpenCode CLI"
LABEL org.opencontainers.image.source="https://github.com/ohmpatel3877/ai-memory-core"
LABEL org.opencontainers.image.title="opencode-container-server"

# ─── System deps ──────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.* python3-pip python3-venv curl ca-certificates git jq \
    && rm -rf /var/lib/apt/lists/*

# ─── Create non-root user ─────────────────────────────────────────
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /usr/sbin/nologin appuser

# ─── Install OpenCode CLI (pinned version) ────────────────────────
RUN npm install -g @opencode/cli@1.11.2

# ─── Clone ai-memory-core (pinned to latest commit) ───────────────
WORKDIR /app
RUN git clone --depth 1 https://github.com/ohmpatel3877/ai-memory-core.git /tmp/repo && \
    cp -r /tmp/repo/scripts /app/scripts && \
    cp -r /tmp/repo/skills /app/skills && \
    cp -r /tmp/repo/data /app/data && \
    rm -rf /tmp/repo

# Install pinned Python dependencies
RUN pip install --break-system-packages pydantic==2.5.0 httpx==0.25.0 2>/dev/null || \
    python3 -m pip install --no-cache-dir pydantic==2.5.0 httpx==0.25.0

# ─── Set ownership ────────────────────────────────────────────────
RUN chown -R appuser:appgroup /app

# ─── Entrypoint (inline — no external script needed) ──────────────
RUN echo '#!/usr/bin/env bash
set -Eeuo pipefail
MODE="${1:-server}"
case "$MODE" in
  server)
    exec python3 /app/scripts/tools-mcp-server.py
    ;;
  health)
    python3 -c "import json; t=json.load(open('"'/app/data/tool-inventory.json'"')); print(f"'"'"'"'"'"'"'"' {len(t)} tools ready'"'"'"'"'"'"'"'")"
    echo "Memory: local BM25 search"
    echo "OK"
    ;;
  shell)
    exec /bin/bash
    ;;
  *)
    echo "Usage: docker run opencode-server [server|shell|health]"
    exit 1
    ;;
esac' > /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 3100
USER appuser
ENTRYPOINT ["/entrypoint.sh"]
CMD ["server"]
