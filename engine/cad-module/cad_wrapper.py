"""CAD module MCP dispatch wrapper."""

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent


def _load_cad_validator():
    sys.path.insert(0, str(BASE))
    import cad_validator as cv

    return cv


def _load_fea_analyzer():
    sys.path.insert(0, str(BASE))
    import fea_analyzer as fa

    return fa


def handle_tool_call(name, args):
    if name == "read_cad_validate_scad":
        cv = _load_cad_validator()
        filepath = args.get("filepath", "")
        if not filepath:
            return {"error": "Missing required argument: filepath", "status": "error"}
        issues = cv.validate_scad(filepath)
        return {
            "filepath": filepath,
            "issues": issues,
            "status": "valid" if not issues else "issues_found",
        }
    elif name == "read_cad_beam_stress":
        fa = _load_fea_analyzer()
        result = fa.rect_beam_stress(
            args.get("force_N", 0),
            args.get("length_mm", 0),
            args.get("width_mm", 0),
            args.get("height_mm", 0),
            args.get("yield_MPa", 40),
        )
        return {
            "stress_MPa": result[0],
            "safety_factor": result[1],
            "deflection_mm": result[2],
        }
    return {"error": f"Unknown CAD tool: {name}"}
