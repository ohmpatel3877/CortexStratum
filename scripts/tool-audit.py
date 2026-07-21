#!/usr/bin/env python3
"""Tool inventory audit — consolidation wins, light tools, improvement candidates."""

import json
import os
import subprocess
import sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
result = subprocess.run(
    [sys.executable, os.path.join(SCRIPTS, "tools-mcp-server.py"), "--list-tools"],
    capture_output=True,
    text=True,
    timeout=15,
)
tools = json.loads(result.stdout)

# Group by domain
domains = {}
for t in tools:
    name = t["name"]
    parts = name.split("_")
    domain = parts[1] if len(parts) >= 2 and parts[0] in ("read", "write") else parts[0]
    domains.setdefault(domain, []).append(name)

print("=== Tools by Domain ===")
for d in sorted(domains):
    print(f"  {d:20s} {len(domains[d]):3d} tools")
print(f"\n  TOTAL: {len(tools)} tools across {len(domains)} domains")

# Deprecated tools
print("\n=== Consolidated (Deprecated) Tools ===")
dep = [t for t in tools if "deprecated" in t.get("description", "").lower()]
if dep:
    for d in dep:
        print(f"  {d['name']:45s} → {d['description'][:50]}")
else:
    print("  (none)")

# Light tools: status-only with no required params
print("\n=== Lightweight Tools (status-only, empty schemas) ===")
light = [
    t
    for t in tools
    if not t.get("inputSchema", {}).get("required", []) and "status" in t["name"]
]
for t in light:
    print(f"  {t['name']:45s} (no inputs)")
print(f"  Found: {len(light)}")

# Tools that could be merged: single-formula sim tools
print("\n=== Merge Candidates (single-formula tools) ===")
sim_mech = [
    t
    for t in tools
    if "sim_mech" in t["name"]
    and t["name"]
    not in (
        "read_sim_mech_fatigue",
        "read_sim_mech_buckle",
        "read_sim_mech_moi",
        "read_sim_mech_fatigue_goodman",
        "read_sim_mech_fatigue_miner",
    )
    and "deprecated" not in t.get("description", "").lower()
]
print(f"  Standalone sim_mech tools: {len(sim_mech)}")
for t in sim_mech:
    print(f"    {t['name']}")

# Sensory tools that could merge further
sensory = [
    t
    for t in tools
    if "sensory" in t["name"] and "deprecated" not in t.get("description", "").lower()
]
print(f"\n  Sensory tools (non-deprecated): {len(sensory)}")
for t in sensory:
    print(f"    {t['name']}")

print("\n=== Recommendations ===")
print("  1. Merge status-only tools into one read_phase_status (saves ~4 defs)")
print("  2. Merge standalone fastener/bolt/bonded into read_sim_mech_joint")
print(
    "  3. Merge force tools (deflection, shear, stress) into read_sim_mech_beam_analysis"
)
print("  4. Merge web tools further: api_request, fetch_rss, search into fetch")
print("  5. Externalize sensory/coder/devops/gamedev/audio/art/lit as separate MCPs")
print("  6. Remove deprecated tools after migration period")
