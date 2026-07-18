#!/usr/bin/env python3
"""Phase A: Tool consolidation — status, joint, beam merges + deprecations."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(ROOT, "scripts", "tools-mcp-server.py")

with open(SERVER, encoding="utf-8") as f:
    content = f.read()

changes = 0

# ── A1: Deprecate individual status tools ──
status_map = {
    "read_compact_status": "use read_phase_status domain=compact",
    "read_mutate_status": "use read_phase_status domain=mutation",
    "read_audit_status": "use read_phase_status domain=audit",
    "read_consolidation_status": "use read_phase_status domain=consolidation",
}
for tool, msg in status_map.items():
    idx = content.find('"' + tool + '"')
    if idx > 0:
        desc_start = content.find('"description"', idx, idx + 200)
        if desc_start > 0:
            val_start = content.find('"', desc_start + 14) + 1
            val_end = content.find('"', val_start)
            old_desc = content[val_start:val_end]
            if "[DEPRECATED" not in old_desc:
                content = (
                    content[:val_start]
                    + "[DEPRECATED - " + msg + "]"
                    + content[val_end:]
                )
                changes += 1
                print(f"  Deprecated {tool}")

# ── Add merged read_phase_status ──
phase_tool = """
    {"name": "read_phase_status", "description": "MERGED — Get status for any domain: compact, mutation, audit, consolidation.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"domain": {"type": "string", "default": "compact", "enum": ["compact", "mutation", "audit", "consolidation"]}}, "required": ["domain"]}},
"""
if "read_phase_status" not in content:
    anchor = "read_consolidation_status"
    idx = content.find(anchor)
    if idx > 0:
        end = content.find("}", content.find("}", idx) + 1) + 1
        content = content[:end] + phase_tool + content[end:]
        changes += 1
        print("  Added read_phase_status")

# ── A2: Deprecate individual joint tools ──
joint_map = {
    "read_sim_mech_fastener_shear": "use read_sim_mech_joint type=fastener",
    "read_sim_mech_bolt_torque": "use read_sim_mech_joint type=bolt",
    "read_sim_mech_bonded_joint": "use read_sim_mech_joint type=bonded",
}
for tool, msg in joint_map.items():
    idx = content.find('"' + tool + '"')
    if idx > 0:
        desc_start = content.find('"description"', idx, idx + 200)
        if desc_start > 0:
            val_start = content.find('"', desc_start + 14) + 1
            val_end = content.find('"', val_start)
            old_desc = content[val_start:val_end]
            if "[DEPRECATED" not in old_desc:
                content = (
                    content[:val_start]
                    + "[DEPRECATED - " + msg + "]"
                    + content[val_end:]
                )
                changes += 1
                print(f"  Deprecated {tool}")

# ── Add merged joint tool ──
joint_tool = """
    {"name": "read_sim_mech_joint", "description": "MERGED — Joint analysis: type=[fastener|bolt|bonded]. Replaces 3 tools.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"type": {"type": "string", "enum": ["fastener", "bolt", "bonded"]}, "force": {"type": "number"}, "area": {"type": "number"}, "num_fasteners": {"type": "integer", "default": 1}, "K": {"type": "number", "default": 0.2}, "D": {"type": "number"}, "F": {"type": "number"}, "width": {"type": "number"}, "overlap_length": {"type": "number"}}, "required": ["type"]}},
"""
if "read_sim_mech_joint" not in content:
    anchor = "read_sim_mech_bonded_joint"
    idx = content.find(anchor)
    if idx > 0:
        end = content.find("}", content.find("}", idx) + 1) + 1
        content = content[:end] + joint_tool + content[end:]
        changes += 1
        print("  Added read_sim_mech_joint")

# ── A3: Deprecate individual beam tools ──
beam_map = {
    "read_sim_mech_stress": "use read_sim_mech_beam_analysis calculate=stress",
    "read_sim_mech_shear": "use read_sim_mech_beam_analysis calculate=shear",
    "read_sim_mech_deflection": "use read_sim_mech_beam_analysis calculate=deflection",
}
for tool, msg in beam_map.items():
    idx = content.find('"' + tool + '"')
    if idx > 0:
        desc_start = content.find('"description"', idx, idx + 200)
        if desc_start > 0:
            val_start = content.find('"', desc_start + 14) + 1
            val_end = content.find('"', val_start)
            old_desc = content[val_start:val_end]
            if "[DEPRECATED" not in old_desc:
                content = (
                    content[:val_start]
                    + "[DEPRECATED - " + msg + "]"
                    + content[val_end:]
                )
                changes += 1
                print(f"  Deprecated {tool}")

# ── Add merged beam tool ──
beam_tool = """
    {"name": "read_sim_mech_beam_analysis", "description": "MERGED — Beam analysis: calculate=[stress|shear|deflection|all]. Replaces 3 tools.", "permission": "read", "annotations": A(False), "inputSchema": {"type": "object", "properties": {"calculate": {"type": "string", "default": "all", "enum": ["stress", "shear", "deflection", "all"]}, "moment": {"type": "number"}, "distance_neutral": {"type": "number"}, "I": {"type": "number"}, "shear_force": {"type": "number"}, "Q": {"type": "number"}, "width": {"type": "number"}, "load": {"type": "number"}, "length": {"type": "number"}, "E": {"type": "number"}}, "required": []}},
"""
if "read_sim_mech_beam_analysis" not in content:
    anchor = "read_sim_mech_deflection"
    idx = content.find(anchor)
    if idx > 0:
        end = content.find("}", content.find("}", idx) + 1) + 1
        content = content[:end] + beam_tool + content[end:]
        changes += 1
        print("  Added read_sim_mech_beam_analysis")

with open(SERVER, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\nPhase A complete: {changes} changes to {SERVER}")
