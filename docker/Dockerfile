# opencode-container-server — Self-Contained Build
# Works standalone: just need this file, no repo needed.
#   docker build -t opencode-server .
#   docker run -d --name opencode-server -p 3100:3100 opencode-server

FROM node:22-bookworm-slim

LABEL description="opencode-container-server — 68-tool MCP server + OpenCode CLI"
LABEL org.opencontainers.image.source="https://github.com/ohmpatel3877/cortex-stratum"
LABEL org.opencontainers.image.title="opencode-container-server"

# ─── System deps ──────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv curl ca-certificates git jq \
    && rm -rf /var/lib/apt/lists/*

# ─── Install OpenCode CLI ─────────────────────────────────────────
RUN npm install -g @opencode/cli@latest

# ─── Clone cortex-stratum (always pulls latest) ───────────────────
WORKDIR /app
RUN git clone --depth 1 https://github.com/ohmpatel3877/cortex-stratum.git /tmp/repo && \
    cp -r /tmp/repo/scripts /app/scripts && \
    cp -r /tmp/repo/skills /app/skills && \
    cp -r /tmp/repo/data /app/data && \
    cp -r /tmp/repo/.mem0.md /app/ && \
    rm -rf /tmp/repo
RUN pip install --break-system-packages pydantic httpx 2>/dev/null || \
    python3 -m pip install --no-cache-dir pydantic httpx

# ─── Entrypoint (inline — no external script needed) ──────────────
RUN echo '#!/usr/bin/env bash
set -Eeuo pipefail
MODE="${1:-server}"
case "$MODE" in
  server)
    exec python3 /app/scripts/tools-mcp-server.py
    ;;
  health)
    python3 -c "import json; t=json.load(open('\''/app/data/tool-inventory.json'\'')); print(f'\''{len(t)} tools ready'\'')"
    echo "MEM0_API_KEY: ${MEM0_API_KEY:+yes}${MEM0_API_KEY:-no}"
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
ENTRYPOINT ["/entrypoint.sh"]
CMD ["server"]
