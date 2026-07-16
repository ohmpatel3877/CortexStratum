#!/usr/bin/env bash
# ai-memory-core container entrypoint
# Starts MCP server, optionally registers with OpenCode, runs health check.
set -Eeuo pipefail

MODE="${1:-server}"  # server | configure | shell | health | help
shift || true

# ─── OpenCode Zen API configuration ────────────────────────────
if [ -n "${OPENCODE_ZEN_API_KEY:-}" ]; then
  export OPENCODE_API_KEY="$OPENCODE_ZEN_API_KEY"
  # Write local opencode config for in-container CLI use
  mkdir -p /root/.config/opencode
  cat > /root/.config/opencode/opencode.json << JSONEOF
{
  "zen": {
    "apiKey": "${OPENCODE_ZEN_API_KEY}",
    "baseUrl": "${OPENCODE_ZEN_BASE_URL:-https://api.opencode.ai}",
    "host": "${OPENCODE_HOST:-patelserver}",
    "deploymentId": "${OPENCODE_DEPLOYMENT_ID:-patelserver-docker}"
  },
  "mcpServers": {
    "ai-memory-core": {
      "name": "ai-memory-core",
      "description": "68-tool MCP memory & orchestration server",
      "command": "python3",
      "args": ["/app/scripts/tools-mcp-server.py"]
    }
  }
}
JSONEOF
  echo "    OpenCode Zen: configured (${OPENCODE_ZEN_BASE_URL:-https://api.opencode.ai})"
fi

case "$MODE" in
  server)
    echo "🧠 ai-memory-core MCP server starting..."
    echo "    MEM0_API_KEY: ${MEM0_API_KEY:+set $(echo "$MEM0_API_KEY" | cut -c1-4)...}"
    echo "    Mode: MCP over stdio"

    # Run the 68-tool MCP server
    exec python3 /app/scripts/tools-mcp-server.py
    ;;

  configure)
    echo "=== OpenCode Zen Configuration ==="
    if [ -n "${OPENCODE_ZEN_API_KEY:-}" ]; then
      echo "  API Key: ${OPENCODE_ZEN_API_KEY:0:8}..."
      echo "  Base URL: ${OPENCODE_ZEN_BASE_URL:-https://api.opencode.ai}"
      echo "  Host: ${OPENCODE_HOST:-patelserver}"
      echo "  Config written to: /root/.config/opencode/opencode.json"
      cat /root/.config/opencode/opencode.json
    else
      echo "  No OPENCODE_ZEN_API_KEY set."
      echo "  Get one at https://opencode.ai and set it in your .env:"
      echo "    OPENCODE_ZEN_API_KEY=your-key-here"
      echo "    OPENCODE_ZEN_BASE_URL=https://api.opencode.ai"
    fi
    ;;

  shell)
    echo "🧠 ai-memory-core shell"
    echo "    OpenCode Zen: ${OPENCODE_ZEN_API_KEY:+connected}${OPENCODE_ZEN_API_KEY:-not configured}"
    echo "    Commands: opencode, python3 tools-mcp-server.py"
    exec /bin/bash "$@"
    ;;

  health)
    echo "=== ai-memory-core health check ==="
    echo "Node: $(node --version)"
    echo "Python: $(python3 --version)"
    echo "OpenCode: $(opencode --version 2>/dev/null || echo 'not found')"
    echo "OpenCode Zen: ${OPENCODE_ZEN_API_KEY:+configured}${OPENCODE_ZEN_API_KEY:-not configured}"
    echo "MCP tools available:"
    python3 -c "
import json
with open('/app/data/tool-inventory.json') as f:
    tools = json.load(f)
print(f'  {len(tools)} registered tools')
for t in tools[:5]:
    print(f'    {t[\"name\"]}')
print('    ...')
"
    echo "MEM0_API_KEY: ${MEM0_API_KEY:+yes}${MEM0_API_KEY:-no}"
    echo "Status: OK"
    ;;

  *)
    echo "Usage: docker run ai-memory-core [server|configure|shell|health]"
    echo ""
    echo "  server     Start MCP server (default)"
    echo "  configure  Print OpenCode Zen config"
    echo "  shell      Interactive shell"
    echo "  health     Run diagnostics"
    exit 1
    ;;
esac
