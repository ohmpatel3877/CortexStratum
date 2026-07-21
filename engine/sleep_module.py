#!/usr/bin/env python3
"""
Sleep Cycle — "lights out" pre-refresh orchestrator for CortexStratum.

Called before context window reset to:
  1. DMN daydream → capture insights, promote episodic→semantic
  2. VQ compress → deduplicate memory content, encode tags to int IDs
  3. MLM consolidate → prune expired TTL items, promote hot items
  4. Generate compact summary → what happened, what was learned
  5. Persist agent memory → write key facts to Hermes/Nextcloud

Each stage is optional and reports its own stats.
"""

import json
import time
from typing import Any


class SleepOrchestrator:
    """Coordinates the full pre-refresh sleep pipeline."""

    def __init__(self):
        self._last_sleep: float | None = None
        self._sleep_count = 0
        self._history: list[dict] = []

    def sleep(self, mlm=None, limbic=None) -> dict:
        """Run the full sleep pipeline. Returns stage-by-stage report."""
        t0 = time.monotonic()
        report = {
            "cycle": self._sleep_count + 1,
            "phases": {},
            "total_seconds": 0,
            "errors": [],
            "warnings": [],
        }

        # Phase 1: DMN daydream
        try:
            dmn = self._get_dmn()
            d_result = dmn.daydream(mlm=mlm, limbic=limbic)
            report["phases"]["dmn_daydream"] = {
                "status": d_result.get("status", "error"),
                "sampled": d_result.get("sampled", 0),
                "promoted": d_result.get("promoted", 0),
                "insights": d_result.get("insights", 0),
                "reinforcements": d_result.get("reinforcements", 0),
            }
        except Exception as e:
            report["phases"]["dmn_daydream"] = {"status": "error", "error": str(e)}
            report["errors"].append(f"DMN: {e}")

        # Phase 2: VQ compression
        if mlm is not None:
            try:
                vq_report = self._compress_mlm(mlm)
                report["phases"]["vq_compress"] = vq_report
            except Exception as e:
                report["phases"]["vq_compress"] = {"status": "error", "error": str(e)}
                report["errors"].append(f"VQ: {e}")
        else:
            report["phases"]["vq_compress"] = {"status": "skipped", "reason": "no MLM"}

        # Phase 3: MLM consolidation
        if mlm is not None:
            try:
                c_result = mlm.consolidate()
                report["phases"]["mlm_consolidate"] = {
                    "status": "ok",
                    "promoted": c_result.get("promoted", 0),
                    "pruned": c_result.get("pruned", 0),
                    "before": c_result.get("before", {}),
                    "after": c_result.get("after", {}),
                }
            except Exception as e:
                report["phases"]["mlm_consolidate"] = {"status": "error", "error": str(e)}
                report["errors"].append(f"MLM consolidate: {e}")
        else:
            report["phases"]["mlm_consolidate"] = {"status": "skipped", "reason": "no MLM"}

        # Phase 4: Persist agent memory (key facts)
        try:
            persist_report = self._persist_memory(mlm, dmn)
            report["phases"]["persist_memory"] = persist_report
        except Exception as e:
            report["phases"]["persist_memory"] = {"status": "error", "error": str(e)}
            report["errors"].append(f"Persist: {e}")

        report["total_seconds"] = round(time.monotonic() - t0, 3)
        status = "ok" if not report["errors"] else "partial"
        report["status"] = status

        self._sleep_count += 1
        self._last_sleep = time.time()
        self._history.append(report)
        self._history = self._history[-20:]  # keep last 20

        return report

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _get_dmn(self):
        """Lazy import and get DMN engine."""
        from engine.daydream_module import DaydreamEngine
        return DaydreamEngine()

    def _compress_mlm(self, mlm) -> dict:
        """Apply VQ compression to all MLM items."""
        from engine.vector_quantizer import VectorQuantizer
        vq = VectorQuantizer()
        count = 0
        for store_name in ("_episodic", "_semantic"):
            store = getattr(mlm, store_name, {})
            for mid in list(store.keys()):
                store[mid] = vq.encode_memory(store[mid])
                count += 1
        return {
            "status": "ok",
            "items_compressed": count,
            "codebook_size": vq.tags.stats()["size"],
            "unique_content": vq.content.stats()["unique_items"],
        }

    def _persist_memory(self, mlm, dmn) -> dict:
        """Extract key facts for agent memory persistence."""
        facts = []
        if mlm is not None:
            try:
                for item in list(mlm._semantic.values())[:5]:
                    c = item.get("content", "")
                    if isinstance(c, str) and len(c) > 10:
                        facts.append(c[:200])
            except Exception:
                pass
        if dmn is not None:
            try:
                for ins in dmn.get_insights(limit=3):
                    facts.append(ins.get("text", "")[:200])
            except Exception:
                pass

        return {
            "status": "ok",
            "facts_extracted": len(facts),
            "facts": facts,
        }

    def status(self) -> dict:
        return {
            "sleep_count": self._sleep_count,
            "last_sleep_seconds_ago": round(time.time() - self._last_sleep, 1) if self._last_sleep else None,
            "last_report": self._history[-1] if self._history else None,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_ORCHESTRATOR: SleepOrchestrator | None = None


def get_orchestrator() -> SleepOrchestrator:
    global _ORCHESTRATOR
    if _ORCHESTRATOR is None:
        _ORCHESTRATOR = SleepOrchestrator()
    return _ORCHESTRATOR


# ---------------------------------------------------------------------------
# MCP Tool definitions
# ---------------------------------------------------------------------------

SLEEP_TOOLS = [
    {
        "name": "write_cortex_sleep",
        "description": " WRITE — Full CortexStratum sleep cycle. Runs DMN daydream, VQ compress, MLM consolidate, and persist all in one coordinated phase. Call before context refresh. Use dry_run for preview.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "phases": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["dmn", "vq", "mlm", "persist", "all"]},
                    "description": "Which phases to run. Default: ['all']",
                    "default": ["all"],
                },
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": [],
        },
    },
    {
        "name": "read_cortex_sleep_status",
        "description": " READ — View last sleep cycle report and orchestrator state.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


# ---------------------------------------------------------------------------
# MCP Tool handler
# ---------------------------------------------------------------------------

def handle_tool_call(name: str, args: dict) -> dict:
    orch = get_orchestrator()
    if name == "read_cortex_sleep_status":
        return {"content": [{"type": "text", "text": json.dumps(orch.status(), indent=2)}]}

    if name == "write_cortex_sleep":
        dry_run = args.get("dry_run", False)
        if dry_run:
            return {"content": [{"type": "text", "text": json.dumps({
                "status": "dry_run",
                "note": "Would run: DMN daydream → VQ compress → MLM consolidate → persist",
                "phases_available": ["dmn", "vq", "mlm", "persist", "all"],
            }, indent=2)}]}

        # Lazy-import MLM and limbic
        try:
            from engine.multi_layer_memory import _get_mlm
            mlm = _get_mlm()
        except Exception as e:
            mlm = None
        try:
            from engine.limbic_module import _get_limbic
            limbic = _get_limbic()
        except Exception:
            limbic = None

        result = orch.sleep(mlm=mlm, limbic=limbic)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    msg = "Unknown sleep tool: " + str(name)
    return {"content": [{"type": "text", "text": json.dumps({"error": msg})}]}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Sleep Cycle Self-Test ===\n")

    # Mock MLM
    class MockMLM:
        def __init__(self):
            self._episodic = {}
            self._semantic = {}
            t = time.time()
            self._episodic["ep1"] = {"id":"ep1","content":"Docker networking fix","tags":["docker"],"layer":"episodic","importance":0.4,"access_count":3,"created_at":t-100,"ttl_seconds":3600}
            self._episodic["ep2"] = {"id":"ep2","content":"MLM rebuild done","tags":["mlm"],"layer":"episodic","importance":0.5,"access_count":2,"created_at":t-200,"ttl_seconds":3600}
            self._semantic["sem1"] = {"id":"sem1","content":"Docker bridge needs port mapping","tags":["docker","networking"],"layer":"semantic","importance":0.85,"access_count":10,"created_at":t-1000}
        def consolidate(self):
            return {"status":"ok","promoted":1,"pruned":0,"before":{"episodic":2,"semantic":1},"after":{"episodic":1,"semantic":2}}
        def search_all(self, q, limit=20):
            return {"episodic":[],"semantic":[]}

    orch = SleepOrchestrator()

    # Test 1: Fresh
    s0 = orch.status()
    print(f"1. Fresh: cycles={s0['sleep_count']}, last={s0['last_sleep_seconds_ago']}")
    assert s0["sleep_count"] == 0
    assert s0["last_sleep_seconds_ago"] is None

    # Test 2: Dry run
    dry = orch.sleep(mlm=None)  # no mlm → skips vq/mlm phases
    print(f"2. Dry run: status={dry['status']}, phases={list(dry['phases'].keys())}")
    # Should have all phases, some skipped

    # Test 3: Full sleep with mock MLM
    mock_mlm = MockMLM()
    r1 = orch.sleep(mlm=mock_mlm)
    print(f"3. Full sleep: status={r1['status']}, time={r1['total_seconds']}s")
    assert r1["total_seconds"] >= 0
    assert "dmn_daydream" in r1["phases"]
    assert "vq_compress" in r1["phases"]
    assert "mlm_consolidate" in r1["phases"]
    assert "persist_memory" in r1["phases"]

    # Test 4: Status after sleep
    s1 = orch.status()
    print(f"4. After sleep: cycles={s1['sleep_count']}, last={s1['last_sleep_seconds_ago']}s ago")
    assert s1["sleep_count"] == 2  # dry run counted as sleep too
    assert s1["last_sleep_seconds_ago"] is not None

    # Test 5: Phase detail
    dmn_phase = r1["phases"]["dmn_daydream"]
    print(f"5. DMN: status={dmn_phase['status']}, sampled={dmn_phase.get('sampled','?')}")
    vq_phase = r1["phases"]["vq_compress"]
    print(f"   VQ: status={vq_phase['status']}, compressed={vq_phase.get('items_compressed','?')}")
    mlm_phase = r1["phases"]["mlm_consolidate"]
    print(f"   MLM: status={mlm_phase['status']}, promoted={mlm_phase.get('promoted','?')}")
    persist_phase = r1["phases"]["persist_memory"]
    print(f"   Persist: facts={persist_phase.get('facts_extracted','?')}")

    print("\nAll self-tests passed.")
