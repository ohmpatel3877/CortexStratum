#!/usr/bin/env python3
"""
Task Analyzer — Evaluates task complexity and recommends execution mode.
Part of the auto-orchestration framework.

Usage:
    python scripts/task-analyzer.py --task "Implement login with OAuth"
    python scripts/task-analyzer.py --file description.txt
    python scripts/task-analyzer.py --interactive
"""

import json, sys, re, math
sys.stdout.reconfigure(encoding="utf-8")

# ============================================================
# Complexity Factors
# ============================================================

HIGH_RISK_KW = ["security", "auth", "authentication", "oauth", "payment", "stripe",
                "migration", "data-loss", "sql injection", "xss", "csp",
                "encryption", "password", "pii", "gdpr", "database schema",
                "breaking change", "rollback", "audit", "compliance"]

MEDIUM_RISK_KW = ["refactor", "redesign", "restructure", "optimize", "performance",
                  "test suite", "ci/cd", "deploy", "docker", "kubernetes",
                  "monitoring", "logging", "error handling", "retry", "timeout"]

TECH_KEYWORDS = {
    "frontend": ["react", "vue", "angular", "html", "css", "tailwind", "ui", "component"],
    "backend": ["api", "rest", "graphql", "server", "route", "middleware", "controller"],
    "database": ["sql", "nosql", "migrat", "schema", "query", "orm", "prisma", "drizzle"],
    "infra": ["docker", "kubernetes", "deploy", "ci", "cd", "terraform", "ansible"],
    "auth": ["oauth", "jwt", "login", "session", "password", "saml"],
    "testing": ["test", "jest", "pytest", "e2e", "unit test", "integration"],
}

def analyze_task(task: str) -> dict:
    """Analyze a task description and return complexity scores."""
    task_lower = task.lower()
    words = task_lower.split()
    
    # Factor 1: Files affected (estimate from task description)
    file_mentions = len(re.findall(r'\b\w+\.\w+\b', task))
    file_patterns = len(re.findall(r'(?:file|module|component|class|function|route|endpoint)\b', task_lower))
    file_score = min(10, (file_mentions * 2) + file_patterns)
    
    # Factor 2: Tech domains
    domains_found = set()
    for domain, kws in TECH_KEYWORDS.items():
        if any(kw in task_lower for kw in kws):
            domains_found.add(domain)
    domain_score = min(10, len(domains_found) * 3)
    
    # Factor 3: Risk
    high_risk = sum(1 for kw in HIGH_RISK_KW if kw in task_lower)
    med_risk = sum(1 for kw in MEDIUM_RISK_KW if kw in task_lower)
    risk_score = min(10, high_risk * 3 + med_risk)
    
    # Factor 4: Independence (can work be parallelized?)
    independence_keywords = ["and", "also", "separate", "independent", "both", "multiple",
                             "each", "individually", "separately", "in parallel"]
    dep_keywords = ["then", "after", "before", "depends", "requires", "prerequisite",
                    "first", "once", "when", "sequential"]
    indep_count = sum(1 for kw in independence_keywords if kw in task_lower)
    dep_count = sum(1 for kw in dep_keywords if kw in task_lower)
    independence_score = min(10, max(0, indep_count * 3 - dep_count * 2))
    
    # Factor 5: Domain novelty (estimate from task description)
    # Longer, more detailed tasks tend to be more familiar ground
    novelty_score = 5  # default medium
    if len(task) > 500:
        novelty_score = 3  # well-specified = less novel
    elif len(task) < 100:
        novelty_score = 7  # vague = more novel
    if "first time" in task_lower or "never" in task_lower or "new to" in task_lower:
        novelty_score += 2
    
    # Factor 6: Business logic complexity
    logic_keywords = ["state", "state machine", "workflow", "transaction", "validation",
                      "business rule", "condition", "branch", "edge case", "error state",
                      "rollback", "concurrency", "race", "locking"]
    logic_score = min(10, sum(1 for kw in logic_keywords if kw in task_lower) * 2)
    
    # Word count as complexity signal
    word_count = len(words)
    size_score = min(10, word_count // 30)
    
    # Total score (weighted)
    scores = {
        "file_impact": file_score,
        "domain_count": domain_score,
        "risk_level": risk_score,
        "parallelism": independence_score,
        "novelty": novelty_score,
        "logic_depth": logic_score,
        "task_size": size_score,
    }
    
    # Weighted total
    weights = {
        "file_impact": 1.5,
        "domain_count": 1.5,
        "risk_level": 2.0,
        "parallelism": 1.0,
        "novelty": 1.0,
        "logic_depth": 1.5,
        "task_size": 0.5,
    }
    
    total = sum(scores[k] * weights[k] for k in scores)
    max_total = sum(10 * weights[k] for k in scores)
    normalized = (total / max_total) * 100
    
    # Determine mode
    if normalized < 25:
        mode = "direct"
        threshold = "LOW"
    elif normalized < 45:
        mode = "split"
        threshold = "MEDIUM"
    elif normalized < 65:
        mode = "orchestrate"
        threshold = "HIGH"
    else:
        mode = "pipeline"
        threshold = "CRITICAL"
    
    # Recommended subagents
    if mode == "direct":
        subagents = 0
    elif mode == "split":
        subagents = 2
    elif mode == "orchestrate":
        subagents = min(5, max(3, len(domains_found)))
    else:
        subagents = min(8, len(domains_found) + 2)
    
    return {
        "score": round(normalized, 1),
        "threshold": threshold,
        "mode": mode,
        "recommended_subagents": subagents,
        "factors": {k: round(v, 1) for k, v in scores.items()},
        "domains": list(domains_found),
        "high_risk_flags": [kw for kw in HIGH_RISK_KW if kw in task_lower],
        "can_parallelize": mode in ("orchestrate", "pipeline") or independence_score >= 6,
        "summary": f"Complexity: {threshold} ({normalized:.0f}/100) → Mode: {mode.upper()} ({subagents} agents)"
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Task complexity analyzer")
    parser.add_argument("--task", type=str, help="Task description to analyze")
    parser.add_argument("--file", type=str, help="File containing task description")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--threshold", type=int, default=12, help="Minimum score for parallel mode (default: 12)")
    
    args = parser.parse_args()
    
    if args.file:
        with open(args.file) as f:
            task = f.read()
    elif args.task:
        task = args.task
    elif args.interactive:
        print("Enter task description (Ctrl+Z then Enter to finish):")
        task = sys.stdin.read()
    else:
        # Default: analyze the current session context from a temp file if it exists
        try:
            with open("C:\\Users\\ohmpa\\github\\CortexStratum\\data\\last-task.txt") as f:
                task = f.read()
        except FileNotFoundError:
            print("Usage: python task-analyzer.py --task \"<task description>\"")
            sys.exit(1)
    
    result = analyze_task(task)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 60)
        print(f"  TASK ANALYSIS")
        print("=" * 60)
        print(f"  Score:    {result['score']}/100")
        print(f"  Level:    {result['threshold']}")
        print(f"  Mode:     {result['mode'].upper()}")
        print(f"  Agents:   {result['recommended_subagents']} subagents recommended")
        print(f"  Domains:  {', '.join(result['domains']) or 'none detected'}")
        print(f"  Risks:    {', '.join(result['high_risk_flags']) or 'none'}")
        print(f"  Parallel: {'YES' if result['can_parallelize'] else 'No'}")
        print()
        print("  Factor Breakdown:")
        for factor, score in result['factors'].items():
            bar = "" * max(1, int(score)) + "" * max(0, 10 - max(1, int(score)))
            print(f"    {factor:15s} [{score:>4.0f}/10] {bar}")
        print()
        print(f"  Summary: {result['summary']}")
