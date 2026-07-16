# ai-memory-core — Container Image
# Bundles the 68-tool MCP server + OpenCode CLI + all dependencies.
# Designed for Portainer-managed or standalone deployment.

FROM node:22-bookworm-slim

LABEL description="ai-memory-core — 68-tool MCP server, skill router, task orchestrator"
LABEL maintainer="Ohm Patel"
LABEL org.opencontainers.image.source="https://github.com/ohmpatel3877/ai-memory-core"

# ─── System Dependencies ─────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    ca-certificates \
    git \
    jq \
    && rm -rf /var/lib/apt/lists/*

# ─── Install OpenCode CLI ────────────────────────────────────────
RUN npm install -g @opencode/cli@latest

# ─── App Setup ───────────────────────────────────────────────────
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --production
COPY . .

# ─── Python deps for MCP server ──────────────────────────────────
RUN python3 -m venv /app/venv && \
    /app/venv/bin/pip install --no-cache-dir pydantic httpx

# ─── Entrypoint ──────────────────────────────────────────────────
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3100 8080

ENTRYPOINT ["/entrypoint.sh"]
