#!/usr/bin/env python3
"""
Daydream Module — DMN (Default Mode Network) for Autonomous Consolidation

Background processing that samples multi-layer memory, evaluates insights,
and autonomously builds new associations. The DMN is the brain's default
mode network — active during wakeful rest, daydreaming, and mind-wandering.
It consolidates episodic memories into semantic knowledge and generates
new insights by cross-linking concepts.

Flow: Sample -> Score -> Promote -> Reinforce -> Log

Tools:
  - read_dmn_status        : View DMN state (cycle count, auto mode, last run)
  - write_dmn_daydream     : Trigger one manual consolidation cycle
  - mutate_dmn_autonomode  : Enable/disable automatic periodic cycling
  - read_dmn_insights      : View generated insights from recent cycles
"""

import json
import random
import threading
import time
from typing import Any


class DaydreamEngine:
    """DMN-style background consolidation engine."""

    def __init__(self):
        self._cycle_count = 0
        self._insights: list[dict] = []
        self._last_run: float | None = None
        self._auto_mode: bool = False
        self._auto_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._sample_size = 8
        self._promote_threshold = 2
        self._insight_score_threshold = 0.5
        self._auto_interval = 60.0

    # ------------------------------------------------------------------
    # Core DMN cycle
    # ------------------------------------------------------------------

    def daydream(self, mlm=None, limbic=None) -> dict:
        """Run one complete DMN consolidation cycle."""
        result = {
            "cycle": self._cycle_count + 1,
            "sampled": 0,
            "promoted": 0,
            "insights": 0,
            "reinforcements": 0,
            "errors": [],
        }

        if mlm is None:
            result["errors"].append("No MLM available")
            result["status"] = "error"
            return result

        try:
            samples = self._sample(mlm)
            result["sampled"] = len(samples)

            scored = [self._score(s) for s in samples]
            high_value = [s for s in scored if s["score"] >= self._insight_score_threshold]

            for sv in high_value:
                insight = self._generate_insight(sv, mlm)
                if insight:
                    self._insights.append(insight)
                    result["insights"] += 1

            promoted = self._auto_promote(mlm, samples)
            result["promoted"] = promoted

            if limbic is not None:
                reinforced = self._auto_reinforce(limbic, high_value)
                result["reinforcements"] = reinforced

            self._insights = self._insights[-50:]
            self._cycle_count += 1
            self._last_run = time.time()
            result["status"] = "ok"

        except Exception as e:
            result["errors"].append(str(e))
            result["status"] = "error"

        return result

    # ------------------------------------------------------------------
    # Internal strategies
    # ------------------------------------------------------------------

    def _sample(self, mlm) -> list[dict]:
        samples = []
        try:
            ep_list = sorted(
                [v for v in mlm._episodic.values()],
                key=lambda x: x.get("created_at", 0), reverse=True,
            )[:self._sample_size // 2]
            samples.extend(ep_list)
        except Exception:
            pass

        try:
            sem_list = sorted(
                [v for v in mlm._semantic.values()],
                key=lambda x: x.get("importance", 0), reverse=True,
            )[:self._sample_size // 2]
            samples.extend(sem_list)
        except Exception:
            pass

        if len(samples) < self._sample_size:
            try:
                all_items = list(mlm._episodic.values()) + list(mlm._semantic.values())
                random.shuffle(all_items)
                samples.extend(all_items[:self._sample_size - len(samples)])
            except Exception:
                pass

        seen = set()
        unique = []
        for s in samples:
            sid = s.get("id", "")
            if sid not in seen:
                seen.add(sid)
                unique.append(s)
        return unique

    def _score(self, item: dict) -> dict:
        now = time.time()
        age = now - item.get("created_at", now)
        access = item.get("access_count", 0)
        importance = item.get("importance", 0.3)

        recency_score = 1.0 / (age / 3600 + 1)
        access_score = min(access / 10.0, 1.0)
        tag_diversity = min(len(item.get("tags", [])) / 5.0, 1.0)

        score = (recency_score * 0.25 + access_score * 0.25
                 + importance * 0.35 + tag_diversity * 0.15)

        return {
            "id": item.get("id"),
            "content": item.get("content"),
            "tags": item.get("tags", []),
            "layer": item.get("layer", "unknown"),
            "score": round(min(score, 1.0), 3),
            "recency_score": round(recency_score, 3),
            "access_score": round(access_score, 3),
            "importance": importance,
        }

    def _generate_insight(self, scored_item: dict, mlm) -> dict | None:
        tags = scored_item.get("tags", [])
        content = scored_item.get("content", "")
        if not tags or not content:
            return None

        query = " ".join(tags[:3])
        related = mlm.search_all(query, limit=5)
        related_items = related.get("semantic", []) + related.get("episodic", [])
        related_items = [r for r in related_items if r.get("id") != scored_item.get("id")]

        if not related_items:
            text = f"Pattern: '{str(content)[:80]}...' tagged {tags}"
        else:
            rc = str(related_items[0].get("content", ""))
            text = f"Cross-link: '{str(content)[:60]}...' <-> '{rc[:60]}...' (tags: {tags})"

        return {
            "id": f"insight-{len(self._insights) + 1}",
            "text": text,
            "source_id": scored_item.get("id"),
            "source_layer": scored_item.get("layer"),
            "tags": tags,
            "score": scored_item.get("score", 0),
            "created_at": time.time(),
            "related_count": len(related_items),
        }

    def _auto_promote(self, mlm, samples: list[dict]) -> int:
        promoted = 0
        for item in samples:
            if item.get("layer") != "episodic":
                continue
            if item.get("access_count", 0) >= self._promote_threshold:
                mid = item.get("id")
                if mid:
                    try:
                        r = mlm.promote(mid)
                        if r.get("status") in ("promoted", "queued"):
                            promoted += 1
                    except Exception:
                        pass
        return promoted

    def _auto_reinforce(self, limbic, high_value: list[dict]) -> int:
        reinforced = 0
        for sv in high_value[:3]:
            key = sv.get("id") or str(sv.get("content", ""))[:40]
            try:
                limbic.reinforce(
                    key=key, outcome="success",
                    delta=sv.get("score", 0.5) * 0.5,
                    reason=f"DMN daydream: {sv.get('tags', [])}",
                    source="daydream_module",
                )
                reinforced += 1
            except Exception:
                pass
        return reinforced

    # ------------------------------------------------------------------
    # Auto-mode (background thread)
    # ------------------------------------------------------------------

    def start_auto(self, interval: float | None = None) -> dict:
        if self._auto_thread and self._auto_thread.is_alive():
            return {"status": "error", "error": "Auto-mode already running"}
        if interval is not None:
            self._auto_interval = interval
        self._auto_mode = True
        self._stop_event.clear()
        self._auto_thread = threading.Thread(
            target=self._auto_loop, daemon=True, name="dmn-auto",
        )
        self._auto_thread.start()
        return {"status": "ok", "interval": self._auto_interval}

    def stop_auto(self):
        self._auto_mode = False
        self._stop_event.set()
        self._auto_thread = None

    def _auto_loop(self):
        while not self._stop_event.is_set():
            try:
                self.daydream()
            except Exception:
                pass
            self._stop_event.wait(self._auto_interval)

    # ------------------------------------------------------------------
    # Status / queries
    # ------------------------------------------------------------------

    def status(self) -> dict:
        now = time.time()
        return {
            "cycle_count": self._cycle_count,
            "auto_mode": self._auto_mode,
            "auto_interval": self._auto_interval if self._auto_mode else None,
            "last_run_seconds_ago": round(now - self._last_run, 1) if self._last_run else None,
            "insights_logged": len(self._insights),
            "sample_size": self._sample_size,
            "promote_threshold": self._promote_threshold,
            "insight_threshold": self._insight_score_threshold,
        }

    def get_insights(self, limit: int = 10) -> list[dict]:
        return self._insights[-limit:]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_ENGINE: DaydreamEngine | None = None


def _get_engine() -> DaydreamEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = DaydreamEngine()
    return _ENGINE


# ---------------------------------------------------------------------------
# MCP Tool handler
# ---------------------------------------------------------------------------

def handle_tool_call(name: str, args: dict) -> dict:
    engine = _get_engine()
    try:
        if name == "read_dmn_status":
            return {"content": [{"type": "text", "text": json.dumps(engine.status(), indent=2)}]}

        elif name == "write_dmn_daydream":
            from engine.multi_layer_memory import _get_mlm
            mlm = _get_mlm()
            try:
                from engine.limbic_module import _get_limbic
                limbic = _get_limbic()
            except Exception:
                limbic = None
            result = engine.daydream(mlm=mlm, limbic=limbic)
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "mutate_dmn_autonomode":
            enable = args.get("enable", True)
            interval = args.get("interval")
            if enable:
                r = engine.start_auto(interval=interval)
            else:
                engine.stop_auto()
                r = {"status": "ok", "auto_mode": False}
            return {"content": [{"type": "text", "text": json.dumps(r, indent=2)}]}

        elif name == "read_dmn_insights":
            limit = args.get("limit", 10)
            return {"content": [{"type": "text", "text": json.dumps({
                "count": len(engine._insights),
                "insights": engine.get_insights(limit=limit),
            }, indent=2)}]}

        else:
            return {"content": [{"type": "text", "text": json.dumps({"error": f"Unknown DMN tool: {name}"})}]}

    except Exception as e:
        return {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}]}


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

DMN_TOOLS = [
    {
        "name": "read_dmn_status",
        "description": " READ — View DMN state: cycle count, auto-mode, last run, insight count.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "write_dmn_daydream",
        "description": " WRITE — Trigger one DMN consolidation cycle. Samples MLM, scores insights, promotes frequent patterns, reinforces in limbic.",
        "permission": "write",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "mutate_dmn_autonomode",
        "description": " MUTATE — Enable/disable automatic periodic DMN daydreaming. Background daemon runs at configurable interval (default 60s).",
        "permission": "mutate",
        "inputSchema": {
            "type": "object",
            "properties": {
                "enable": {"type": "boolean", "default": True},
                "interval": {"type": "number", "description": "Seconds between cycles"},
            },
            "required": [],
        },
    },
    {
        "name": "read_dmn_insights",
        "description": " READ — View recent insights generated by DMN cycles.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
            },
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== DMN Daydream Module Self-Test ===\n")

    engine = DaydreamEngine()

    # Mock MLM
    class MockMLM:
        def __init__(self):
            self._episodic = {}
            self._semantic = {}
            t = time.time()
            self._episodic["ep1"] = {"id":"ep1","content":"Docker networking issue","tags":["docker","networking"],"layer":"episodic","importance":0.4,"access_count":3,"created_at":t-100,"last_access":t,"ttl_seconds":3600,"promotion_count":0}
            self._episodic["ep2"] = {"id":"ep2","content":"Null pointer debug session","tags":["debug","python"],"layer":"episodic","importance":0.6,"access_count":5,"created_at":t-200,"last_access":t,"ttl_seconds":3600,"promotion_count":0}
            self._episodic["ep3"] = {"id":"ep3","content":"MLM consolidation flow","tags":["mlm","memory"],"layer":"episodic","importance":0.5,"access_count":2,"created_at":t-300,"last_access":t,"ttl_seconds":3600,"promotion_count":0}
            self._semantic["sem1"] = {"id":"sem1","content":"Docker bridge needs port mapping","tags":["docker","networking"],"layer":"semantic","importance":0.85,"access_count":10,"created_at":t-1000,"last_access":t,"ttl_seconds":86400,"promotion_count":0}
        def search_all(self, q, limit=20):
            ql = q.lower()
            ep = [v for v in self._episodic.values() if any(ql in t.lower() for t in v.get("tags",[]))]
            sem = [v for v in self._semantic.values() if any(ql in t.lower() for t in v.get("tags",[]))]
            return {"episodic": ep[:limit], "semantic": sem[:limit]}
        def promote(self, mid):
            if mid in self._episodic:
                self._semantic[f"auto-{mid}"] = dict(self._episodic[mid])
                del self._episodic[mid]
                return {"status": "promoted"}
            return {"status": "error"}
        def status(self):
            return {"episodic": {"count": len(self._episodic)}, "semantic": {"count": len(self._semantic)}}

    # Mock limbic
    class MockLimbic:
        def __init__(self):
            self.reinforces = []
        def reinforce(self, **kw):
            self.reinforces.append(kw)
        def status(self):
            return {"tags": []}

    mock_mlm = MockMLM()
    mock_limbic = MockLimbic()

    # Test 1: Fresh status
    s0 = engine.status()
    print(f"1. Status (fresh): cycle={s0['cycle_count']}, auto={s0['auto_mode']}")
    assert s0["cycle_count"] == 0

    # Test 2: One daydream cycle
    r1 = engine.daydream(mlm=mock_mlm, limbic=mock_limbic)
    print(f"2. Daydream: status={r1['status']}, sampled={r1['sampled']}, promoted={r1['promoted']}, insights={r1['insights']}, reinforces={r1['reinforcements']}")
    assert r1["status"] == "ok"
    assert r1["sampled"] > 0

    # Test 3: Status after cycle
    s1 = engine.status()
    print(f"3. After: cycle={s1['cycle_count']}, insights={s1['insights_logged']}")
    assert s1["cycle_count"] == 1

    # Test 4: Insights
    ins = engine.get_insights()
    print(f"4. Insights logged: {len(ins)}")
    if ins:
        print(f"   First: {ins[0]['text'][:80]}...")

    # Test 5: Auto-mode toggle
    a1 = engine.start_auto(interval=120.0)
    print(f"5. Auto start: ok")
    assert engine._auto_mode is True
    engine.stop_auto()
    assert engine._auto_mode is False
    print(f"   Stopped: OK")

    # Test 6: Mock MLM state
    st = mock_mlm.status()
    print(f"6. MLM after: ep={st['episodic']['count']}, sem={st['semantic']['count']}")

    # Test 7: Limbic was called
    print(f"7. Limbic reinforces: {len(mock_limbic.reinforces)}")
    if mock_limbic.reinforces:
        assert mock_limbic.reinforces[0].get("source") == "daydream_module"
        print(f"   Source verified: daydream_module")

    print("\nAll self-tests passed.")
