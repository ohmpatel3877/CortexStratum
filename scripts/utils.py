#!/usr/bin/env python3
"""Shared utilities for CortexStratum modules.

Eliminates the 15+ duplicate copies of _load_json/_save_json across modules.
All modules should import from here instead of defining their own.
"""

import json, os
from pathlib import Path

def load_json(path, default=None):
    """Load JSON from file. Returns default on any error (file not found, corrupt, etc.)."""
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return default if default is not None else {}

def save_json(path, data):
    """Save JSON to file atomically (write to temp, then rename)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.parent / (p.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)

def ensure_dir(path):
    """Ensure a directory exists."""
    os.makedirs(path, exist_ok=True)
    return path
