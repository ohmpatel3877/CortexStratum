#!/usr/bin/env python3
"""
Utility Module — Database, format conversion, and regex tools.
Zero external dependencies (stdlib only).
"""

import csv
import io
import json
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# ── Database Tools ──────────────────────────────────────────────────────


def _db_query(db_path: str, sql: str) -> dict:
    """Execute a SQL SELECT query and return results."""
    if not os.path.isfile(db_path):
        return {"error": f"Database not found: {db_path}"}
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT") and not sql_upper.startswith("PRAGMA"):
        return {"error": "Only SELECT and PRAGMA queries are allowed via read_db_query"}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql)
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        return {"rows": rows, "count": len(rows)}
    except Exception as e:
        return {"error": str(e)}


def _db_schema(db_path: str) -> dict:
    """List tables and their columns in a SQLite database."""
    if not os.path.isfile(db_path):
        return {"error": f"Database not found: {db_path}"}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = []
        for row in cur.fetchall():
            tname = row[0]
            cols = conn.execute(f"PRAGMA table_info('{tname}')").fetchall()
            columns = [
                {
                    "cid": c[0],
                    "name": c[1],
                    "type": c[2],
                    "notnull": bool(c[3]),
                    "pk": bool(c[5]),
                }
                for c in cols
            ]
            tables.append({"name": tname, "columns": columns})
        conn.close()
        return {"tables": tables, "count": len(tables)}
    except Exception as e:
        return {"error": str(e)}


def _db_execute(db_path: str, sql: str, dry_run: bool = False) -> dict:
    """Execute INSERT/UPDATE/DELETE with dry-run support."""
    if not os.path.isfile(db_path):
        return {"error": f"Database not found: {db_path}"}
    sql_upper = sql.strip().upper()
    if sql_upper.startswith("SELECT") or sql_upper.startswith("PRAGMA"):
        return {"error": "Use read_db_query for SELECT queries"}
    try:
        conn = sqlite3.connect(db_path)
        if dry_run:
            conn.execute("BEGIN")
            cur = conn.execute(sql)
            affected = conn.total_changes
            conn.execute("ROLLBACK")
            return {"dry_run": True, "rows_affected": affected, "sql": sql[:200]}
        cur = conn.execute(sql)
        conn.commit()
        affected = cur.rowcount
        conn.close()
        return {"rows_affected": affected, "sql": sql[:200]}
    except Exception as e:
        return {"error": str(e)}


# ── Conversion Tools ────────────────────────────────────────────────────


def _convert_csv_to_json(
    csv_text: str, dialect: str = "excel", has_header: bool = True
) -> dict:
    """Convert CSV text to JSON."""
    try:
        if has_header:
            reader = csv.DictReader(io.StringIO(csv_text))
            rows = list(reader)
        else:
            reader = csv.reader(io.StringIO(csv_text))
            rows = [row for row in reader]
        return {"data": rows, "count": len(rows), "format": "json"}
    except Exception as e:
        return {"error": str(e)}


def _convert_json_to_csv(json_text: str) -> dict:
    """Convert JSON array to CSV text."""
    try:
        data = json.loads(json_text)
        if not isinstance(data, list) or not data:
            return {"error": "JSON must be a non-empty array of objects"}
        if not isinstance(data[0], dict):
            return {"csv": "\n".join(str(v) for v in data), "format": "csv"}
        fieldnames = list(data[0].keys())
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
        return {"csv": output.getvalue(), "count": len(data), "format": "csv"}
    except Exception as e:
        return {"error": str(e)}


def _convert_json_to_xml(
    json_text: str, root_name: str = "root", item_name: str = "item"
) -> dict:
    """Convert JSON to XML string."""
    try:
        data = json.loads(json_text)

        def _build(parent, value):
            if isinstance(value, dict):
                for k, v in value.items():
                    child = ET.SubElement(parent, k.replace(" ", "_"))
                    _build(child, v)
            elif isinstance(value, list):
                for v in value:
                    child = ET.SubElement(parent, item_name)
                    _build(child, v)
            else:
                parent.text = str(value)

        root = ET.Element(root_name)
        _build(root, data)
        return {"xml": ET.tostring(root, encoding="unicode"), "format": "xml"}
    except Exception as e:
        return {"error": str(e)}


def _convert_xml_to_json(xml_text: str) -> dict:
    """Convert XML string to JSON."""
    try:
        root = ET.fromstring(xml_text)

        def _parse(element):
            result = {}
            for child in element:
                child_data = _parse(child)
                if child.tag in result:
                    if not isinstance(result[child.tag], list):
                        result[child.tag] = [result[child.tag]]
                    result[child.tag].append(child_data)
                else:
                    result[child.tag] = child_data
            if element.text and element.text.strip():
                if not result:
                    return element.text.strip()
                result["#text"] = element.text.strip()
            return result

        data = {root.tag: _parse(root)}
        return {"data": data, "format": "json"}
    except Exception as e:
        return {"error": str(e)}


def _has_yaml() -> bool:
    try:
        import yaml  # noqa: F401

        return True
    except ImportError:
        return False


def _convert_json_to_yaml(json_text: str) -> dict:
    """Convert JSON to YAML (requires PyYAML)."""
    if not _has_yaml():
        return {"error": "PyYAML not installed. Run: pip install pyyaml"}
    import yaml

    try:
        data = json.loads(json_text)
        yaml_str = yaml.dump(data, default_flow_style=False)
        return {"yaml": yaml_str, "format": "yaml"}
    except Exception as e:
        return {"error": str(e)}


def _convert_yaml_to_json(yaml_text: str) -> dict:
    """Convert YAML to JSON (requires PyYAML)."""
    if not _has_yaml():
        return {"error": "PyYAML not installed. Run: pip install pyyaml"}
    import yaml

    try:
        data = yaml.safe_load(yaml_text)
        return {"data": data, "format": "json"}
    except Exception as e:
        return {"error": str(e)}


# ── Regex Tools ─────────────────────────────────────────────────────────


def _regex_test(pattern: str, text: str, flags: str = "") -> dict:
    """Test a regex pattern against text and return matches."""
    try:
        flag_mask = 0
        if "i" in flags:
            flag_mask |= re.IGNORECASE
        if "m" in flags:
            flag_mask |= re.MULTILINE
        if "s" in flags:
            flag_mask |= re.DOTALL
        if "x" in flags:
            flag_mask |= re.VERBOSE
        compiled = re.compile(pattern, flag_mask)
        matches = []
        for m in compiled.finditer(text):
            matches.append(
                {
                    "start": m.start(),
                    "end": m.end(),
                    "match": m.group(),
                    "groups": list(m.groups()) if m.groups() else None,
                }
            )
        return {
            "pattern": pattern,
            "flags": flags or "none",
            "matches": matches,
            "count": len(matches),
            "matched": len(matches) > 0,
        }
    except re.error as e:
        return {"error": f"Invalid regex: {e}"}


def _regex_explain(pattern: str) -> dict:
    """Explain what a regex pattern does."""
    try:
        re.compile(pattern)  # validate
        parts = []
        i = 0
        while i < len(pattern):
            if pattern[i] == "\\" and i + 1 < len(pattern):
                nxt = pattern[i + 1]
                mapping = {
                    "d": "digit [0-9]",
                    "w": "word char [a-zA-Z0-9_]",
                    "s": "whitespace",
                    "b": "word boundary",
                    "D": "non-digit",
                    "W": "non-word char",
                    "S": "non-whitespace",
                    "B": "non-word boundary",
                    "t": "tab",
                    "n": "newline",
                    "r": "carriage return",
                }
                parts.append(mapping.get(nxt, f"literal '{nxt}'"))
                i += 2
            elif pattern[i] == "^":
                parts.append("start of string")
                i += 1
            elif pattern[i] == "$":
                parts.append("end of string")
                i += 1
            elif pattern[i] == ".":
                parts.append("any char (except newline)")
                i += 1
            elif pattern[i] == "*":
                parts.append("zero or more")
                i += 1
            elif pattern[i] == "+":
                parts.append("one or more")
                i += 1
            elif pattern[i] == "?":
                parts.append("optional (zero or one)")
                i += 1
            elif pattern[i] == "|":
                parts.append("OR")
                i += 1
            elif pattern[i] == "(":
                parts.append("group start")
                i += 1
            elif pattern[i] == ")":
                parts.append("group end")
                i += 1
            elif pattern[i] == "[":
                j = i + 1
                while j < len(pattern) and pattern[j] != "]":
                    j += 1
                class_content = (
                    pattern[i + 1 : j] if j < len(pattern) else pattern[i + 1 :]
                )
                parts.append(f"char class [{class_content}]")
                i = j + 1 if j < len(pattern) else j
            elif pattern[i] == "{":
                j = i + 1
                while j < len(pattern) and pattern[j] != "}":
                    j += 1
                quant = pattern[i + 1 : j] if j < len(pattern) else ""
                parts.append(f"  {{{quant}}}")
                i = j + 1
            else:
                parts.append(f"literal '{pattern[i]}'")
                i += 1
        return {
            "pattern": pattern,
            "explanation": " → ".join(parts),
            "parts": parts,
            "valid": True,
        }
    except re.error as e:
        return {"error": f"Invalid regex: {e}"}


# ── Verification Gate ────────────────────────────────────────────────────


def _run_verify_gate(steps: list | None = None) -> dict:
    """Run the full verification gate: lint, syntax, MCP test, skill pipeline, verifier.
    Optionally specify which steps to run (default: all)."""
    import sys

    SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
    results = {}
    all_passed = True

    step_registry = {
        "ruff": {
            "label": "Ruff linting",
            "cmd": ["ruff", "check", "."],
            "run": lambda: _run_step(["ruff", "check", "."]),
        },
        "syntax": {
            "label": "Python syntax check",
            "cmd": [sys.executable, "-m", "py_compile"],
            "run": lambda: _run_py_compile(SCRIPTS_DIR),
        },
        "mcp_test": {
            "label": "MCP protocol test",
            "cmd": [sys.executable, str(SCRIPTS_DIR / "test-mcp-server.py")],
            "run": lambda: _run_step(
                [sys.executable, str(SCRIPTS_DIR / "test-mcp-server.py")]
            ),
        },
        "skill_pipeline": {
            "label": "Skill pipeline integrity",
            "cmd": [sys.executable, str(SCRIPTS_DIR / "test-skill-pipeline.py")],
            "run": lambda: _run_step(
                [sys.executable, str(SCRIPTS_DIR / "test-skill-pipeline.py")]
            ),
        },
        "verifier": {
            "label": "Verifier middleware",
            "cmd": [sys.executable, str(SCRIPTS_DIR / "verifier_middleware.py")],
            "run": lambda: _run_step(
                [sys.executable, str(SCRIPTS_DIR / "verifier_middleware.py")]
            ),
        },
        "tool_count": {
            "label": "Tool count check",
            "cmd": [
                sys.executable,
                str(SCRIPTS_DIR / "tools-mcp-server.py"),
                "--list-tools",
            ],
            "run": lambda: _run_tool_count(SCRIPTS_DIR),
        },
    }

    if steps:
        selected = {k: v for k, v in step_registry.items() if k in steps}
    else:
        selected = step_registry

    for key, step in selected.items():
        try:
            result = step["run"]()
            results[key] = result
            if not result.get("passed", False):
                all_passed = False
        except Exception as e:
            results[key] = {"passed": False, "error": str(e)}
            all_passed = False

    return {
        "all_passed": all_passed,
        "steps": results,
        "total": len(results),
        "passed": sum(1 for r in results.values() if r.get("passed")),
        "failed": sum(1 for r in results.values() if not r.get("passed")),
    }


def _run_step(cmd: list) -> dict:
    import subprocess

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        stdout = r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout
        stderr = r.stderr[-1000:] if len(r.stderr) > 1000 else r.stderr
        return {
            "passed": r.returncode == 0,
            "returncode": r.returncode,
            "stdout_tail": stdout,
            "stderr_tail": stderr,
        }
    except subprocess.TimeoutExpired:
        return {"passed": False, "error": "Timed out after 120s"}
    except FileNotFoundError as e:
        return {"passed": False, "error": f"Command not found: {e}"}


def _run_py_compile(scripts_dir: Path) -> dict:
    import subprocess
    import sys

    py_files = list(scripts_dir.glob("*.py"))
    failed = []
    for f in py_files:
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", str(f)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            failed.append({"file": f.name, "error": r.stderr.strip()})
    return {
        "passed": len(failed) == 0,
        "files_checked": len(py_files),
        "failed_files": failed,
    }


def _run_tool_count(scripts_dir: Path) -> dict:
    import json
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, str(scripts_dir / "tools-mcp-server.py"), "--list-tools"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        tools = json.loads(r.stdout)
        count = len(tools)
        return {
            "passed": count >= 120,
            "tool_count": count,
            "tools": [t["name"] for t in tools],
        }
    except (json.JSONDecodeError, KeyError) as e:
        return {"passed": False, "error": f"Failed to parse tool list: {e}"}


# ── Dispatch ─────────────────────────────────────────────────────────────


def handle_tool_call(name: str, args: dict) -> Any:
    if name == "read_db_query":
        return _db_query(args.get("db_path", ""), args.get("sql", ""))
    elif name == "read_db_schema":
        return _db_schema(args.get("db_path", ""))
    elif name == "write_db_execute":
        return _db_execute(
            args.get("db_path", ""), args.get("sql", ""), args.get("dry_run", False)
        )
    elif name == "read_convert_csv_to_json":
        return _convert_csv_to_json(
            args.get("csv_text", ""),
            args.get("dialect", "excel"),
            args.get("has_header", True),
        )
    elif name == "read_convert_json_to_csv":
        return _convert_json_to_csv(args.get("json_text", ""))
    elif name == "read_convert_json_to_xml":
        return _convert_json_to_xml(
            args.get("json_text", ""),
            args.get("root_name", "root"),
            args.get("item_name", "item"),
        )
    elif name == "read_convert_xml_to_json":
        return _convert_xml_to_json(args.get("xml_text", ""))
    elif name == "read_convert_json_to_yaml":
        return _convert_json_to_yaml(args.get("json_text", ""))
    elif name == "read_convert_yaml_to_json":
        return _convert_yaml_to_json(args.get("yaml_text", ""))
    elif name == "read_regex_test":
        return _regex_test(
            args.get("pattern", ""), args.get("text", ""), args.get("flags", "")
        )
    elif name == "read_regex_explain":
        return _regex_explain(args.get("pattern", ""))
    elif name == "mutate_verify_run":
        return _run_verify_gate(args.get("steps", None))
    return {"error": f"Unknown utility tool: {name}"}
