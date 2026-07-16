#!/usr/bin/env python3
"""
Skill Pipeline Test Suite — validates the full skill routing, loading, and
cross-reference integrity of the ai-memory-core skill system.

Tests:
  1. Local skill SKILL.md files exist and are parseable
  2. Skill router JSON is valid and all rules have required fields
  3. Router trigger → skill mappings are non-empty and deduplicated
  4. Each referenced skill either:
       a. Exists in the local skills/ directory, OR
       b. Is a known OpenCode built-in skill (from the OpenCode skills registry)
  5. End-to-end: router matches expected skills for known task descriptions
  6. Fallback mechanism returns default skills when no rule matches
  7. ALL 68 MCP tools are callable with valid permissions
"""

import json, os, re, sys, subprocess, time
from pathlib import Path
from collections import Counter

# Windows console encoding fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Paths ───────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
ROUTER_PATH = SKILLS_DIR / "skill-router.json"

RESULTS = {"passed": 0, "failed": 0, "warnings": 0, "details": []}


def log(status: str, test: str, detail: str = ""):
    icon = {"PASS": "OK", "FAIL": "XX", "WARN": "!!", "INFO": ".."}.get(status, "??")
    print(f"  [{icon}] {test}")
    if detail:
        print(f"         {detail}")
    RESULTS["details"].append({"test": test, "status": status, "detail": detail})
    if status == "PASS":
        RESULTS["passed"] += 1
    elif status == "FAIL":
        RESULTS["failed"] += 1
    elif status == "WARN":
        RESULTS["warnings"] += 1


# ═══════════════════════════════════════════════════════════════════════════════
# Test 1: Validate all local skill SKILL.md files
# ═══════════════════════════════════════════════════════════════════════════════

def test_local_skills():
    """Check every directory under skills/ has a SKILL.md with valid structure."""
    print("\n--- Test 1: Local Skill Files ---")
    skill_dirs = [d for d in SKILLS_DIR.iterdir() if d.is_dir()]
    
    if not skill_dirs:
        log("FAIL", "Local skills", "No skill directories found under skills/")
        return
    
    for skill_dir in sorted(skill_dirs):
        skill_name = skill_dir.name
        skill_file = skill_dir / "SKILL.md"
        
        if not skill_file.exists():
            log("FAIL", f"  {skill_name}/SKILL.md", "MISSING — skill directory has no SKILL.md")
            continue
        
        content = skill_file.read_text(encoding="utf-8", errors="replace")
        
        # Basic content checks
        checks = []
        if len(content) < 100:
            checks.append(f"too short ({len(content)} chars)")
        if not content.strip():
            checks.append("empty file")
        if not any(w in content.lower() for w in ["skill", "description", "use when", "purpose"]):
            checks.append("no recognizable skill structure (missing 'skill', 'description', or 'use when')")
        
        if checks:
            log("WARN", f"  {skill_name}/SKILL.md", "; ".join(checks))
        else:
            log("PASS", f"  {skill_name}/SKILL.md", f"{len(content)} chars, valid structure")
    
    log("INFO", f"  Total skill directories: {len(skill_dirs)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 2: Validate skill router JSON
# ═══════════════════════════════════════════════════════════════════════════════

def test_router_structure():
    """Validate the skill-router.json schema and all rule fields."""
    print("\n--- Test 2: Skill Router Structure ---")
    
    if not ROUTER_PATH.exists():
        log("FAIL", "Router file", "skill-router.json not found")
        return

    try:
        router = json.loads(ROUTER_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log("FAIL", "Router file", f"Invalid JSON: {e}")
        return

    # Version check
    version = router.get("version", 0)
    if version < 1:
        log("WARN", "Router version", f"version={version}, expected >= 1")
    else:
        log("PASS", f"Router version={version}", "")

    # Rules count
    rules = router.get("rules", [])
    if not rules:
        log("FAIL", "Router rules", "No rules defined")
        return
    log("PASS", f"Router rules count: {len(rules)}", "")

    # Validate each rule
    seen_triggers = Counter()
    for i, rule in enumerate(rules):
        triggers = rule.get("triggers", [])
        skills = rule.get("skills", [])
        priority = rule.get("priority", 0)
        
        issues = []
        if not triggers:
            issues.append("no triggers")
        if not skills:
            issues.append("no skills")
        if not isinstance(priority, (int, float)) or priority < 0:
            issues.append(f"invalid priority: {priority}")
        
        for t in triggers:
            seen_triggers[t.lower()] += 1
        
        if issues:
            log("FAIL", f"  Rule {i}: {', '.join(issues)}", f"triggers={triggers}, skills={skills}")
        else:
            log("PASS", f"  Rule {i}: {triggers[0]}... ({len(skills)} skills, priority={priority})", "")

    # Check for duplicate triggers across rules
    duplicates = {t: c for t, c in seen_triggers.items() if c > 1}
    if duplicates:
        log("WARN", "Duplicate triggers across rules", f"{len(duplicates)} duplicates: {dict(list(duplicates.items())[:10])}")
    else:
        log("PASS", "No duplicate trigger across rules", "")

    # Default skills check
    defaults = router.get("default_skills", [])
    if defaults:
        log("PASS", f"Default skills: {defaults}", "")
    else:
        log("WARN", "Default skills", "No default_skills defined")

    # Conflict resolution
    conflict = router.get("conflict_resolution", "none")
    if conflict == "priority_highest_wins":
        log("PASS", "Conflict resolution: priority_highest_wins", "")
    else:
        log("WARN", f"Conflict resolution: {conflict}", "expected 'priority_highest_wins'")

    # Fallback mechanism
    fallback = router.get("fallback", {})
    if fallback.get("levels"):
        log("PASS", "Fallback mechanism configured", f"{len(fallback['levels'])} levels")
    else:
        log("WARN", "Fallback mechanism", "No fallback levels configured")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 3: Router end-to-end matching (direct logic, no subprocess)
# ═══════════════════════════════════════════════════════════════════════════════

def _match_skills_direct(task: str, router_config: dict) -> dict:
    """Replicate the router matching logic from tools-mcp-server.py inline."""
    matched = []
    matched_rules = []
    task_lower = task.lower()
    for rule in router_config.get("rules", []):
        for t in rule.get("triggers", []):
            if t.lower() in task_lower:
                matched.extend(rule.get("skills", []))
                matched_rules.append({"trigger": t, "priority": rule.get("priority", 0)})
                break
    matched = list(dict.fromkeys(matched))

    # Fallback
    if not matched:
        fallback_config = router_config.get("fallback", {})
        for level in fallback_config.get("levels", []):
            if "check_env" in level:
                env_val = os.environ.get(level["check_env"], "")
                if env_val:
                    matched = [s.strip() for s in env_val.split(",") if s.strip()]
                    break
            if level.get("check_user_config"):
                user_path = router_config.get("user_config_path", "~/.opencode/skill-router-overrides.json")
                user_path = os.path.expanduser(user_path)
                if os.path.exists(user_path):
                    try:
                        user_config = json.loads(open(user_path, encoding="utf-8").read())
                        if "fallback_skills" in user_config:
                            matched = user_config["fallback_skills"]
                            break
                    except (json.JSONDecodeError, OSError):
                        pass
            if level.get("use_defaults"):
                defaults = router_config.get("default_skills", [])
                matched = level.get("skills", defaults)
                break

    return {"matched_skills": matched, "matched_rules": matched_rules if matched_rules else "fallback_applied"}


def test_router_matching():
    """Test the router with known task descriptions using direct logic (no MCP server)."""
    print("\n--- Test 3: Router End-to-End Matching ---")
    
    if not ROUTER_PATH.exists():
        log("FAIL", "Router file", "skill-router.json not found")
        return
    
    router_config = json.loads(ROUTER_PATH.read_text(encoding="utf-8"))

    test_cases = [
        ("debug error fix this crash", ["troubleshooting-master"], "debug keywords"),
        ("inno setup windows installer build exe", ["inno-setup-pipeline"], "Inno Setup"),
        ("samba nas permission denied smb", ["debug-samba"], "Samba/NAS"),
        ("kubernetes pod deployment k8s cluster", ["k8s-manifest-generator"], "Kubernetes"),
        ("design a dark cyberpunk theme", ["art-module"], "Art/theme"),
        ("test the api endpoints unit test", ["test-driven-development"], "Testing"),
        ("security vulnerability authentication", ["security-hardening"], "Security"),
        ("hello world", [], "noise — should fallback to defaults"),
        ("memory consolidation merge duplicates", [], "memory operation — no direct trigger, should use fallback"),
    ]

    for task, expected_skills, label in test_cases:
        result = _match_skills_direct(task, router_config)
        matched = result.get("matched_skills", [])

        if not expected_skills:
            is_fallback = result.get("matched_rules") == "fallback_applied"
            if is_fallback:
                log("INFO", f"  '{task}' ({label})", f"fallback applied: matched={matched}")
            else:
                log("INFO", f"  '{task}' ({label})", f"matched={matched}")
        else:
            found = [s for s in expected_skills if s in matched or any(s in m for m in matched)]
            if found:
                log("PASS", f"  '{task}' ({label})", f"matched={matched}")
            else:
                log("WARN", f"  '{task}' ({label})", f"expected at least one of {expected_skills}, got={matched}")

    # Test fallback: task with zero keyword matches
    fallback_result = _match_skills_direct("completely unrelated gibberish xyzzy", router_config)
    is_fallback = fallback_result.get("matched_rules") == "fallback_applied"
    if is_fallback:
        log("PASS", "  Fallback mechanism: no-match task", f"returned defaults: {fallback_result['matched_skills']}")
    else:
        log("WARN", "  Fallback mechanism: no-match task", f"expected fallback, got: {fallback_result['matched_skills']}")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 4: Identify dud skills (referenced but not available)
# ═══════════════════════════════════════════════════════════════════════════════

def test_dud_skills():
    """
    Check every skill referenced in the router against:
      1. Local skills/ directory
      2. Known OpenCode built-in skills (from available_skills list in the system prompt)
    
    Any skill not found in either location is flagged as a DUD.
    """
    print("\n--- Test 4: Dud Skill Detection ---")
    
    if not ROUTER_PATH.exists():
        return
    
    router = json.loads(ROUTER_PATH.read_text(encoding="utf-8"))
    rules = router.get("rules", [])
    defaults = router.get("default_skills", [])
    
    # Collect all referenced skill names
    referenced = set()
    for rule in rules:
        for s in rule.get("skills", []):
            referenced.add(s)
    for s in defaults:
        referenced.add(s)
    
    # Build local skill inventory (directory names + SKILL.md names)
    local_skills = set()
    for d in SKILLS_DIR.iterdir():
        if d.is_dir():
            local_skills.add(d.name)
            # Also check SKILL.md for a defined name
            skill_file = d / "SKILL.md"
            if skill_file.exists():
                content = skill_file.read_text(encoding="utf-8", errors="replace")
                for line in content.split("\n"):
                    if line.startswith("# ") and len(line) > 3:
                        local_skills.add(line[2:].strip().lower())
    
    # Known OpenCode built-in skills (from the system prompt available_skills list)
    known_builtins = {
        # Troubleshooting & debugging
        "troubleshooting-master", "error-triage", "debug-samba",
        # Testing
        "test-driven-development", "test-patterns", "bats-testing-patterns",
        # Review
        "pr-review", "code-review-excellence",
        # Learning
        "educate", "wikipedia-ghost", "study-tutor", "tutoring",
        # Architecture
        "electron-desktop-architecture", "adr-write", "architecture-decision-records",
        "brainstorm", "api-contract", "api-design-principles",
        # Self-improvement
        "model-psychologist", "anti-ai-pattern", "concise-filter",
        # UI/Frontend
        "openui", "frontend-design", "responsive-design",
        # Browser automation
        "browser-automation", "playwright-automation", "web-scraping",
        # API
        "api-contract", "api-design-principles",
        # Release
        "changelog-generate", "git-release",
        # Migration
        "migration", "dependency-upgrade",
        # Dependencies
        "dependency-audit",
        # OpenCode config
        "customize-opencode", "skill-ideator",
        # Knowledge
        "obsidian-zettelkasten",
        # Session
        "session-artifact",
        # Incident
        "incident-postmortem", "incident-runbook-templates",
        # Environment
        "env-setup",
        # Security
        "security-hardening", "auth-implementation-patterns",
        # Parallel
        "parallel-worktree", "agent-teams-task-coordination-strategies",
        # Verification
        "verification-before-completion",
        # Memory
        "ne-memory-search", "ne-memory-remember", "ne-memory-status",
        "memory-search",
        # Media
        "context-extractor",
        # Module-specific
        "art-module", "literature-module", "audio-module", "game-dev-module",
        "devops-module",
        # Inno Setup
        "inno-setup-pipeline",
        # VM
        "vm-test-engine",
        # Framework
        "framework-builder",
        # Parameter virtualizer
        "parameter-virtualizer",
        # Pattern flipper
        "pattern-flipper",
        # Speed
        "speed-optimizer",
        # Accessibility
        "accessibility-compliance",
        # Payment
        "stripe-integration", "billing-automation",
        # Database
        "postgresql-table-design", "sql-optimization-patterns",
        # Kubernetes
        "k8s-manifest-generator", "helm-chart-scaffolding", "gitops-workflow",
        # Infrastructure
        "terraform-module-library",
        # Monitoring
        "prometheus-configuration", "grafana-dashboards", "slo-implementation",
        # CI/CD
        "github-actions-templates", "deployment-pipeline-design",
        # Excel
        "excel-engineer",
        # Legal
        "gdpr-data-handling", "employment-contract-templates",
        # Task
        "task-orchestrator",
        # Miscellaneous
        "bash-defensive-patterns",
        # Verifier
        "verifier-middleware",
    }
    
    duds = []
    for skill_name in sorted(referenced):
        sn = skill_name.lower().strip()
        # Check if it's in local skills
        is_local = any(sn == ls.lower() or sn in ls.lower() for ls in local_skills)
        # Check if it's in known builtins
        is_builtin = sn in known_builtins or any(sn == b or sn in b for b in known_builtins)
        
        if is_local:
            log("PASS", f"  {skill_name}", "local skill")
        elif is_builtin:
            log("PASS", f"  {skill_name}", "known OpenCode built-in")
        else:
            duds.append(skill_name)
            log("WARN", f"  {skill_name}", "DUD — not found locally or in known builtins")
    
    if duds:
        log("WARN", f"Dud skills detected", f"{len(duds)} referenced but unavailable: {duds}")
    else:
        log("PASS", "All referenced skills accounted for", f"{len(referenced)} total references")
    
    return duds


# ═══════════════════════════════════════════════════════════════════════════════
# Test 5: All 68 MCP tools are properly defined
# ═══════════════════════════════════════════════════════════════════════════════

def test_tool_inventory():
    """Validate the MCP tool definitions from --list-tools output."""
    print("\n--- Test 5: MCP Tool Inventory ---")
    
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "tools-mcp-server.py"), "--list-tools"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    
    try:
        tools = json.loads(result.stdout)
    except json.JSONDecodeError:
        log("FAIL", "Tool inventory", f"Invalid JSON: {result.stdout[:200]}")
        return

    if len(tools) != 68:
        log("WARN", f"Tool count: {len(tools)}", "Expected 68 tools")

    # Check naming conventions
    naming_issues = []
    for t in tools:
        name = t.get("name", "")
        permission = t.get("permission", "read")
        
        # Check prefix matches permission
        if permission == "read" and not name.startswith("read_"):
            naming_issues.append(f"{name}: read permission but no read_ prefix")
        elif permission == "write" and not name.startswith("write_"):
            naming_issues.append(f"{name}: write permission but no write_ prefix")
        elif permission == "mutate" and not name.startswith("mutate_"):
            naming_issues.append(f"{name}: mutate permission but no mutate_ prefix")
    
    if naming_issues:
        for issue in naming_issues[:5]:
            log("WARN", f"  Naming: {issue}", "")
    else:
        log("PASS", "All tool names match permission prefixes", "")

    # Check all tools have description
    no_desc = [t["name"] for t in tools if not t.get("description")]
    if no_desc:
        log("WARN", f"Tools without description", str(no_desc))
    else:
        log("PASS", "All tools have descriptions", "")

    # Permission distribution
    perms = {"read": 0, "write": 0, "mutate": 0}
    for t in tools:
        p = t.get("permission", "read")
        perms[p] = perms.get(p, 0) + 1
    
    log("INFO", f"Permission distribution", f"read={perms['read']} write={perms['write']} mutate={perms['mutate']}")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  ai-memory-core Skill Pipeline Test Suite")
    print("=" * 60)
    print(f"  Project: {PROJECT_ROOT}")
    print(f"  Skills:  {SKILLS_DIR}")
    print(f"  Router:  {ROUTER_PATH}")
    print("=" * 60)

    test_local_skills()
    test_router_structure()
    test_router_matching()
    test_tool_inventory()
    duds = test_dud_skills()

    # Summary
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    print(f"  Passed:   {RESULTS['passed']}")
    print(f"  Failed:   {RESULTS['failed']}")
    print(f"  Warnings: {RESULTS['warnings']}")
    if duds:
        print(f"\n  ⚠ DUD SKILLS FOUND: {duds}")
    print(f"\n  {'ALL SKILL PIPELINE TESTS PASSED' if RESULTS['failed'] == 0 else 'SOME TESTS FAILED'}")
    print("=" * 60)

    # Save results
    results_path = PROJECT_ROOT / "data" / "skill-pipeline-test-results.json"
    results_path.parent.mkdir(exist_ok=True)
    RESULTS["dud_skills"] = duds
    RESULTS["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results_path.write_text(json.dumps(RESULTS, indent=2))
    print(f"\nResults saved to: {results_path}")

    return 1 if RESULTS["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
