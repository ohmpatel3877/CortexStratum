#!/usr/bin/env python3
"""Add merged tool definitions to tools-mcp-server.py."""
import os

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools-mcp-server.py")
with open(p, encoding="utf-8") as f:
    content = f.read()

# Tools to insert and their anchors (insert AFTER anchor's closing brace)
insertions = [
    ("read_audit_status", """
    {"name": "read_phase_status", "description": "MERGED - Get status for any domain: compact, mutation, audit, consolidation.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"domain": {"type": "string", "default": "compact", "enum": ["compact", "mutation", "audit", "consolidation"]}}, "required": ["domain"]}},
"""),
    ("read_sim_mech_bonded_joint", """
    {"name": "read_sim_mech_joint", "description": "MERGED - Joint analysis: type=[fastener,bolt,bonded]. Replaces 3 tools.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"type": {"type": "string", "enum": ["fastener", "bolt", "bonded"]}, "force": {"type": "number"}, "area": {"type": "number"}, "num_fasteners": {"type": "integer", "default": 1}, "K": {"type": "number", "default": 0.2}, "D": {"type": "number"}, "F": {"type": "number"}, "width": {"type": "number"}, "overlap_length": {"type": "number"}}, "required": ["type"]}},
"""),
    ("read_sim_mech_deflection", """
    {"name": "read_sim_mech_beam_analysis", "description": "MERGED - Beam analysis: calculate=[stress,shear,deflection,all]. Replaces 3 tools.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"calculate": {"type": "string", "default": "all", "enum": ["stress", "shear", "deflection", "all"]}, "moment": {"type": "number"}, "distance_neutral": {"type": "number"}, "I": {"type": "number"}, "shear_force": {"type": "number"}, "Q": {"type": "number"}, "width": {"type": "number"}, "load": {"type": "number"}, "length": {"type": "number"}, "E": {"type": "number"}}, "required": []}},
"""),
]

for anchor, new_tool in insertions:
    if new_tool.strip()[:20] in content:
        print(f"  Skipped {anchor}: already inserted")
        continue
    idx = content.find('"' + anchor + '"')
    if idx < 0:
        print(f"  ERROR: anchor {anchor} not found")
        continue
    # Find the closing of this tool definition
    end = content.find("}", idx)
    end = content.find("}", end + 1) + 1
    content = content[:end] + "," + new_tool + content[end:]
    print(f"  Inserted after {anchor}")

with open(p, "w", encoding="utf-8") as f:
    f.write(content)
print("\nDone")
