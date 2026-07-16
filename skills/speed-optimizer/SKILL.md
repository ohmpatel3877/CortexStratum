---
name: speed-optimizer
description: Monitors slowdowns logged in memory, analyzes bottleneck patterns, and generates workaround strategies. Learns from past bottlenecks so the same slowdown never hits twice. Integrates with xTrace event logging for cross-session performance tracking.
---

# Speed Optimizer — Self-Learning Performance Optimization

Automatically detects operations that are slower than expected, clusters them by pattern, matches against known bottleneck resolutions, and applies the best strategy. Learns cross-session so recurring slowdowns get automatically mitigated.

## When to Use This Skill

- Pipelines are slowing down and you don't know why
- You want a performance baseline for common operations
- The same slow operation keeps happening across sessions
- Need to decide between competing optimization strategies
- Want to track total time spent on build/install/inference operations

## Architecture

```
Operation completes
       │
       ▼
┌──────────────────┐
│  log_slowdown()  │  ← Call after any timed operation
│  (category, op,  │
│   duration,      │
│   expected)      │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Memory Store     │  ← Events stored as type: speed_event
│  (cross-session)  │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  analyze()        │  ← Clusters by category:operation
│  → bottlenecks    │     Computes avg, ratio, totals
│  → clock_consumers│
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  generate_        │  ← Matches against known patterns
│  strategies()     │     (pip, docker, npm, inference, etc.)
│  → recommendations│     Returns actionable strategies
└──────────────────┘
```

## Usage

### Log a slowdown (call after any timed operation)

```python
from speed_optimizer import SpeedOptimizer

opt = SpeedOptimizer()

# Log a docker build that took 45s when it should take 5s
opt.log_slowdown("tool_call", "docker_build", 45000, 5000)

# Log an npm install that took 30s
opt.log_slowdown("tool_call", "npm_install", 30000, 10000)
```

### Analyze and optimize

```python
# Get full report
report = opt.analyze()
print(f"Bottlenecks: {len(report['bottlenecks'])}")
for b in report['bottlenecks']:
    print(f"  {b['key']}: {b['slowdown_ratio']}x slower")

# Generate resolution strategies
strategies = opt.generate_strategies()
for s in strategies:
    print(f"→ {s['operation']}: try {s['recommended_strategy']}")
```

## Known Bottleneck Patterns

| Operation | Typical Time | Threshold | Best Strategy |
|-----------|-------------|-----------|---------------|
| `pip_install` | 30s | 15s | Switch to `uv` (10-100x faster) |
| `docker_build` | 120s | 30s | Reorder layers for cache efficiency |
| `npm_install` | 45s | 15s | Use `npm ci` instead of `npm install` |
| `model_inference` | 15s | 5s | Prompt compression + parameter virtualizer |
| `file_read` | 2s | 0.5s | Read first N lines, use grep |
| `git_operation` | 5s | 2s | Shallow clone (`--depth 1`) |
| `network_request` | 5s | 2s | Exponential backoff retry |
| `compilation` | 30s | 10s | Incremental compilation |

## Strategy Suggestions

When a pattern is detected, the optimizer will suggest:

```json
{
  "operation": "npm_install",
  "severity": "warning",
  "current_avg_ms": 45000,
  "recommended_strategy": "ci",
  "options": [
    {"name": "pnpm", "description": "Replace npm with pnpm", "effort": "low", "impact": "high"},
    {"name": "ci", "description": "Use npm ci instead of npm install", "effort": "low", "impact": "high"},
    {"name": "cache", "description": "Use npm cache with persistent volume", "effort": "low", "impact": "medium"}
  ]
}
```

## Memory Integration

Events are stored in memory as `type: speed_event`:

```
type: speed_event
operation: npm_install
duration_ms: 45000
expected_ms: 10000
is_slowdown: true
```

Strategies are stored as `type: speed_strategy`:

```
type: speed_strategy
operation: npm_install
recommended: ci
```

## Custom Patterns

Add your own known bottlenecks:

```python
from speed_optimizer import BOTTLENECK_PATTERNS

BOTTLENECK_PATTERNS["terraform_apply"] = {
    "description": "Terraform apply is slow on large infrastructures",
    "typical_ms": 120000,
    "threshold_ms": 30000,
    "strategies": [
        {"name": "parallelism", "description": "Increase parallelism with -parallelism=50", "effort": "low", "impact": "high"},
        {"name": "targeted", "description": "Use -target to apply specific resources only", "effort": "low", "impact": "high"},
        {"name": "pre_plan", "description": "Always run plan first, cache the plan file", "effort": "low", "impact": "medium"},
    ],
    "recommended": "parallelism",
}
```

## CLI

```bash
python scripts/speed_optimizer.py --log tool_call docker_build 45000 --expected 5000
python scripts/speed_optimizer.py --analyze
python scripts/speed_optimizer.py --strategies
python scripts/speed_optimizer.py --summary
python scripts/speed_optimizer.py --analyze --json
```
