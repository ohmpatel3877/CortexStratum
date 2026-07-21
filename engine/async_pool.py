#!/usr/bin/env python3
"""
Async Pool — ThreadPoolExecutor manager for CortexStratum.

Replaces unbounded `threading.Thread()` per tool call with a bounded
thread pool. Tracks active, pending, completed, and errored calls.

Default max_workers = 4. Resizable at runtime.
"""

import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any


class AsyncPool:
    """Bounded thread pool with runtime observability."""

    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="cortex-pool",
        )
        self._lock = threading.Lock()
        self._active = 0
        self._pending = 0
        self._completed = 0
        self._errors = 0
        self._total_submitted = 0
        self._start_time = time.monotonic()

    def submit(
        self, fn: Callable, *args: Any, **kwargs: Any
    ) -> Future:
        """Submit a task to the pool. Returns a Future."""
        self._track_submit()
        future = self._executor.submit(self._wrapped_fn, fn, *args, **kwargs)
        future.add_done_callback(self._track_done)
        return future

    def _track_submit(self):
        with self._lock:
            self._total_submitted += 1
            self._pending += 1

    def _track_done(self, future: Future):
        with self._lock:
            self._pending -= 1
            self._active -= max(0, self._pending)  # approximate
            self._active = max(0, self._active)
            ex = future.exception()
            if ex is not None:
                self._errors += 1
            self._completed += 1

    def _wrapped_fn(self, fn: Callable, *args, **kwargs) -> Any:
        """Wrapper that tracks active count."""
        with self._lock:
            self._active += 1
        try:
            return fn(*args, **kwargs)
        except Exception:
            raise

    def resize(self, max_workers: int) -> dict:
        """Resize the pool. Creates a new executor; in-flight tasks drain on old one."""
        old = self._max_workers
        if max_workers < 1:
            max_workers = 1
        if max_workers == old:
            return {"status": "no_change", "max_workers": old}

        old_executor = self._executor
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="cortex-pool",
        )
        self._max_workers = max_workers
        # Shut down old executor after in-flight tasks finish
        old_executor.shutdown(wait=False)
        return {"status": "resized", "from": old, "to": max_workers}

    def status(self) -> dict:
        with self._lock:
            now = time.monotonic()
            return {
                "max_workers": self._max_workers,
                "active": self._active,
                "pending": self._pending,
                "completed": self._completed,
                "errors": self._errors,
                "total_submitted": self._total_submitted,
                "uptime_seconds": round(now - self._start_time, 1),
                "queue_depth": self._pending,
            }

    def shutdown(self, wait: bool = True):
        """Shut down the pool gracefully."""
        self._executor.shutdown(wait=wait)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_POOL: AsyncPool | None = None


def get_pool() -> AsyncPool:
    global _POOL
    if _POOL is None:
        _POOL = AsyncPool(max_workers=4)
    return _POOL


# ---------------------------------------------------------------------------
# MCP Tool definitions & handler
# ---------------------------------------------------------------------------

ASYNC_POOL_TOOLS = [
    {
        "name": "read_cortex_pool_status",
        "description": " READ — View async pool state: active/pending/completed/errors, max workers, queue depth.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "write_cortex_pool_resize",
        "description": " WRITE — Resize the thread pool. Default 4 workers. Min 1.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_workers": {
                    "type": "integer",
                    "default": 4,
                    "description": "New pool size (min 1)",
                },
            },
            "required": ["max_workers"],
        },
    },
]


def handle_tool_call(name: str, args: dict) -> dict:
    pool = get_pool()
    if name == "read_cortex_pool_status":
        return {"content": [{"type": "text", "text": json.dumps(pool.status(), indent=2)}]}
    elif name == "write_cortex_pool_resize":
        mw = max(1, args.get("max_workers", 4))
        return {"content": [{"type": "text", "text": json.dumps(pool.resize(mw), indent=2)}]}
    msg = "Unknown pool tool: " + str(name)
    return {"content": [{"type": "text", "text": json.dumps({"error": msg})}]}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import time

    print("=== Async Pool Self-Test ===\n")

    p = AsyncPool(max_workers=2)

    # 1. Fresh
    s0 = p.status()
    print(f"1. Fresh: workers={s0['max_workers']}, queue={s0['queue_depth']}")
    assert s0["max_workers"] == 2
    assert s0["queue_depth"] == 0

    # 2. Submit tasks
    results = []
    def dummy(sec, label):
        time.sleep(sec)
        return label

    f1 = p.submit(dummy, 0.05, "a")
    f2 = p.submit(dummy, 0.05, "b")
    r1 = f1.result()
    r2 = f2.result()
    print(f"2. Tasks: {r1}, {r2}")
    assert r1 == "a"
    assert r2 == "b"

    # 3. Status after tasks
    s1 = p.status()
    print(f"3. After: completed={s1['completed']}, errors={s1['errors']}")
    assert s1["completed"] == 2
    assert s1["errors"] == 0

    # 4. Error tracking
    def fails():
        raise ValueError("boom")

    f3 = p.submit(fails)
    try:
        f3.result()
    except ValueError:
        pass

    s2 = p.status()
    print(f"4. Error: total={s2['total_submitted']}, errors={s2['errors']}")
    assert s2["errors"] == 1

    # 5. Resize
    r = p.resize(8)
    print(f"5. Resize: {r['status']}, {r['from']}→{r['to']}")
    assert r["status"] == "resized"
    assert r["to"] == 8

    # 6. Status after resize
    s3 = p.status()
    print(f"6. After resize: workers={s3['max_workers']}")
    assert s3["max_workers"] == 8

    # 7. Concurrent tracking
    p2 = AsyncPool(max_workers=8)
    latches = []
    def slow_task(idx):
        time.sleep(0.1)
        return idx

    futures = [p2.submit(slow_task, i) for i in range(5)]
    for f in futures:
        f.result()

    s4 = p2.status()
    print(f"7. Concurrent 5 tasks: completed={s4['completed']}, errors={s4['errors']}")
    assert s4["completed"] == 5

    p.shutdown()
    p2.shutdown()
    print("\nAll self-tests passed.")
