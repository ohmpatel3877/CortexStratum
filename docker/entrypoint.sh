#!/usr/bin/env bash
set -Eeuo pipefail
MODE="${1:-server}"
case "$MODE" in
  server)
    exec python3 /app/scripts/tools-mcp-server.py
    ;;
  health)
    python3 -c "import json; t=json.load(open('/app/data/tool-inventory.json')); print(str(len(t)) + ' tools ready')"
    echo "Memory: SQLite+FTS5 search"
    echo "OK"
    ;;
  shell)
    exec /bin/bash
    ;;
  *)
    echo "Usage: docker run opencode-server [server|shell|health]"
    exit 1
    ;;
esac
