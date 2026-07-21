"""Test memory search consolidate + dry-run + permission model."""

import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.memory_search import NEMemorySearch

tmpdir = tempfile.mkdtemp()
m = NEMemorySearch(storage_path=tmpdir)
m.add_memory(
    "Test memory one for BM25 search", source="test", metadata={"confidence": 0.9}
)
m.add_memory(
    "Test memory two for BM25 retrieval", source="test", metadata={"confidence": 0.7}
)
m.add_memory(
    "Test memory one for BM25 search", source="manual", metadata={"confidence": 0.5}
)

# Dry run
r = m.consolidate(threshold=0.5, dry_run=True)
assert r["dry_run"], "dry_run flag not returned"
assert r["removed"] > 0 or r["merged"] > 0, "should find duplicates"
print(f"DRY-RUN OK: {r['removed']} removed, {r['merged']} merged")

# Real run
r2 = m.consolidate(threshold=0.5, dry_run=False)
assert not r2["dry_run"]
print(f"CONSOLIDATE OK: {r2['remaining']} remaining")

# Permission model test
from scripts.tools_mcp_server import can_call_tool

ok, _ = can_call_tool("write_memory_add", {"mode": "auto"})
assert not ok, "auto mode should block write_memory_add"
ok, _ = can_call_tool("write_memory_add", {"mode": "interactive"})
assert ok, "interactive mode should allow write_memory_add"
print("PERMISSION MODEL OK")
print("ALL MEMORY ENGINE TESTS PASSED")
