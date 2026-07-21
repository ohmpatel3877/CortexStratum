#!/usr/bin/env python3
"""
Observability Layer — real-time metrics for every tool call.

Tracks: call count (per-tool), latency histogram, error rate, peak concurrency.
Zero-touch integration: wraps `handle_tool_call` in the server dispatch.
"""

import json
import threading
import time
from collections import defaultdict
from typing import Any

# ---------------------------------------------------------------------------
# Buckets for latency histogram (seconds)
# ---------------------------------------------------------------------------

HISTOGRAM_BUCKETS = [0.05, 0.2, 0.5, 1.0, float("inf")]
BUCKET_LABELS = ["<50ms", "<200ms", "<500ms", "<1s", ">1s"]


def _bucket(duration: float) -> str:
    for i, bound in enumerate(HISTOGRAM_BUCKETS):
        if duration < bound:
            return BUCKET_LABELS[i]
    return BUCKET_LABELS[-1]


# ---------------------------------------------------------------------------
# Metrics Collector (thread-safe)
# ---------------------------------------------------------------------------

class MetricsCollector:
    """Thread-safe, lock-free via single lock."""

    def __init__(self):
        self._lock = threading.Lock()
        # Per-tool counters
        self._call_count: dict[str, int] = defaultdict(int)
        self._error_count: dict[str, int] = defaultdict(int)
        self._latency_buckets: dict[str, dict[str, int]] = defaultdict(
            lambda: {b: 0 for b in BUCKET_LABELS}
        )
        # Aggregate
        self._total_calls = 0
        self._total_errors = 0
        self._start_time = time.monotonic()
        self._peak_concurrent = 0
        self._current_concurrent = 0
        # Per-tool total duration (for average)
        self._total_duration: dict[str, float] = defaultdict(float)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_call(self, name: str) -> dict:
        """Call BEFORE dispatch. Returns a context dict for end_call()."""
        ctx = {"name": name, "t0": time.monotonic()}
        return ctx

    def record_result(self, ctx: dict, error: bool = False):
        """Call AFTER dispatch with the context from record_call()."""
        name = ctx["name"]
        duration = time.monotonic() - ctx["t0"]
        with self._lock:
            self._call_count[name] += 1
            self._total_calls += 1
            self._total_duration[name] += duration
            self._latency_buckets[name][_bucket(duration)] += 1
            if error:
                self._error_count[name] += 1
                self._total_errors += 1

    def record_concurrency(self, delta: int):
        """Call with +1 at start, -1 at end (or use the context manager)."""
        with self._lock:
            self._current_concurrent += delta
            if self._current_concurrent > self._peak_concurrent:
                self._peak_concurrent = self._current_concurrent

    # ------------------------------------------------------------------
    # Context manager (preferred)
    # ------------------------------------------------------------------

    class _ObserveContext:
        def __init__(self, collector: "MetricsCollector", name: str):
            self.collector = collector
            self.name = name
            self.error = False
            self._ctx = None

        def __enter__(self):
            self.collector.record_concurrency(1)
            self._ctx = self.collector.record_call(self.name)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                self.error = True
            self.collector.record_result(self._ctx, error=self.error)
            self.collector.record_concurrency(-1)
            return False  # don't suppress exceptions

    def observe(self, name: str) -> "_ObserveContext":
        """Use: with metrics.observe('tool_name') as ctx: ..."""
        return self._ObserveContext(self, name)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def status(self) -> dict:
        with self._lock:
            now = time.monotonic()
            uptime = now - self._start_time

            # Per-tool detail
            tools = {}
            for name in sorted(set(list(self._call_count.keys()) + list(self._error_count.keys()))):
                cnt = self._call_count.get(name, 0)
                err = self._error_count.get(name, 0)
                total_dur = self._total_duration.get(name, 0.0)
                avg_latency = round(total_dur / cnt, 3) if cnt else 0.0
                tools[name] = {
                    "calls": cnt,
                    "errors": err,
                    "error_rate": round(err / cnt, 3) if cnt else 0.0,
                    "avg_latency_sec": avg_latency,
                    "latency_histogram": dict(self._latency_buckets[name]),
                }

            return {
                "uptime_seconds": round(uptime, 1),
                "total_calls": self._total_calls,
                "total_errors": self._total_errors,
                "error_rate": round(self._total_errors / self._total_calls, 3) if self._total_calls else 0.0,
                "peak_concurrent": self._peak_concurrent,
                "current_concurrent": self._current_concurrent,
                "tools_monitored": len(tools),
                "tools": tools,
                "aggregate_latency": {
                    b: sum(
                        self._latency_buckets[name][b]
                        for name in self._call_count
                    )
                    for b in BUCKET_LABELS
                },
            }

    def reset(self):
        with self._lock:
            self._call_count.clear()
            self._error_count.clear()
            self._latency_buckets.clear()
            self._total_calls = 0
            self._total_errors = 0
            self._total_duration.clear()
            self._start_time = time.monotonic()
            self._peak_concurrent = self._current_concurrent  # preserve current
            return {"status": "ok", "reset_at": self._start_time}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_METRICS: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    global _METRICS
    if _METRICS is None:
        _METRICS = MetricsCollector()
    return _METRICS


# ---------------------------------------------------------------------------
# MCP Tool handler
# ---------------------------------------------------------------------------

OBSERVABILITY_TOOLS = [
    {
        "name": "read_cortex_metrics",
        "description": " READ — View observability metrics: call counts, latency histograms, error rates per tool, peak concurrency.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "write_cortex_metrics_reset",
        "description": " WRITE — Reset all accumulated observability metrics to zero.",
        "permission": "write",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


def handle_tool_call(name: str, args: dict) -> dict:
    metrics = get_metrics()
    if name == "read_cortex_metrics":
        return {"content": [{"type": "text", "text": json.dumps(metrics.status(), indent=2)}]}
    elif name == "write_cortex_metrics_reset":
        return {"content": [{"type": "text", "text": json.dumps(metrics.reset(), indent=2)}]}
    msg = "Unknown observability tool: " + str(name)
    return {"content": [{"type": "text", "text": json.dumps({"error": msg})}]}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Observability Self-Test ===\n")

    m = MetricsCollector()

    # 1. Fresh state
    s0 = m.status()
    print(f"1. Fresh: calls={s0['total_calls']}, uptime>0={s0['uptime_seconds'] > 0}")
    assert s0["total_calls"] == 0
    assert s0["uptime_seconds"] >= 0

    # 2. Record a few calls
    for i in range(5):
        ctx = m.record_call("tool_a")
        time.sleep(0.01)
        m.record_result(ctx, error=(i == 3))

    ctx = m.record_call("tool_b")
    m.record_result(ctx, error=True)

    s1 = m.status()
    print(f"2. After 6 calls: calls={s1['total_calls']}, errors={s1['total_errors']}, tools={s1['tools_monitored']}")
    assert s1["total_calls"] == 6
    assert s1["total_errors"] == 2  # tool_a[3] + tool_b
    assert s1["tools_monitored"] == 2

    # 3. Per-tool stats
    ta = s1["tools"].get("tool_a", {})
    tb = s1["tools"].get("tool_b", {})
    print(f"3. tool_a: calls={ta['calls']}, errors={ta['errors']}, avg_latency={ta['avg_latency_sec']}")
    print(f"   tool_b: calls={tb['calls']}, errors={tb['errors']}")
    assert ta["calls"] == 5
    assert ta["errors"] == 1
    assert tb["calls"] == 1
    assert tb["errors"] == 1

    # 4. Context manager
    with m.observe("tool_c"):
        time.sleep(0.005)

    s2 = m.status()
    print(f"4. After ctx manager: calls={s2['total_calls']}, tool_c_calls={s2['tools'].get('tool_c', {}).get('calls', 0)}")
    assert s2["total_calls"] == 7

    # 5. Reset
    r = m.reset()
    s3 = m.status()
    print(f"5. Reset: calls={s3['total_calls']}, uptime={s3['uptime_seconds']:.1f}")
    assert s3["total_calls"] == 0

    # 6. Concurrency
    with m.observe("tool_d"):
        with m.observe("tool_d_nested"):
            time.sleep(0.005)
    s4 = m.status()
    print(f"6. Concurrency: peak={s4['peak_concurrent']}, current={s4['current_concurrent']}")
    assert s4["peak_concurrent"] >= 2

    print("\nAll self-tests passed.")
