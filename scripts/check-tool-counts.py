#!/usr/bin/env python3
"""
CortexStratum Tool Count Auditor

Single source of truth for tool count verification.
Run after ANY change to the TOOLS list in tools-mcp-server.py.

Usage:
    python scripts/check-tool-counts.py              # Audit only (exit 1 on mismatch)
    python scripts/check-tool-counts.py --fix         # Auto-fix stale references
    python scripts/check-tool-counts.py --list-only   # Just print real count
    python scripts/check-tool-counts.py --ci          # CI mode: quiet, exit code only

Exit codes:
    0: All counts match / fixed successfully
    1: Mismatch(es) found (and --fix was not passed)
    2: Script error
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files to exclude from scanning
EXCLUDE_DIRS = {".git", ".build-venv", "__pycache__", "node_modules", ".memory", "archive"}
EXCLUDE_PATTERNS = [re.compile(r"\.git/"), re.compile(r"\.build-venv/")]

# ============================================================
# 1. Get the ACTUAL tool count from the TOOLS list
# ============================================================

def get_real_tool_count() -> int:
    """Get the actual tool count by running the server with --list-tools."""
    server_path = REPO_ROOT / "scripts" / "tools-mcp-server.py"
    if not server_path.exists():
        print(f"ERROR: {server_path} not found", file=sys.stderr)
        sys.exit(2)

    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, str(server_path), "--list-tools"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print(f"ERROR: server exited {result.returncode}: {result.stderr}", file=sys.stderr)
            sys.exit(2)
        tools = json.loads(result.stdout)
        return len(tools)
    except Exception as e:
        print(f"ERROR: could not count tools: {e}", file=sys.stderr)
        sys.exit(2)


# Known stale references mapped to current count
# Format: (pattern_to_search, replacement)
# Each pattern is checked against file content and replaced if --fix
def get_stale_patterns(real_count: int) -> list[dict]:
    """Return known stale count patterns that appear in docs/strings."""
    # These are the canonical stale number references we've seen drift to
    stale_numbers = {
        68: "pre-v0.5 count",
        69: "pre-v0.5 count (cortexstratum-dev skill)",
        77: "old skill-router count",
        79: "old 'all annotated' comment count",
        82: "old OpenCode config count",
        122: "pre-sim-engine count",
        133: "old total (read_ count only)",
        134: "old tool-inventory snapshot",
        135: "old total",
        159: "inflated count (handoff hallucination)",
        161: "pre-WM count",
        166: "pre-compute-alloc count",
        169: "pre-limbic count",
        173: "pre-reinforcement count",
        175: "pre-compute-exec count",
        178: "pre-dmn+vq count",
    }

    patterns = []

    for num, label in stale_numbers.items():
        if num == real_count:
            continue  # Don't flag if it somehow matches
        patterns.append({
            "stale": num,
            "label": label,
            # Match patterns like "159-tool", "159 tools", "**159**", "159-tool MCP"
            "word_patterns": [
                re.compile(rf"\b{num}-tool\b"),
                re.compile(rf"\b{num} tools\b"),
                re.compile(rf"\b{num} Tools\b"),
                re.compile(rf"\*\*{num}\*\*"),
                re.compile(rf"Tools-{num}\b"),
                re.compile(rf"\b{num}-tool MCP server\b"),
            ],
        })

    return patterns


# ============================================================
# 2. Scan project files for stale references
# ============================================================

SKIP_EXACT_FILES = {
    "scripts/check-tool-counts.py",  # This file itself
    "scripts/utils.py",
    ".gitattributes",
}

# Historical files that should keep original tool counts for context
# (e.g. changelog entries, benchmark data, audit docs quoting old counts)
HISTORICAL_FILES = {
    "CHANGELOG.md",
    "data/session-overview.json",
    "data/terminal-bench-results.json",
    "docs/memory-bloat-audit.md",
    "docs/issue-backlog.md",
}

def should_scan(path: Path) -> bool:
    """Check if a file should be scanned for stale tool counts."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    if rel in SKIP_EXACT_FILES:
        return False
    if rel in HISTORICAL_FILES:
        return False  # Preserve historical records
    for excl in EXCLUDE_DIRS:
        if f"/{excl}/" in rel or rel == excl or rel.startswith(f"{excl}/"):
            return False
    for pat in EXCLUDE_PATTERNS:
        if pat.search(rel):
            return False
    # Only scan text files likely to contain count references
    ext = path.suffix.lower()
    return ext in {".md", ".py", ".json", ".jsonc", ".yaml", ".yml", ".html", ".ps1", ".sh", ".txt", ".cfg", ".ini"}


# ============================================================
# 3. Fix stale references
# ============================================================

def fix_stale_in_file(path: Path, old_num: int, new_num: int, dry_run: bool) -> list[str]:
    """Replace stale count references in a file. Returns list of changes made."""
    changes = []
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return changes

    original = content

    # Replace whole-word occurrences of the stale number in tool-count contexts
    # Pattern: "N-tool" or "N tools" or "**N**" or "Tools-N" or "N-tool MCP"
    patterns = [
        (re.compile(rf"\b{old_num}-tool\b"), f"{new_num}-tool"),
        (re.compile(rf"\b{old_num} tools\b"), f"{new_num} tools"),
        (re.compile(rf"\b{old_num} Tools\b"), f"{new_num} Tools"),
        (re.compile(rf"\*\*{old_num}\*\*"), f"**{new_num}**"),
        (re.compile(rf"Tools-{old_num}\b"), f"Tools-{new_num}"),
    ]

    for pattern, replacement in patterns:
        new_content, count = pattern.subn(replacement, content)
        if count > 0:
            rel = path.relative_to(REPO_ROOT).as_posix()
            changes.append(f"  {rel}: replaced {old_num}→{new_num} ({count}x) — {pattern.pattern}")
            content = new_content

    if content != original and not dry_run:
        path.write_text(content, encoding="utf-8")

    return changes


def fix_stale_number(content: str, old_num: int, new_num: int) -> str:
    """Replace stale count references in a content string."""
    patterns = [
        (re.compile(rf"\b{old_num}-tool\b"), f"{new_num}-tool"),
        (re.compile(rf"\b{old_num} tools\b"), f"{new_num} tools"),
        (re.compile(rf"\b{old_num} Tools\b"), f"{new_num} Tools"),
        (re.compile(rf"\*\*{old_num}\*\*"), f"**{new_num}**"),
        (re.compile(rf"Tools-{old_num}\b"), f"Tools-{new_num}"),
    ]
    for pattern, replacement in patterns:
        content = pattern.sub(replacement, content)
    return content


def scan_file_for_stale(path: Path, real_count: int, known_stale: list[int]) -> list[dict]:
    """Scan a single file for stale tool count references."""
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return []

    findings = []
    for line_no, line in enumerate(content.splitlines(), 1):
        for stale_num in known_stale:
            if stale_num == real_count:
                continue
            # Check for tool-count patterns
            if re.search(rf"\b{stale_num}-tool\b", line) and "badge" not in line:
                pass  # Found it
            elif re.search(rf"\b{stale_num} tools\b", line, re.IGNORECASE):
                pass
            elif re.search(rf"\*\*{stale_num}\*\*", line):
                pass
            elif re.search(rf"\b{stale_num}-tool MCP", line):
                pass
            else:
                continue

            rel = path.relative_to(REPO_ROOT).as_posix()
            findings.append({
                "file": rel,
                "line": line_no,
                "stale": stale_num,
                "content": line.strip(),
            })
    return findings


# ============================================================
# 4. Rebuild tool-inventory.json
# ============================================================

def rebuild_tool_inventory(real_count: int) -> list[str]:
    """Rebuild data/tool-inventory.json by running the server with --list-tools."""
    server_path = REPO_ROOT / "scripts" / "tools-mcp-server.py"
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, str(server_path), "--list-tools"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return [f"  ERROR: server exited {result.returncode}: {result.stderr}"]
        tools = json.loads(result.stdout)

        inventory_path = REPO_ROOT / "data" / "tool-inventory.json"
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(
            json.dumps(tools, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return [f"  data/tool-inventory.json: {len(tools)} tools written"]
    except Exception as e:
        return [f"  ERROR rebuilding tool-inventory.json: {e}"]


# ============================================================
# 5. Main
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="CortexStratum Tool Count Auditor")
    parser.add_argument("--fix", action="store_true", help="Auto-fix stale references")
    parser.add_argument("--list-only", action="store_true", help="Just print real tool count and exit")
    parser.add_argument("--ci", action="store_true", help="CI mode: minimal output, exit code only")
    args = parser.parse_args()

    # Get real count
    real_count = get_real_tool_count()

    if args.list_only:
        print(real_count)
        return

    # Known stale numbers that have appeared in docs
    known_stale = [68, 69, 77, 79, 82, 122, 133, 134, 135, 158, 159, 161, 166, 169, 173, 175, 178]
    known_stale = [n for n in known_stale if n != real_count]

    if not args.ci:
        print("\n🔍 CortexStratum Tool Count Auditor")
        print(f"{'='*45}")
        print(f"  Real tool count:  {real_count}")
        print(f"  Scanning for stale: {known_stale}")
        print()

    # Scan all project files
    findings = []
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file() or not should_scan(path):
            continue
        findings.extend(scan_file_for_stale(path, real_count, known_stale))

    if findings:
        if not args.ci:
            print(f"  Found {len(findings)} stale reference(s):\n")
            for f in findings:
                print(f"  ❌ {f['file']}:{f['line']} — stale count {f['stale']}")
                print(f"     {f['content'][:100]}")
            print()
    else:
        if not args.ci:
            print("  ✅ No stale references found.\n")

    # Auto-fix mode
    fix_results = []
    if args.fix:
        if not args.ci:
            print("  🔧 Fix mode enabled\n")

        # Fix files with stale references
        fixed_files = set()
        for f in findings:
            path = REPO_ROOT / f["file"]
            if path in fixed_files:
                continue
            fixed_files.add(path)

            changes = fix_stale_in_file(path, f["stale"], real_count, dry_run=False)
            fix_results.extend(changes)

        # Also fix data/tool-inventory.json by rebuilding it
        if not args.ci:
            print("  🔧 Rebuilding data/tool-inventory.json from TOOLS list...")
        rebuild_results = rebuild_tool_inventory(real_count)
        fix_results.extend(rebuild_results)

        if fix_results:
            if not args.ci:
                print("  Changes made:\n")
                for r in fix_results:
                    print(f"  {r}")
                print()
        else:
            if not args.ci:
                print("  No changes needed.\n")

    # Exit code
    if findings and not args.fix:
        if not args.ci:
            print("  ❌ Run with --fix to auto-correct, or fix manually.")
        sys.exit(1)
    elif findings and args.fix:
        if not args.ci:
            print(f"  ✅ Fixed {len(findings)} stale reference(s).")
    else:
        if not args.ci:
            print("  ✅ All tool counts match. Good to go!")

    if not args.ci:
        print()


if __name__ == "__main__":
    main()
