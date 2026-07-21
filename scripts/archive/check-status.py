#!/usr/bin/env python3
"""NE-Memory Status Checker — checks local memory store health."""

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
MEMORY_STORE = BASE / "data" / "memory_store.json"

G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
C = "\033[96m"
N = "\033[0m"


def main():
    print(f"{C}=== NE-Memory Status Check ==={N}\n")

    # Memory store
    if MEMORY_STORE.exists():
        try:
            data = json.loads(MEMORY_STORE.read_text(encoding="utf-8"))
            entries = (
                data
                if isinstance(data, list)
                else data.get("memories", data.get("entries", []))
            )
            entry_count = len(entries)
            size_kb = MEMORY_STORE.stat().st_size / 1024
            print(f"  {G}Memory store:{N} {MEMORY_STORE}")
            print(f"  {Y}Entries:{N}     {entry_count}")
            print(f"  {Y}Size:{N}       {size_kb:.1f} KB")
        except (json.JSONDecodeError, OSError) as e:
            print(f"  {R}Memory store corrupted:{N} {e}")
    else:
        print(f"  {Y}Memory store:{N} NOT FOUND at {MEMORY_STORE}")
        print(f"  {Y}Run memory_search.py to initialize.{N}")

    # Agent-Memory-MCP .memory/
    memory_dir = BASE / ".memory"
    if memory_dir.is_dir():
        md_files = list(memory_dir.rglob("*.md")) + list(memory_dir.rglob("*.json"))
        print(f"\n  {G}.memory/ directory:{N} PRESENT ({len(md_files)} files)")
    else:
        print(f"\n  {Y}.memory/ directory:{N} MISSING")

    # NE memory subdir
    ne_dir = memory_dir / "ne"
    if ne_dir.is_dir():
        ne_files = list(ne_dir.iterdir())
        print(f"  {G}.memory/ne/:{N} PRESENT ({len(ne_files)} items)")
    else:
        print(f"  {Y}.memory/ne/:{N} MISSING")

    # Identity directory
    identity_dir = memory_dir / "identity"
    if identity_dir.is_dir():
        id_files = list(identity_dir.rglob("*"))
        print(f"  {G}.memory/identity/:{N} PRESENT ({len(id_files)} files)")
    else:
        print(f"  {Y}.memory/identity/:{N} MISSING")

    print(f"\n{C}=== Status Complete ==={N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
