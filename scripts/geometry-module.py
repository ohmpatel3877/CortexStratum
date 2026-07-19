"""
[WIP] geometry-module.py — CortexStratum geometry layer backed by OpenGeometry (Rust/WASM CAD kernel).

WIP STATUS: integrated and PARTIALLY working. Verified-OK ops: primitive, brep, transform.
BROKEN op: boolean (shape.subtract([cutter]) fails with upstream "empty pos matrix"
placement quirk in the Node/WASM path). Boolean is a known future fix (see roadmap F1).
Do NOT treat this module as production-ready. Kept in-tree per operator decision; pushing
as WIP, not as a finished feature.

CortexStratum is pure-stdlib Python; OpenGeometry is an npm/Node/WASM package.
This module shells out to scripts/og-node/opengeometry-shim.mjs (real subprocess,
no mock), parses the JSON it returns. This is the geometry foundation a simulation
engine would build on (B-rep, bounds, booleans) — OpenGeometry is the kernel;
FEA/CFD solvers would sit on top elsewhere.

Ops (all kernel-backed, verified against opengeometry@2.0.11):
  primitive  build Cuboid/Cylinder/Sphere/Wedge -> B-rep (v/e/f) + bounds   [OK]
  brep       raw B-rep topology of a primitive                                  [OK]
  boolean     shape.subtract([cutter]) -> resulting B-rep   [WIP: upstream placement quirk]
  transform   set placement/scale on a shape                                    [OK]
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

_SHIM_DIR = Path(__file__).resolve().parent / "og-node"
_SHIM = _SHIM_DIR / "opengeometry-shim.mjs"
_NODE = "node"


def _call(op: str, args: dict | None = None) -> dict:
    """Run one OpenGeometry op via the Node shim. Returns parsed JSON result."""
    if not _SHIM.exists():
        return {"ok": False, "error": f"shim missing: {_SHIM}"}
    cmd = {"op": op, "args": args or {}}
    try:
        proc = subprocess.run(
            [_NODE, str(_SHIM)],
            input=json.dumps(cmd),
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(_SHIM_DIR),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"OpenGeometry op '{op}' timed out (60s)"}
    except FileNotFoundError:
        return {"ok": False, "error": "node not found on PATH"}
    if proc.returncode != 0 and not proc.stdout.strip():
        return {"ok": False, "error": (proc.stderr or "node exited").strip().splitlines()[0][:200]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": f"bad shim output: {(proc.stdout or proc.stderr)[:200]}"}


def primitive(kind: str = "cuboid", **dims) -> dict:
    return _call("primitive", {"kind": kind, **dims})


def brep(kind: str = "cuboid", **dims) -> dict:
    return _call("brep", {"kind": kind, **dims})


def boolean(mode: str = "subtraction", base: dict | None = None, cutter: dict | None = None) -> dict:
    return _call("boolean", {"mode": mode, "base": base or {}, "cutter": cutter or {}})


def transform(shape: dict | None = None, translate=None, scale=None) -> dict:
    args = {"shape": shape or {}}
    if translate is not None:
        args["translate"] = list(translate)
    if scale is not None:
        args["scale"] = list(scale)
    return _call("transform", args)


HEALTH = {
    "backend": "opengeometry (Rust/WASM CAD kernel, via Node shim)",
    "shim_present": _SHIM.exists(),
    "ops": ["primitive", "brep", "boolean", "transform"],
}


if __name__ == "__main__":
    res = primitive("cuboid", width=2, height=3, depth=4)
    print(json.dumps(res, indent=2))
