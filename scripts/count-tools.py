#!/usr/bin/env python3
"""
count-tools.py — Derive the AUTHORITATIVE tool counts from source, so docs never drift.

Two numbers matter and they are NOT the same:
  discoverable : tools returned by the MCP `tools/list` method (what a client sees)
  dispatchable : discoverable + module-dispatched tools callable by name in handle_tool_call

Run:  python scripts/count-tools.py            # human summary
      python scripts/count-tools.py --json     # machine-readable
"""
from __future__ import annotations
import importlib.util as _util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _load_server():
    spec = _util.spec_from_file_location("tools_mcp_server", SCRIPTS / "tools-mcp-server.py")
    mod = _util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _module_tool_names() -> dict[str, set[str]]:
    """Scan module files for REAL tool definitions (dispatch-table keys), not
    enum/data 'name' values. A real module tool appears as a key in a
    *_handle_tool_call dispatch dict: '"tool_name": lambda a: ...'."""
    out: dict[str, set[str]] = {}
    seen: set[Path] = set()
    for f in sorted(SCRIPTS.glob("*module*.py")):
        if f in seen:
            continue
        seen.add(f)
        txt = f.read_text(encoding="utf-8", errors="replace")
        # dispatch-table entries: "name": lambda  (the authoritative tool set)
        names = set(re.findall(r'"([a-z0-9_]+)"\s*:\s*lambda\b', txt))
        if names:
            out[f.name] = names
    return out


def counts() -> dict:
    server = _load_server()
    discoverable = {t["name"] for t in server.TOOLS}
    modules = _module_tool_names()
    module_names: set[str] = set().union(*modules.values()) if modules else set()
    dispatchable = discoverable | module_names
    return {
        "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "discoverable": len(discoverable),
        "dispatchable": len(dispatchable),
        "module_only": len(module_names - discoverable),
        "modules": {k: len(v) for k, v in modules.items()},
    }


def main() -> None:
    c = counts()
    if "--json" in sys.argv:
        print(json.dumps(c, indent=2))
        return
    print(f"CortexStratum v{c['version']}")
    print(f"  discoverable (tools/list) : {c['discoverable']}")
    print(f"  dispatchable (total)      : {c['dispatchable']}")
    print(f"  module-only (hidden)      : {c['module_only']}")
    if c["module_only"]:
        print(f"  WARNING: {c['module_only']} module tools are dispatchable but NOT in tools/list")
    for name, n in c["modules"].items():
        print(f"    {name}: {n}")


if __name__ == "__main__":
    main()
