#!/usr/bin/env bash
# ai-memory-core container entrypoint
# Starts MCP server, optionally registers with OpenCode, runs health check.
set -Eeuo pipefail

MODE="${1:-server}"  # server | shell | help
shift || true

case "$MODE" in
  server)
    echo "🧠 ai-memory-core MCP server starting..."
    echo "    MEM0_API_KEY: ${MEM0_API_KEY:+set $(echo "$MEM0_API_KEY" | cut -c1-4)...}"
    echo "    Mode: MCP over stdio"

    # Run the 68-tool MCP server
    exec python3 /app/scripts/tools-mcp-server.py
    ;;

  shell)
    echo "🧠 ai-memory-core shell"
    echo "    Type 'opencode' to launch, 'python tools-mcp-server.py' for MCP"
    exec /bin/bash "$@"
    ;;

  health)
    echo "=== ai-memory-core health check ==="
    echo "Node: $(node --version)"
    echo "Python: $(python3 --version)"
    echo "OpenCode: $(opencode --version 2>/dev/null || echo 'not found')"
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
    echo "Usage: docker run ai-memory-core [server|shell|health]"
    exit 1
    ;;
esac
