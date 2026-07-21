#!/usr/bin/env python3
"""
mutation-module.py — Algorithmic Mutation Phase (/mutate)

Master Spec:
  1. Scope Assessment — parse execution triggers → functional boundaries + target metrics
  2. Redundancy Audit — scan tool inventories + DAGs for overlapping execution flows
  3. Execution — codebase audit → bottleneck ID → recursive algorithmic refactoring
  4. Validation — strict cross-validation against core database before committing
"""

import hashlib
import re
import time
from pathlib import Path

from utils import load_json, save_json

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data"
SCRIPTS_DIR = BASE


def _load_tool_inventory():
    """Load the current tool inventory from tools-mcp-server or cached file."""
    inv_path = DATA_DIR / "tool-inventory.json"
    if inv_path.exists():
        return load_json(inv_path, {})
    # Fallback: try to import from the server
    try:
        import importlib.util as _util

        spec = _util.spec_from_file_location(
            "tools_server", str(SCRIPTS_DIR / "tools-mcp-server.py")
        )
        if spec and spec.loader:
            mod = _util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            tools = getattr(mod, "TOOLS", [])
            inventory = {
                t["name"]: {
                    "permission": t.get("permission"),
                    "has_dry_run": "dry_run" in str(t.get("inputSchema", {})),
                }
                for t in tools
            }
            save_json(inv_path, inventory)
            return inventory
    except Exception as e:
        return {"error": str(e)}
    return {}


#
# Scope Assessment
#


def assess_scope(trigger_text=""):
    """
    Parse execution triggers to define functional boundaries and target metrics.

    Analyzes a trigger text (e.g., task description, error log, command) and
    identifies:
    - Domain(s) involved
    - Tools likely needed
    - Functional boundaries (what's in/out of scope)
    - Target metrics for success
    """
    trigger_lower = trigger_text.lower() if trigger_text else ""

    # Domain detection
    domain_keywords = {
        "memory": ["memory", "remember", "forget", "recall", "store", "bm25"],
        "simulation": [
            "simulate",
            "fea",
            "cfd",
            "stress",
            "buckle",
            "fatigue",
            "mechanics",
            "beam",
        ],
        "compact": ["compact", "compress", "condense", "token", "velocity"],
        "sensory": ["browse", "scrape", "screenshot", "pdf", "ocr", "web"],
        "code": [
            "code",
            "review",
            "analyze",
            "refactor",
            "debug",
            "python",
            "typescript",
        ],
        "pipeline": ["verify", "check", "test", "validate", "gate", "pipeline"],
        "system": ["config", "permission", "tool", "server", "status", "health"],
    }
    detected_domains = []
    for domain, kws in domain_keywords.items():
        if any(kw in trigger_lower for kw in kws):
            detected_domains.append(domain)
    if not detected_domains:
        detected_domains.append("general")

    # Tool suggestion based on domain
    domain_tool_map = {
        "memory": [
            "read_memory_search",
            "write_memory_add",
            "read_memory_synthesize",
            "write_memory_consolidate",
        ],
        "compact": [
            "read_compact_token_velocity",
            "read_compact_synthesize",
            "write_compact_execute",
        ],
        "sensory": [
            "read_sensory_browse",
            "read_sensory_screenshot",
            "read_sensory_extract_pdf",
        ],
        "code": ["read_coder_analyze_code", "read_coder_review", "read_coder_debug"],
        "pipeline": ["read_verifier_status", "read_compact_status"],
        "system": [
            "read_xtrace_status",
            "read_goal_registry_status",
            "read_audit_status",
        ],
    }
    suggested_tools = []
    for d in detected_domains:
        suggested_tools.extend(domain_tool_map.get(d, []))
    suggested_tools = list(dict.fromkeys(suggested_tools))  # dedupe preserve order

    # Metrics
    metrics = {
        "domains": len(detected_domains),
        "suggested_tools": len(suggested_tools),
        "trigger_length": len(trigger_text),
    }

    return {
        "scope_id": hashlib.md5(trigger_text.encode()).hexdigest()[:8],
        "trigger_analyzed": trigger_text[:200]
        + ("..." if len(trigger_text) > 200 else ""),
        "detected_domains": detected_domains,
        "suggested_tools": suggested_tools[:10],
        "metrics": metrics,
        "assessment": "Scope defined. Proceed to redundancy audit before execution.",
    }


#
# Redundancy Audit
#


def audit_redundancy(scope_id="", domains=None):
    """
    Scan tool inventories and active DAGs for overlapping execution flows.
    Detects:
    - Tools with similar names/purposes (potential duplicates)
    - Tools that could be merged
    - Orphaned tools (defined but never referenced in dispatch)
    - Feature bloat indicators
    """
    inventory = _load_tool_inventory()
    if isinstance(inventory, dict) and "error" in inventory:
        return {
            "error": inventory["error"],
            "note": "Run tools-mcp-server.py first to build inventory",
        }

    # Normalize: inventory may be a dict {name: info} or a list of tool dicts
    if isinstance(inventory, list):
        tool_names = [t.get("name", f"tool_{i}") for i, t in enumerate(inventory)]
    else:
        tool_names = list(inventory.keys())

    # Detect naming overlaps: tools sharing the same prefix after read_/write_/mutate_
    prefix_groups = {}
    for name in tool_names:
        # Strip permission prefix
        core = re.sub(r"^(read_|write_|mutate_)", "", name)
        # Group by first segment
        segment = core.split("_")[0] if "_" in core else core
        prefix_groups.setdefault(segment, []).append(name)

    # Flag groups with 3+ tools as potential redundancy clusters
    redundancy_clusters = {k: v for k, v in prefix_groups.items() if len(v) >= 3}

    # Check for orphaned patterns: tools whose module might not exist
    module_map = {
        "xtrace": "trace.py",
        "dtrace": "trace.py",
        "goal_registry": "trace.py",
        "commitment_checker": "trace.py",
        "compact": "compact-module.py",
        "sim_mech": "simulation/sim-mechanics-module.py",
        "sensory": "sensory-module.py",
        "audio": "audio-module.py",
        "coder": "coder-module.py",
        "devops": "devops-module.py",
        "gamedev": "game-dev-module.py",
        "memory": "memory_search.py",
        "verifier": "verifier_middleware.py",
        "hooks": "hooks.py",
        "art": "art-module.py",
        "lit": "literature-module.py",
        "skill_router": "tools-mcp-server.py",
        "tools": "tool_router.py",
        "audit": "permission_audit.py",
        "undo": "permission_audit.py",
    }

    unlinked = []
    for name in tool_names:
        core = re.sub(r"^(read_|write_|mutate_)", "", name)
        module_key = core.split("_")[0] if "_" in core else core
        if module_key not in module_map:
            unlinked.append(name)

    return {
        "total_tools": len(tool_names),
        "redundancy_clusters": {
            k: v for k, v in list(redundancy_clusters.items())[:10]
        },
        "cluster_count": len(redundancy_clusters),
        "unlinked_tools": unlinked[:10],
        "unlinked_count": len(unlinked),
        "scope_id": scope_id,
        "audit_result": "PASS"
        if len(unlinked) == 0
        else f"{len(unlinked)} tools with unrecognized module mapping",
        "recommendation": "No action needed"
        if len(unlinked) == 0 and len(redundancy_clusters) <= 2
        else "Review flagged clusters for consolidation opportunities",
    }


#
# Execution
#

_last_mutation = None


def execute_mutation(scope_id="", dry_run=False):
    """
    Execute the full mutation cycle:
    1. Load scope assessment
    2. Run redundancy audit
    3. Generate refactoring recommendations
    4. Record mutation event (unless dry_run)
    """
    global _last_mutation

    # Step 1-2: Run audit
    audit = audit_redundancy(scope_id)

    # Step 3: Generate refactoring plan
    refactors = []
    if audit.get("cluster_count", 0) > 2:
        for cluster_name, tools in list(audit.get("redundancy_clusters", {}).items())[
            :5
        ]:
            refactors.append(
                {
                    "type": "consolidation",
                    "target": cluster_name,
                    "tools_involved": len(tools),
                    "suggestion": f"Consider consolidating {len(tools)} tools sharing '{cluster_name}' prefix",
                }
            )

    if audit.get("unlinked_count", 0) > 0:
        refactors.append(
            {
                "type": "mapping",
                "target": "unlinked_tools",
                "count": audit["unlinked_count"],
                "suggestion": "Add module mappings for unlinked tools in mutation-module.py module_map",
            }
        )

    mutation = {
        "mutation_id": hashlib.md5(f"{scope_id}{time.time()}".encode()).hexdigest()[
            :12
        ],
        "timestamp": time.time(),
        "scope_id": scope_id,
        "audit": {
            "total_tools": audit["total_tools"],
            "clusters_found": audit["cluster_count"],
            "unlinked_found": audit["unlinked_count"],
            "passed": audit["audit_result"],
        },
        "refactoring_plan": refactors,
        "refactor_count": len(refactors),
        "dry_run": dry_run,
        "status": "simulated" if dry_run else "executed",
    }

    if not dry_run:
        # Persist the mutation record
        history = load_json(DATA_DIR / "mutation-history.json", {"mutations": []})
        history.setdefault("mutations", []).append(
            {
                "mutation_id": mutation["mutation_id"],
                "timestamp": mutation["timestamp"],
                "scope_id": scope_id,
                "refactor_count": len(refactors),
            }
        )
        save_json(DATA_DIR / "mutation-history.json", history)
        _last_mutation = mutation
    else:
        mutation["note"] = "Dry run only. Execute without dry_run=true to commit."

    return mutation


#
# Status
#


def get_status():
    """Return current mutation state and history."""
    global _last_mutation
    history = load_json(DATA_DIR / "mutation-history.json", {"mutations": []})
    last = history.get("mutations", [])
    return {
        "last_mutation": _last_mutation,
        "mutation_count": len(last),
        "last_timestamp": last[-1]["timestamp"] if last else None,
        "recent_mutations": last[-5:] if last else [],
    }


#
# Handler Dispatch
#


def handle_tool_call(name, args):
    if name == "read_mutate_scope":
        return assess_scope(args.get("trigger", ""))
    elif name == "read_mutate_audit":
        return audit_redundancy(args.get("scope_id", ""), args.get("domains"))
    elif name == "mutate_execute":
        return execute_mutation(args.get("scope_id", ""), args.get("dry_run", False))
    elif name == "read_mutate_status":
        return get_status()
    return {"error": f"Unknown mutation tool: {name}"}
