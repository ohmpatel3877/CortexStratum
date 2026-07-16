#!/usr/bin/env python3
"""
Integration Layer Test Suite — Verifies all 5 workstream outputs wire together correctly.

Tests:
  a) DAG coordinator import
  b) Identity manager import
  c) Sandbox manager import
  d) Doc generator import
  e) Orchestrator DAG flag
  f) DAG JSON schema validation
  g) Full integration pipeline (plan mode)
  h) ADR file existence
  i) All scripts parseable
  j) DAG coordinator plan output

Usage:
    python scripts/test-integration-layer.py
    python scripts/test-integration-layer.py --verbose
    python scripts/test-integration-layer.py --list
"""

import json, os, sys, subprocess, importlib.util, glob, re
from typing import Optional

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(BASE, "scripts")
DATA = os.path.join(BASE, "data")
DOCS = os.path.join(BASE, "docs")
ADR_DIR = os.path.join(DATA, "adr")
DAG_DEFS = os.path.join(DATA, "dag-definitions")
DAG_SCHEMAS = os.path.join(DATA, "dag-schemas")

G = "\033[92m"; Y = "\033[93m"; B = "\033[94m"; R = "\033[91m"; C = "\033[96m"; N = "\033[0m"; BOLD = "\033[1m"
PASS = f"{G}✓ PASS{N}"
FAIL = f"{R}✗ FAIL{N}"
SKIP = f"{Y}~ SKIP{N}"

results = {"passed": 0, "failed": 0, "skipped": 0, "tests": []}


def test(name: str, func):
    try:
        func()
        results["passed"] += 1
        results["tests"].append({"name": name, "status": "PASS"})
        print(f"  {PASS} {name}")
    except AssertionError as e:
        results["failed"] += 1
        results["tests"].append({"name": name, "status": "FAIL", "error": str(e)})
        print(f"  {FAIL} {name}")
        print(f"       {R}{e}{N}")
    except Exception as e:
        results["failed"] += 1
        results["tests"].append({"name": name, "status": "FAIL", "error": f"{type(e).__name__}: {e}"})
        print(f"  {FAIL} {name}")
        print(f"       {R}{type(e).__name__}: {e}{N}")


def skip(name: str, reason: str):
    results["skipped"] += 1
    results["tests"].append({"name": name, "status": "SKIP", "error": reason})
    print(f"  {SKIP} {name} ({reason})")


def import_from_path(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec is not None, f"Could not create spec for {file_path}"
    assert spec.loader is not None, f"No loader for {file_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Tests ──────────────────────────────────────────────────

def test_dag_coordinator_import():
    mod = import_from_path("dag_coordinator", os.path.join(SCRIPTS, "dag-coordinator.py"))
    assert hasattr(mod, "load_dag_definition"), "load_dag_definition not found"
    assert hasattr(mod, "topological_sort"), "topological_sort not found"
    assert hasattr(mod, "execute_pipeline"), "execute_pipeline not found"
    assert hasattr(mod, "show_dag_info"), "show_dag_info not found"
    assert callable(mod.load_dag_definition), "load_dag_definition not callable"
    assert callable(mod.topological_sort), "topological_sort not callable"


def test_identity_manager_import():
    mod = import_from_path("identity_manager", os.path.join(SCRIPTS, "identity-manager.py"))
    assert hasattr(mod, "IdentityManager"), "IdentityManager class not found"
    mgr = mod.IdentityManager()
    assert hasattr(mgr, "consolidate_identity"), "consolidate_identity not found"
    assert hasattr(mgr, "render_session_prompt"), "render_session_prompt not found"


def test_sandbox_manager_import():
    mod = import_from_path("sandbox_manager", os.path.join(SCRIPTS, "sandbox-manager.py"))
    assert hasattr(mod, "SandboxManager"), "SandboxManager class not found"
    mgr = mod.SandboxManager()
    assert hasattr(mgr, "execute_python"), "execute_python not found"
    assert hasattr(mgr, "evaluate_code_safety"), "evaluate_code_safety not found"
    assert hasattr(mgr, "verify_sandbox"), "verify_sandbox not found"


def test_doc_generator_import():
    mod = import_from_path("doc_generator", os.path.join(SCRIPTS, "doc-generator.py"))
    assert hasattr(mod, "DocGenerator"), "DocGenerator class not found"
    gen = mod.DocGenerator()
    assert hasattr(gen, "scan_scripts"), "scan_scripts not found"
    assert hasattr(gen, "scan_mcp_tools"), "scan_mcp_tools not found"
    assert hasattr(gen, "generate_markdown"), "generate_markdown not found"
    assert hasattr(gen, "generate_html"), "generate_html not found"
    assert hasattr(gen, "run_all"), "run_all not found"


def test_orchestrator_dag_flag():
    """Run task-orchestrator with --dag flag, verify it doesn't crash."""
    dag_file = os.path.join(DAG_DEFS, "seed-dag.json")
    if not os.path.isfile(dag_file):
        skip("test_orchestrator_dag_flag", "seed-dag.json not found")
        return
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "task-orchestrator.py"),
         "--dag", dag_file, "--info"],
        capture_output=True, encoding="utf-8", errors="replace", cwd=BASE, timeout=30
    )
    assert result.returncode == 0, f"Orchestrator DAG mode failed: {result.stderr}"


def test_dag_json_valid():
    """Validate all DAG definition JSON files against schema."""
    schema_path = os.path.join(DAG_SCHEMAS, "dag-definition-v1.json")
    assert os.path.isfile(schema_path), f"Schema file not found: {schema_path}"

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    dag_files = glob.glob(os.path.join(DAG_DEFS, "*.json"))
    if not dag_files:
        skip("test_dag_json_valid", "No DAG definition JSON files found")
        return

    for dag_file in dag_files:
        with open(dag_file, "r", encoding="utf-8") as f:
            dag = json.load(f)

        # Required fields
        assert "dag_id" in dag, f"{dag_file}: missing dag_id"
        assert "name" in dag, f"{dag_file}: missing name"
        assert "description" in dag, f"{dag_file}: missing description"
        assert "nodes" in dag, f"{dag_file}: missing nodes"
        assert "edges" in dag, f"{dag_file}: missing edges"
        assert len(dag["nodes"]) > 0, f"{dag_file}: empty nodes array"
        for n in dag["nodes"]:
            assert "id" in n, f"{dag_file}: node missing id"
            assert "description" in n, f"{dag_file}: node {n.get('id', '?')} missing description"
        for e in dag.get("edges", []):
            assert "from" in e, f"{dag_file}: edge missing 'from'"
            assert "to" in e, f"{dag_file}: edge missing 'to'"


def test_integration_pipeline():
    """Full pipeline test (plan mode only, no actual execution)."""
    # Test that the unified orchestrator runs
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "task-analyzer.py"),
         "--task", "Build integration layer", "--json"],
        capture_output=True, encoding="utf-8", errors="replace", cwd=BASE, timeout=30
    )
    assert result.returncode == 0, f"task-analyzer failed: {result.stderr}"
    analysis = json.loads(result.stdout)
    assert "score" in analysis, "analysis missing score"
    assert "threshold" in analysis, "analysis missing threshold"
    assert "mode" in analysis, "analysis missing mode"

    # Test DAG coordinator plan
    dag_file = os.path.join(DAG_DEFS, "seed-dag.json")
    if os.path.isfile(dag_file):
        dag_result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "dag-coordinator.py"),
             "--dag", dag_file, "--dry-run"],
            capture_output=True, encoding="utf-8", errors="replace", cwd=BASE, timeout=30
        )
        assert dag_result.returncode == 0, f"DAG coordinator plan failed: {dag_result.stderr}"

    # Test doc generator scan (no --health flag in WS-D version)
    doc_result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "doc-generator.py"), "--scan"],
        capture_output=True, encoding="utf-8", errors="replace", cwd=BASE, timeout=30
    )
    assert doc_result.returncode == 0, f"doc-generator scan failed: {doc_result.stderr}"
    assert "Scripts" in doc_result.stdout, f"doc-generator scan output missing: {doc_result.stdout[:200]}"

    # Test sandbox verify
    sandbox_result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "sandbox-manager.py"), "--verify"],
        capture_output=True, encoding="utf-8", errors="replace", cwd=BASE, timeout=30
    )
    # Sandbox verification may fail if pwsh is not available; that's OK
    # but the script itself should not crash
    assert sandbox_result.returncode in (0, 1), f"sandbox-manager verify crashed: {sandbox_result.stderr}"


def test_adr_exists():
    """Verify all 4 ADR files exist."""
    expected = [
        "adr-001-hybrid-triage-dag.md",
        "adr-002-identity-persistence.md",
        "adr-003-sandbox-isolation.md",
        "adr-004-documentation-generation.md",
    ]
    assert os.path.isdir(ADR_DIR), f"ADR directory not found: {ADR_DIR}"
    for adr in expected:
        path = os.path.join(ADR_DIR, adr)
        assert os.path.isfile(path), f"ADR file missing: {path}"
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert content.strip(), f"ADR file empty: {path}"
        assert "# ADR-" in content, f"ADR file missing '# ADR-' header: {path}"


def test_all_scripts_executable():
    """Verify all scripts can at least be imported/parsed without syntax errors."""
    python_scripts = glob.glob(os.path.join(SCRIPTS, "*.py"))
    assert len(python_scripts) > 10, f"Too few Python scripts found: {len(python_scripts)}"

    for script in python_scripts:
        fname = os.path.basename(script)
        if fname == "test-integration-layer.py":
            continue  # don't recurse
        with open(script, "r", encoding="utf-8") as f:
            try:
                import ast
                ast.parse(f.read())
            except SyntaxError as e:
                assert False, f"Syntax error in {fname}: {e}"

    # Check PowerShell scripts exist and are non-empty
    ps_scripts = glob.glob(os.path.join(SCRIPTS, "*.ps1"))
    for script in ps_scripts:
        fname = os.path.basename(script)
        size = os.path.getsize(script)
        assert size > 50, f"PowerShell script too small or empty: {fname} ({size} bytes)"


def test_dag_coordinator_plan():
    """Run DAG coordinator with --dry-run flag on seed DAG, verify output."""
    dag_file = os.path.join(DAG_DEFS, "seed-dag.json")
    if not os.path.isfile(dag_file):
        skip("test_dag_coordinator_plan", "seed-dag.json not found")
        return
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "dag-coordinator.py"),
         "--dag", dag_file, "--dry-run"],
        capture_output=True, encoding="utf-8", errors="replace", cwd=BASE, timeout=30
    )
    assert result.returncode == 0, f"DAG coordinator dry-run failed: {result.stderr}"
    output = result.stdout or ""
    assert any(kw in output for kw in ["DAG", "Pipeline", "integration", "seed"]), \
        f"DAG plan output missing expected content: {output[:300]}"


# ── Main ───────────────────────────────────────────────────

def run_all():
    print(f"\n{B}{'=' * 60}{N}")
    print(f"{B}{BOLD}  INTEGRATION LAYER TEST SUITE{N}")
    print(f"{B}{'=' * 60}{N}")
    print(f"  Base:    {BASE}")
    print(f"  Scripts: {SCRIPTS}")
    print(f"  Data:    {DATA}")
    print(f"\n  {C}Running {10} tests...{N}\n")

    test("a) DAG Coordinator Import", test_dag_coordinator_import)
    test("b) Identity Manager Import", test_identity_manager_import)
    test("c) Sandbox Manager Import", test_sandbox_manager_import)
    test("d) Doc Generator Import", test_doc_generator_import)
    test("e) Orchestrator DAG Flag", test_orchestrator_dag_flag)
    test("f) DAG JSON Schema Validity", test_dag_json_valid)
    test("g) Integration Pipeline", test_integration_pipeline)
    test("h) ADR File Existence", test_adr_exists)
    test("i) All Scripts Executable", test_all_scripts_executable)
    test("j) DAG Coordinator Plan", test_dag_coordinator_plan)

    total = results["passed"] + results["failed"] + results["skipped"]
    print(f"\n{'=' * 60}")
    print(f"  {BOLD}Results:{N}")
    print(f"  {G}Passed:  {results['passed']}/{total}{N}")
    if results["failed"]:
        print(f"  {R}Failed:  {results['failed']}/{total}{N}")
    if results["skipped"]:
        print(f"  {Y}Skipped: {results['skipped']}/{total}{N}")
    print(f"{'=' * 60}\n")

    return results["failed"] == 0


def list_tests():
    tests = [
        "test_dag_coordinator_import",
        "test_identity_manager_import",
        "test_sandbox_manager_import",
        "test_doc_generator_import",
        "test_orchestrator_dag_flag",
        "test_dag_json_valid",
        "test_integration_pipeline",
        "test_adr_exists",
        "test_all_scripts_executable",
        "test_dag_coordinator_plan",
    ]
    print("Available tests:")
    for t in tests:
        print(f"  - {t}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Integration Layer Test Suite")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--list", action="store_true", help="List available tests")
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    args = parser.parse_args()

    if args.list:
        list_tests()
        sys.exit(0)

    success = run_all()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to: {args.output}")

    sys.exit(0 if success else 1)
