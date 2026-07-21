"""Electrical module MCP dispatch wrapper."""

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent


def _load_circuit():
    sys.path.insert(0, str(BASE))
    import circuit_designer as cd

    return cd


def handle_tool_call(name, args):
    if name == "read_electrical_design_circuit":
        cd = _load_circuit()
        components = args.get("components", [])
        connections = args.get("connections", [])
        circuit = cd.Circuit(name=args.get("name", "unnamed_circuit"))
        for c in components:
            circuit.add_component(c.get("name", "?"), c.get("type", "generic"))
        for conn in connections:
            circuit.connect(conn.get("from", ""), conn.get("to", ""))
        return {
            "status": "designed",
            "components": len(components),
            "connections": len(connections),
        }
    elif name == "read_electrical_analyze_circuit":
        cd = _load_circuit()
        data = json.loads(args.get("circuit_json", "{}"))
        circuit = cd.Circuit()
        for c in data.get("components", []):
            circuit.add_component(c.get("name", "?"), c.get("type", "generic"))
        for conn in data.get("connections", []):
            circuit.connect(conn.get("from", ""), conn.get("to", ""))
        return {
            "status": "analyzed",
            "components": len(circuit.components),
            "connections": len(circuit.connections),
        }
    return {"error": f"Unknown electrical tool: {name}"}
