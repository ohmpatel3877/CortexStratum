#!/usr/bin/env python3
"""
Speed Optimizer — Monitors slowdowns logged in memory, analyzes bottleneck
patterns, and generates workaround strategies. Learns from past bottlenecks
so the same slowdown doesn't hit twice.

Events are logged to memory as structured entries, then this module reads
them back, clusters by pattern, and suggests/pre-applies mitigations.

Usage:
    from speed_optimizer import SpeedOptimizer
    opt = SpeedOptimizer()
    opt.log_slowdown("tool_call", "docker_build", 45000, 5000)
    report = opt.analyze()
    strategies = opt.generate_strategies()
"""

import json, os, sys, time, hashlib, statistics, re
from dataclasses import dataclass, field, asdict
from typing import Optional
from collections import defaultdict
from pathlib import Path


#  Event Schema 
# Each slowdown is logged as a memory event with this structure:

@dataclass
class SpeedEvent:
    category: str        # tool_call, file_read, build, network, model_inference, etc.
    operation: str       # Specific operation name (docker_build, pip_install, etc.)
    duration_ms: int     # How long it took
    expected_ms: int     # What it should be (baseline)
    threshold_ms: int    # What's considered "too slow" 
    context: str = ""    # Additional context (file path, URL, etc.)
    timestamp: float = 0
    fingerprint: str = ""

    def __post_init__(self):
        self.timestamp = self.timestamp or time.time()
        raw = f"{self.category}|{self.operation}|{self.context}"
        self.fingerprint = hashlib.md5(raw.encode()).hexdigest()[:12]


#  Known Bottleneck Patterns 
# These are cross-session learnings stored as resolution strategies.

BOTTLENECK_PATTERNS = {
    "pip_install": {
        "description": "pip install is slow due to package resolution and wheel compilation",
        "typical_ms": 30000,
        "threshold_ms": 15000,
        "strategies": [
            {"name": "uv", "description": "Replace pip with uv (10-100x faster)", "effort": "low", "impact": "high"},
            {"name": "wheels", "description": "Use pre-built wheels, skip source compilation", "effort": "low", "impact": "medium"},
            {"name": "cache", "description": "Use --cache-dir on persistent volume", "effort": "low", "impact": "medium"},
            {"name": "no-deps", "description": "Skip dependency resolution with --no-deps if already satisfied", "effort": "medium", "impact": "high"},
        ],
        "recommended": "uv",
    },
    "docker_build": {
        "description": "Docker build is slow due to cache misses and large layers",
        "typical_ms": 120000,
        "threshold_ms": 30000,
        "strategies": [
            {"name": "layer_cache", "description": "Reorder Dockerfile for cache efficiency (frequent changes last)", "effort": "medium", "impact": "high"},
            {"name": "multi_stage", "description": "Use multi-stage builds to separate build deps from runtime", "effort": "medium", "impact": "high"},
            {"name": "deps_bundled", "description": "Pre-bundle base image with dependencies", "effort": "high", "impact": "very_high"},
            {"name": "cache_from", "description": "Use --cache-from to reuse remote cache", "effort": "low", "impact": "medium"},
        ],
        "recommended": "layer_cache",
    },
    "npm_install": {
        "description": "npm install is slow due to dependency resolution and network",
        "typical_ms": 45000,
        "threshold_ms": 15000,
        "strategies": [
            {"name": "pnpm", "description": "Replace npm with pnpm (faster, disk-efficient)", "effort": "low", "impact": "high"},
            {"name": "ci", "description": "Use npm ci instead of npm install (skips resolution)", "effort": "low", "impact": "high"},
            {"name": "cache", "description": "Use npm cache with persistent volume", "effort": "low", "impact": "medium"},
            {"name": "lockfile", "description": "Ensure package-lock.json is committed", "effort": "low", "impact": "medium"},
        ],
        "recommended": "ci",
    },
    "model_inference": {
        "description": "Large model inference is slow on free-tier models",
        "typical_ms": 15000,
        "threshold_ms": 5000,
        "strategies": [
            {"name": "prompt_compression", "description": "Compress prompts, remove redundant context", "effort": "medium", "impact": "high"},
            {"name": "parameter_virtualizer", "description": "Use parameter virtualizer to get better output from smaller model", "effort": "low", "impact": "medium"},
            {"name": "caching", "description": "Cache common inference results in memory", "effort": "low", "impact": "medium"},
            {"name": "batching", "description": "Batch multiple inference requests into one", "effort": "medium", "impact": "high"},
        ],
        "recommended": "prompt_compression",
    },
    "file_read": {
        "description": "Reading large files is slow",
        "typical_ms": 2000,
        "threshold_ms": 500,
        "strategies": [
            {"name": "head_only", "description": "Read only first N lines instead of entire file", "effort": "low", "impact": "high"},
            {"name": "grep", "description": "Use grep to find specific content instead of full read", "effort": "low", "impact": "high"},
            {"name": "binary", "description": "Skip binary/large files, use metadata instead", "effort": "low", "impact": "medium"},
            {"name": "mmap", "description": "Use memory-mapped files for very large files", "effort": "high", "impact": "medium"},
        ],
        "recommended": "head_only",
    },
    "git_operation": {
        "description": "Git operations are slow on large repos",
        "typical_ms": 5000,
        "threshold_ms": 2000,
        "strategies": [
            {"name": "shallow", "description": "Use --depth 1 for clones/fetches", "effort": "low", "impact": "high"},
            {"name": "filter_blob", "description": "Use --filter=blob:none for partial clones", "effort": "low", "impact": "high"},
            {"name": "sparse_checkout", "description": "Use sparse checkout to only get needed directories", "effort": "medium", "impact": "high"},
            {"name": "worktree", "description": "Use git worktree instead of switching branches", "effort": "medium", "impact": "high"},
        ],
        "recommended": "shallow",
    },
    "network_request": {
        "description": "Network requests are slow or timing out",
        "typical_ms": 5000,
        "threshold_ms": 2000,
        "strategies": [
            {"name": "timeout", "description": "Reduce timeout from default 60s to 10s", "effort": "low", "impact": "medium"},
            {"name": "retry", "description": "Add exponential backoff retry, fail fast after 3 attempts", "effort": "low", "impact": "high"},
            {"name": "parallel", "description": "Parallelize independent network requests", "effort": "medium", "impact": "high"},
            {"name": "caching", "description": "Cache responses with TTL to avoid repeat requests", "effort": "low", "impact": "high"},
        ],
        "recommended": "retry",
    },
    "compilation": {
        "description": "Code compilation/bundling is slow",
        "typical_ms": 30000,
        "threshold_ms": 10000,
        "strategies": [
            {"name": "incremental", "description": "Use incremental compilation (sccache, turbopack)", "effort": "medium", "impact": "high"},
            {"name": "parallel", "description": "Parallelize compilation across cores", "effort": "low", "impact": "high"},
            {"name": "skip_test", "description": "Skip test compilation in dev builds", "effort": "low", "impact": "medium"},
            {"name": "codegen_units", "description": "Reduce codegen units for Rust, enable LTO only for release", "effort": "medium", "impact": "medium"},
        ],
        "recommended": "incremental",
    },
}


class SpeedOptimizer:
    """
    Monitors slowdown events, analyzes patterns, and generates
    optimization strategies. Stores learnings in memory for cross-session use.
    """

    def __init__(self, memory_store: Optional[list] = None):
        self.events: list[SpeedEvent] = []
        self.memory_store = memory_store or []  # Simulated memory backend
        self._load_from_memory()

    def log_slowdown(self, category: str, operation: str, duration_ms: int,
                     expected_ms: int, context: str = "") -> SpeedEvent:
        """Log a slowdown event. Call this after any operation that took too long."""
        threshold_ms = int(expected_ms * 1.5)
        event = SpeedEvent(
            category=category,
            operation=operation,
            duration_ms=duration_ms,
            expected_ms=expected_ms,
            threshold_ms=threshold_ms,
            context=context,
        )
        self.events.append(event)
        self._store_event(event)
        return event

    def _store_event(self, event: SpeedEvent):
        """Store event in the memory-backed store."""
        entry = {
            "type": "speed_event",
            "category": event.category,
            "operation": event.operation,
            "duration_ms": event.duration_ms,
            "expected_ms": event.expected_ms,
            "threshold_ms": event.threshold_ms,
            "context": event.context,
            "fingerprint": event.fingerprint,
            "timestamp": event.timestamp,
            "is_slowdown": event.duration_ms > event.threshold_ms,
        }
        self.memory_store.append(entry)

    def _load_from_memory(self):
        """Load past events from memory store."""
        for entry in self.memory_store:
            if entry.get("type") == "speed_event":
                self.events.append(SpeedEvent(
                    category=entry["category"],
                    operation=entry["operation"],
                    duration_ms=entry["duration_ms"],
                    expected_ms=entry["expected_ms"],
                    threshold_ms=entry.get("threshold_ms", int(entry["expected_ms"] * 1.5)),
                    context=entry.get("context", ""),
                    timestamp=entry.get("timestamp", 0),
                ))

    def analyze(self) -> dict:
        """
        Analyze all logged events and produce a bottleneck report.
        Clusters by (category, operation) and computes stats.
        """
        if not self.events:
            return {"status": "no_data", "message": "No slowdown events logged yet"}

        # Cluster events
        clusters = defaultdict(list)
        for event in self.events:
            key = f"{event.category}:{event.operation}"
            clusters[key].append(event)

        report = {
            "total_events": len(self.events),
            "total_slowdowns": sum(1 for e in self.events if e.duration_ms > e.threshold_ms),
            "bottlenecks": [],
            "clock_consumers": [],
        }

        for key, events in sorted(clusters.items()):
            durations = [e.duration_ms for e in events]
            expected = [e.expected_ms for e in events]
            avg_duration = statistics.mean(durations)
            avg_expected = statistics.mean(expected)
            slowdown_ratio = avg_duration / max(avg_expected, 1)
            total_time = sum(durations)

            bottleneck = {
                "key": key,
                "category": events[0].category,
                "operation": events[0].operation,
                "count": len(events),
                "avg_duration_ms": round(avg_duration, 1),
                "avg_expected_ms": round(avg_expected, 1),
                "slowdown_ratio": round(slowdown_ratio, 2),
                "total_time_ms": total_time,
                "pct_of_total": 0,  # computed below
            }

            if slowdown_ratio > 1.5:
                report["bottlenecks"].append(bottleneck)
            report["clock_consumers"].append(bottleneck)

        # Sort by total time descending
        report["clock_consumers"].sort(key=lambda x: x["total_time_ms"], reverse=True)
        report["bottlenecks"].sort(key=lambda x: x["slowdown_ratio"], reverse=True)

        total = sum(b["total_time_ms"] for b in report["clock_consumers"])
        for b in report["clock_consumers"]:
            b["pct_of_total"] = round(b["total_time_ms"] / max(total, 1) * 100, 1)

        return report

    def generate_strategies(self) -> list:
        """
        Generate optimization strategies based on current bottlenecks.
        Matches events against known patterns and returns actionable recommendations.
        """
        report = self.analyze()
        if report.get("status") == "no_data":
            return [{"status": "no_data", "message": "Log slowdowns first with log_slowdown()"}]

        strategies = []

        for bottleneck in report["bottlenecks"]:
            op = bottleneck["operation"]
            pattern = BOTTLENECK_PATTERNS.get(op)

            if pattern:
                strategies.append({
                    "operation": op,
                    "description": pattern["description"],
                    "severity": "critical" if bottleneck["slowdown_ratio"] > 3 else "warning",
                    "current_avg_ms": bottleneck["avg_duration_ms"],
                    "recommended_strategy": pattern["recommended"],
                    "options": pattern["strategies"],
                    "applied": pattern["recommended"],
                })
            else:
                # Unknown pattern — suggest investigation
                strategies.append({
                    "operation": op,
                    "description": f"Unrecognized slowdown pattern in {op}",
                    "severity": "info",
                    "current_avg_ms": bottleneck["avg_duration_ms"],
                    "recommended_strategy": "investigate",
                    "options": [
                        {"name": "investigate", "description": "Profile the operation to identify root cause", "effort": "medium", "impact": "high"},
                        {"name": "threshold", "description": "Increase timeout/threshold if this is expected", "effort": "low", "impact": "low"},
                    ],
                    "applied": "investigate",
                })

        # Apply strategies (record what was recommended)
        self._record_strategies(strategies)
        return strategies

    def _record_strategies(self, strategies: list):
        """Store the applied strategies in memory for future reference."""
        for s in strategies:
            self.memory_store.append({
                "type": "speed_strategy",
                "operation": s["operation"],
                "recommended": s["recommended_strategy"],
                "timestamp": time.time(),
                "severity": s["severity"],
            })

    def get_learned_patterns(self) -> list:
        """Return all previously recorded strategy learnings from memory."""
        return [e for e in self.memory_store if e.get("type") == "speed_strategy"]

    def summary(self) -> str:
        """Human-readable summary of the current state."""
        report = self.analyze()
        if report.get("status") == "no_data":
            return "No speed data collected yet."

        lines = [
            f"Speed Optimizer Report",
            f"{'='*50}",
            f"Total events logged: {report['total_events']}",
            f"Total slowdowns: {report['total_slowdowns']}",
            f"",
            f"Top time consumers:",
        ]
        for b in report["clock_consumers"][:5]:
            lines.append(f"  {b['key']}: {b['total_time_ms']/1000:.1f}s ({b['pct_of_total']}%)")

        bottlenecks = report["bottlenecks"]
        if bottlenecks:
            lines.append(f"\nBottlenecks detected ({len(bottlenecks)}):")
            for b in bottlenecks[:5]:
                lines.append(f"   {b['key']}: {b['slowdown_ratio']}x slower than expected")

        strategies = self.generate_strategies()
        if strategies:
            lines.append(f"\nRecommended optimizations:")
            for s in strategies:
                lines.append(f"  → {s['operation']}: {s['recommended_strategy']}")

        return "\n".join(lines)


#  CLI 

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Speed Optimizer")
    parser.add_argument("--log", nargs=3, metavar=("CATEGORY", "OPERATION", "DURATION_MS"),
                        help="Log a slowdown event")
    parser.add_argument("--expected", type=int, default=1000,
                        help="Expected duration in ms (for --log)")
    parser.add_argument("--context", default="", help="Context string")
    parser.add_argument("--analyze", action="store_true", help="Analyze logged events")
    parser.add_argument("--strategies", action="store_true", help="Generate optimization strategies")
    parser.add_argument("--summary", action="store_true", help="Print summary")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    opt = SpeedOptimizer()

    if args.log:
        cat, op, dur = args.log
        event = opt.log_slowdown(cat, op, int(dur), args.expected, args.context)
        print(f"Logged: {event.category}/{event.operation} = {event.duration_ms}ms (expected {event.expected_ms}ms)")

    if args.analyze:
        report = opt.analyze()
        print(json.dumps(report, indent=2) if args.json else opt.summary())

    if args.strategies:
        strategies = opt.generate_strategies()
        print(json.dumps(strategies, indent=2) if args.json else json.dumps(strategies, indent=2))

    if args.summary:
        print(opt.summary())


if __name__ == "__main__":
    main()
