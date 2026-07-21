#!/usr/bin/env python3
"""Check merged and deprecated tools."""

import json
import os
import subprocess
import sys

r = os.path.join(os.path.dirname(os.path.abspath(__file__)))
result = subprocess.run(
    [sys.executable, os.path.join(r, "tools-mcp-server.py"), "--list-tools"],
    capture_output=True,
    text=True,
    timeout=15,
)
tools = json.loads(result.stdout)

merged = [t for t in tools if "MERGED" in t.get("description", "")]
deprecated = [t for t in tools if "DEPRECATED" in t.get("description", "")]

print("Total tools:", len(tools))
print()
print(f"Merged tools ({len(merged)}):")
for t in merged:
    print("  {0}: {1}".format(t["name"], t["description"][:60]))
print()
print(f"Deprecated ({len(deprecated)}):")
for t in deprecated:
    print("  {0}".format(t["name"]))
print()
tool_count_no_dep = len(tools) - len(deprecated)
print(f"Active (non-deprecated) tools: {tool_count_no_dep}")
print(f"Net reduction potential: {len(deprecated)} more to remove")
