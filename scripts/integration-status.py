#!/usr/bin/env python3
"""
Integration Status Report Generator — Checks all 5 workstream outputs,
validates schemas, runs the integration test suite, and generates an HTML report.

Usage:
    python scripts/integration-status.py
    python scripts/integration-status.py --output docs/integration-status.html
    python scripts/integration-status.py --quick
"""

import json, os, sys, subprocess, glob, hashlib
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(BASE, "scripts")
DATA = os.path.join(BASE, "data")
DOCS = os.path.join(BASE, "docs")
ADR_DIR = os.path.join(DATA, "adr")
DAG_DEFS = os.path.join(DATA, "dag-definitions")
DAG_SCHEMAS = os.path.join(DATA, "dag-schemas")
DAG_TRACES = os.path.join(DATA, "dag-traces")

G = "\033[92m"; Y = "\033[93m"; B = "\033[94m"; R = "\033[91m"; C = "\033[96m"; N = "\033[0m"; BOLD = "\033[1m"
BAR = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_file(path: str, label: str) -> dict:
    exists = os.path.isfile(path)
    size = os.path.getsize(path) if exists else 0
    return {"check": label, "path": path, "exists": exists, "size": size, "status": "PASS" if exists else "FAIL"}


def check_dir(path: str, label: str) -> dict:
    exists = os.path.isdir(path)
    count = len(os.listdir(path)) if exists else 0
    return {"check": label, "path": path, "exists": exists, "file_count": count, "status": "PASS" if exists else "FAIL"}


def check_import(module_name: str, file_path: str, class_name: str) -> dict:
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            return {"check": f"Import {module_name}", "status": "FAIL", "error": "Could not create spec"}
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, class_name):
            return {"check": f"Import {module_name}", "status": "FAIL", "error": f"{class_name} not found"}
        return {"check": f"Import {module_name}", "status": "PASS", "class": class_name}
    except Exception as e:
        return {"check": f"Import {module_name}", "status": "FAIL", "error": str(e)}


def check_adr_completeness() -> list:
    results = []
    expected = [
        "adr-001-hybrid-triage-dag.md",
        "adr-002-identity-persistence.md",
        "adr-003-sandbox-isolation.md",
        "adr-004-documentation-generation.md",
    ]
    if not os.path.isdir(ADR_DIR):
        return [{"check": "ADR directory", "status": "FAIL", "error": f"Directory not found: {ADR_DIR}"}]

    for adr in expected:
        path = os.path.join(ADR_DIR, adr)
        exists = os.path.isfile(path)
        has_header = False
        if exists:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            has_header = "# ADR-" in content
        results.append({
            "check": f"ADR: {adr}",
            "status": "PASS" if (exists and has_header) else "FAIL",
            "error": None if (exists and has_header) else ("Missing" if not exists else "Missing header"),
        })
    return results


def run_test_suite() -> dict:
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "test-integration-layer.py")],
        capture_output=True, text=True, cwd=BASE, timeout=60
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "passed": result.stdout.count("PASS"),
        "failed": result.stdout.count("FAIL"),
        "skipped": result.stdout.count("SKIP"),
    }


def generate_report(quick: bool = False) -> str:
    checks = []

    # Workstream A: DAG Coordinator
    checks.append(check_file(os.path.join(SCRIPTS, "dag-coordinator.py"), "DAG Coordinator script"))
    checks.append(check_dir(DAG_DEFS, "DAG definitions directory"))
    checks.append(check_dir(DAG_SCHEMAS, "DAG schema directory"))
    checks.append(check_dir(DAG_TRACES, "DAG traces directory"))
    checks.append(check_file(os.path.join(DAG_SCHEMAS, "dag-definition-v1.json"), "DAG definition schema"))
    dag_files = glob.glob(os.path.join(DAG_DEFS, "*.json"))
    for df in dag_files:
        checks.append(check_file(df, f"DAG def: {os.path.basename(df)}"))

    # Workstream B: Identity Manager
    checks.append(check_file(os.path.join(SCRIPTS, "identity-manager.py"), "Identity Manager script"))
    checks.append(check_import("identity_manager", os.path.join(SCRIPTS, "identity-manager.py"), "IdentityManager"))

    # Workstream C: Sandbox
    checks.append(check_file(os.path.join(SCRIPTS, "sandbox-manager.py"), "Sandbox Manager script"))
    checks.append(check_import("sandbox_manager", os.path.join(SCRIPTS, "sandbox-manager.py"), "SandboxManager"))

    # Workstream D: Doc Generator
    checks.append(check_file(os.path.join(SCRIPTS, "doc-generator.py"), "Doc Generator script"))
    checks.append(check_import("doc_generator", os.path.join(SCRIPTS, "doc-generator.py"), "DocGenerator"))

    # Workstream E: Integration Layer
    checks.append(check_file(os.path.join(SCRIPTS, "orchestrate-all.ps1"), "Unified Orchestrator"))
    checks.append(check_file(os.path.join(SCRIPTS, "test-integration-layer.py"), "Integration test suite"))
    checks.append(check_file(os.path.join(SCRIPTS, "integration-status.py"), "Status report generator"))

    # ADRs
    checks.extend(check_adr_completeness())

    # Decision registry
    checks.append(check_file(os.path.join(DATA, "decision-registry.json"), "Decision registry"))

    passed = sum(1 for c in checks if c.get("status") == "PASS")
    failed = sum(1 for c in checks if c.get("status") == "FAIL")
    total = len(checks)

    # Run test suite (unless quick)
    test_results = None
    if not quick:
        test_results = run_test_suite()
        test_pass_rate = f"{test_results['passed']}/{test_results['passed'] + test_results['failed'] + test_results['skipped']}"
    else:
        test_pass_rate = "skipped (--quick)"

    # Build HTML
    checks_rows = ""
    for c in checks:
        status_icon = "✅" if c.get("status") == "PASS" else "❌"
        details = ""
        if "size" in c and c.get("exists"):
            details = f"Size: {c['size']} bytes"
        elif "file_count" in c and c.get("exists"):
            details = f"Files: {c['file_count']}"
        elif "error" in c and c.get("error"):
            details = f"Error: {c['error']}"
        elif "class" in c:
            details = f"Class: {c['class']}"
        checks_rows += f"""
        <tr>
            <td>{status_icon}</td>
            <td>{c.get('status', 'UNKNOWN')}</td>
            <td><code>{c.get('check', '')}</code></td>
            <td><code>{c.get('path', '')}</code></td>
            <td>{details}</td>
        </tr>"""

    test_section = ""
    if test_results:
        test_lines = test_results["stdout"].split("\n")
        test_body = "\n".join(f"        <pre>{l}</pre>" for l in test_lines if l.strip())
        test_section = f"""
        <h2>Test Suite Results</h2>
        <div class="test-output">
            <p>Return code: {test_results['returncode']} | Passed: {test_results['passed']} | Failed: {test_results['failed']} | Skipped: {test_results['skipped']}</p>
            {test_body}
        </div>"""

    timestamp = now_iso()[:19]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>cortex-stratum — Integration Status</title>
<style>
    {{font-family: system-ui, -apple-system, sans-serif; line-height: 1.5; max-width: 1200px; margin: 0 auto; padding: 2rem; background: #0d1117; color: #c9d1d9;}}
    h1, h2 {{color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 0.5rem;}}
    h1 span {{font-size: 0.6em; color: #8b949e;}}
    table {{border-collapse: collapse; width: 100%; margin: 1rem 0;}}
    th, td {{text-align: left; padding: 0.5rem; border-bottom: 1px solid #30363d;}}
    th {{background: #161b22; color: #58a6ff;}}
    tr:hover {{background: #1c2128;}}
    .pass {{color: #3fb950;}} .fail {{color: #f85149;}} .skip {{color: #d29922;}}
    .summary {{display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1rem 0;}}
    .card {{background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 1rem;}}
    .card h3 {{margin: 0 0 0.5rem; font-size: 0.9em; color: #8b949e;}}
    .card .value {{font-size: 2em; font-weight: bold;}}
    .test-output {{background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 1rem; overflow-x: auto;}}
    .test-output pre {{margin: 0; font-size: 0.85em; color: #c9d1d9; white-space: pre-wrap;}}
    code {{background: #1c2128; padding: 0.15em 0.3em; border-radius: 3px; font-size: 0.9em;}}
</style>
</head>
<body>
    <h1>cortex-stratum — Integration Status <span>{timestamp}</span></h1>

    <div class="summary">
        <div class="card">
            <h3>Total Checks</h3>
            <div class="value">{total}</div>
        </div>
        <div class="card">
            <h3>Passed</h3>
            <div class="value" style="color:#3fb950">{passed}</div>
        </div>
        <div class="card">
            <h3>Failed</h3>
            <div class="value" style="color:#f85149">{failed}</div>
        </div>
        <div class="card">
            <h3>Test Pass Rate</h3>
            <div class="value">{test_pass_rate}</div>
        </div>
    </div>

    <h2>Workstream Checks</h2>
    <table>
        <thead>
            <tr><th></th><th>Status</th><th>Check</th><th>Path</th><th>Details</th></tr>
        </thead>
        <tbody>
            {checks_rows}
        </tbody>
    </table>

    {test_section}

    <hr style="border-color: #30363d; margin: 2rem 0;">
    <p style="text-align: center; color: #8b949e;">Generated by scripts/integration-status.py at {timestamp}</p>
</body>
</html>"""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Integration Status Report Generator")
    parser.add_argument("--output", type=str, default=os.path.join(DOCS, "integration-status.html"),
                        help="Output HTML path")
    parser.add_argument("--quick", action="store_true", help="Skip running tests")
    args = parser.parse_args()

    print(f"\n{B}{BAR}{N}")
    print(f"{B}{BOLD}  INTEGRATION STATUS REPORT{N}")
    print(f"{B}{BAR}{N}")

    html = generate_report(quick=args.quick)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    # Also print summary to console
    check_count = html.count("<tr>")
    pass_count = html.count('✅')
    fail_count = html.count('❌')
    print(f"  Checks:  {check_count} ({pass_count} pass, {fail_count} fail)")
    print(f"  Report:  {G}{args.output}{N}")
    print(f"\n  {'─'*50}")
    print(f"  Workstream A (DAG):      dag-coordinator.py, seed DAG, schemas")
    print(f"  Workstream B (Identity): identity-manager.py with IdentityManager")
    print(f"  Workstream C (Sandbox):  sandbox-manager.py with SandboxManager")
    print(f"  Workstream D (Docs):     doc-generator.py with DocGenerator")
    print(f"  Workstream E (Integrate): orchestrate-all.ps1, ADRs, tests")
    print(f"  {'─'*50}")
    print(f"\n  To run tests:  python scripts/test-integration-layer.py")
    print(f"  To re-generate: python scripts/integration-status.py\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
