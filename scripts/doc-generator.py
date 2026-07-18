#!/usr/bin/env python3
"""
Doc Generator — Automatic API documentation for CortexStratum.

Scans scripts/, tools-mcp-server.py, and data/ to produce
markdown, HTML, and JSON documentation artifacts.

Usage:
    python scripts/doc-generator.py --scan            Quick scan, print summary
    python scripts/doc-generator.py --generate-md     Generate markdown docs
    python scripts/doc-generator.py --generate-html   Generate HTML docs
    python scripts/doc-generator.py --generate-all    Generate everything
    python scripts/doc-generator.py --watch           Watch mode
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE = Path(__file__).resolve().parent
PROJECT_ROOT = BASE.parent
SCRIPTS_DIR = BASE
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"

G = "\033[92m"
Y = "\033[93m"
B = "\033[94m"
M = "\033[95m"
C = "\033[96m"
R = "\033[91m"
N = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


class DocGenerator:
    """Generates documentation from CortexStratum scripts and MCP tools."""

    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.scripts_dir = SCRIPTS_DIR
        self.data_dir = DATA_DIR
        self.docs_dir = DOCS_DIR
        self.scripts: List[Dict[str, Any]] = []
        self.mcp_tools: List[Dict[str, Any]] = []
        self.data_files: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def scan_scripts(self) -> List[Dict[str, Any]]:
        """Scan all .py and .ps1 files in scripts/, extract metadata."""
        results = []
        for fpath in sorted(self.scripts_dir.iterdir()):
            if fpath.suffix not in (".py", ".ps1"):
                continue
            if fpath.name == "doc-generator.py":
                continue
            raw = fpath.read_text(encoding="utf-8", errors="replace")
            entry: Dict[str, Any] = {
                "filename": fpath.name,
                "language": "python" if fpath.suffix == ".py" else "powershell",
                "docstring": self._extract_docstring(raw, fpath.suffix),
                "functions": [],
                "classes": [],
                "cli_args": [],
            }
            if fpath.suffix == ".py":
                entry["functions"] = self._extract_py_functions(raw)
                entry["classes"] = self._extract_py_classes(raw)
                entry["cli_args"] = self._extract_py_cli_args(raw)
            else:
                entry["functions"] = self._extract_ps_functions(raw)
                entry["classes"] = []
                entry["cli_args"] = self._extract_ps_params(raw)
            results.append(entry)
        self.scripts = results
        return results

    def _extract_docstring(self, raw: str, suffix: str) -> str:
        if suffix == ".py":
            m = re.search(r'^#!/usr/bin/env python3\s*"""(.+?)"""', raw, re.DOTALL)
            if m:
                return m.group(1).strip()
            m = re.search(r'^\s*"""(.+?)"""', raw, re.DOTALL)
            if m:
                return m.group(1).strip()
        else:
            m = re.search(r'<#(.+?)#>', raw, re.DOTALL)
            if m:
                block = m.group(1).strip()
                lines = [l.strip() for l in block.split("\n") if l.strip()]
                parts = []
                for l in lines:
                    if re.match(r'^\.(SYNOPSIS|DESCRIPTION|PARAMETER|EXAMPLE)\s', l, re.IGNORECASE):
                        parts.append("")
                    parts.append(l)
                return "\n".join(p.strip() for p in parts if p.strip())
        return ""

    def _extract_py_functions(self, raw: str) -> List[Dict[str, str]]:
        funcs = []
        for m in re.finditer(
            r'^def\s+(\w+)\s*\((.*?)\)\s*(->\s*(\w+(?:\[.*?\])?)\s*)?:',
            raw,
            re.MULTILINE,
        ):
            funcs.append({
                "name": m.group(1),
                "args": self._parse_args(m.group(2)),
                "return_type": (m.group(4) or "").strip(),
            })
        return funcs

    def _parse_args(self, args_str: str) -> List[Dict[str, str]]:
        if not args_str.strip():
            return []
        result = []
        depth = 0
        parts = []
        current = []
        for ch in args_str:
            if ch in "([{":
                depth += 1
                current.append(ch)
            elif ch in ")]}":
                depth -= 1
                current.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(ch)
        parts.append("".join(current).strip())
        for p in parts:
            if not p or p == "self" or p == "cls":
                continue
            p = re.sub(r':\s*(?:list|dict|str|int|float|bool|Any|Optional|List|Dict|Tuple|Set)\[.*?\]', '', p)
            p = re.sub(r':\s*\w+', '', p)
            p = p.split("=")[0].strip()
            if p and p not in ("self", "cls", "*", "**kwargs", "**args"):
                result.append({"name": p})
        return result

    def _extract_py_classes(self, raw: str) -> List[Dict[str, Any]]:
        classes = []
        for m in re.finditer(r'^class\s+(\w+)\s*(?:\(.*?\))?\s*:', raw, re.MULTILINE):
            classes.append({"name": m.group(1)})
        return classes

    def _extract_py_cli_args(self, raw: str) -> List[Dict[str, str]]:
        args = []
        for m in re.finditer(
            r"""add_argument\s*\(['"]([-]{1,2}\w[\w-]*)['"]""", raw
        ):
            args.append({"flag": m.group(1)})
        return args

    def _extract_ps_functions(self, raw: str) -> List[Dict[str, str]]:
        funcs = []
        for m in re.finditer(
            r'^function\s+(\w[\w-]*)\s*{', raw, re.MULTILINE
        ):
            funcs.append({"name": m.group(1), "args": [], "return_type": ""})
        return funcs

    def _extract_ps_params(self, raw: str) -> List[Dict[str, str]]:
        params = []
        for m in re.finditer(r'^\s*\[string\]\$(\w+)', raw, re.MULTILINE):
            params.append({"flag": f"-{m.group(1)}", "type": "string"})
        for m in re.finditer(r'^\s*\[string\[\]\]\$(\w+)', raw, re.MULTILINE):
            params.append({"flag": f"-{m.group(1)}", "type": "string[]"})
        return params

    def scan_mcp_tools(self) -> List[Dict[str, Any]]:
        """Parse tools-mcp-server.py for all MCP tool definitions."""
        tools_path = self.scripts_dir / "tools-mcp-server.py"
        if not tools_path.exists():
            print(f"{R}Error: tools-mcp-server.py not found{N}")
            return []

        raw = tools_path.read_text(encoding="utf-8")
        tools = []

        in_tools = False
        top_depth = 0
        current_lines: List[str] = []
        current_module = "Core"

        module_map = {
            "xTrace": "xTrace",
            "DTrace": "DTrace",
            "Skill Router": "Skill Router",
            "Output Condenser": "Output Condenser",
            "Goal Registry": "Goal Registry",
            "Commitment Checker": "Commitment Checker",
            "Art Module": "Art",
            "Literature Module": "Literature",
            "Sensory Module": "Sensory",
            "Audio Module": "Audio",
            "Coder Module": "Coder",
            "DevOps Module": "DevOps",
            "Game Dev Module": "Game Dev",
            "NE-Memory Search": "Memory Search",
            "Verifier Middleware": "Verifier",
        }

        for line in raw.split("\n"):
            mm = re.search(r'# --- (.+?) tools?\b', line)
            if mm:
                current_module = module_map.get(mm.group(1).strip(), mm.group(1).strip())

            if not in_tools:
                if "TOOLS = [" in line:
                    in_tools = True
                    top_depth = 1
                continue

            stripped = line.strip()
            delta = line.count("{") + line.count("[") - line.count("}") - line.count("]")
            old_depth = top_depth
            top_depth += delta

            is_single_line_tool = bool(re.search(r'"name"\s*:\s*"', stripped)) and stripped.startswith("{") and stripped.rstrip().endswith("},")

            if is_single_line_tool:
                tool = self._parse_tool_block(stripped, current_module)
                if tool:
                    tools.append(tool)
            elif old_depth == 1 and top_depth == 2 and not is_single_line_tool:
                current_lines = [line]
            elif old_depth >= 2 and not is_single_line_tool:
                current_lines.append(line)
                if top_depth == 1 and current_lines:
                    block = "".join(current_lines)
                    tool = self._parse_tool_block(block, current_module)
                    if tool:
                        tools.append(tool)
                    current_lines = []
            elif top_depth == 0 and "]" in line:
                in_tools = False

        self.mcp_tools = tools
        return tools

    def _parse_tool_block(self, block: str, module: str) -> Optional[Dict[str, Any]]:
        name = ""
        desc = ""
        params: List[Dict[str, Any]] = []
        required: List[str] = []

        nm = re.search(r'"name"\s*:\s*"([^"]+)"', block)
        if nm:
            name = nm.group(1)

        dm = re.search(r'"description"\s*:\s*"([^"]+)"', block)
        if dm:
            desc = dm.group(1)

        for pm in re.finditer(
            r'"(\w+)"\s*:\s*\{\s*"type"\s*:\s*"([^"]+)"',
            block,
        ):
            pname = pm.group(1)
            if pname in ("type", "required", "items", "inputSchema", "properties", "object", "array"):
                continue
            ptype = pm.group(2)
            pdesc = ""
            pdm = re.search(
                rf'"{pname}"\s*:{{[^}}]*?"description"\s*:\s*"([^"]+)"',
                block,
            )
            if pdm:
                pdesc = pdm.group(1)
            params.append({"name": pname, "type": ptype, "description": pdesc})

        rm = re.search(r'"required"\s*:\s*\[(.*?)\]', block)
        if rm:
            required = [r.strip(' "') for r in rm.group(1).split(",") if r.strip()]

        if not name:
            return None

        return {
            "name": name,
            "description": desc,
            "module": module,
            "parameters": params,
            "required": required,
            "param_count": len(params),
            "has_return_value": True,
        }

    def scan_data_files(self) -> List[Dict[str, Any]]:
        """Scan data/ for JSON files, extract schema and record count."""
        results = []
        for fpath in sorted(self.data_dir.rglob("*.json")):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            raw = fpath.read_text(encoding="utf-8", errors="replace")
            keys = list(self._extract_keys(data))
            record_count = self._count_records(data)

            category = "config"
            if "results" in fpath.name or "benchmark" in fpath.name:
                category = "results"
            elif "trace" in fpath.name or "log" in fpath.name:
                category = "trace"
            elif "registry" in fpath.name:
                category = "registry"
            elif "schema" in fpath.stem:
                category = "config"

            rel_path = fpath.relative_to(self.project_root)
            results.append({
                "filename": str(rel_path),
                "file_size": len(raw),
                "keys": keys[:20],
                "record_count": record_count,
                "category": category,
                "has_schema": "$schema" in raw,
            })
        self.data_files = results
        return results

    def _extract_keys(self, obj: Any, prefix: str = "") -> set:
        keys = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                full = f"{prefix}.{k}" if prefix else k
                keys.add(full)
                if isinstance(v, dict) and len(str(v)) < 2000:
                    keys |= self._extract_keys(v, full)
                elif isinstance(v, list) and v and isinstance(v[0], dict):
                    keys |= self._extract_keys(v[0], f"{full}[]")
        return keys

    def _count_records(self, obj: Any) -> int:
        if isinstance(obj, dict):
            for key in ("results", "records", "items", "entries", "decisions", "commitments", "tools"):
                if key in obj and isinstance(obj[key], list):
                    return len(obj[key])
            for v in obj.values():
                if isinstance(v, list):
                    return len(v)
            return 0
        elif isinstance(obj, list):
            return len(obj)
        return 0

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate_markdown(self) -> str:
        """Generate docs/api-overview.md."""
        self._ensure_docs_dir()

        total_py = sum(1 for s in self.scripts if s["language"] == "python")
        total_ps = sum(1 for s in self.scripts if s["language"] == "powershell")
        total_funcs = sum(len(s["functions"]) for s in self.scripts)
        total_classes = sum(len(s["classes"]) for s in self.scripts)
        modules = sorted(set(t["module"] for t in self.mcp_tools))
        total_data = len(self.data_files)

        lines = [
            "# CortexStratum API Documentation",
            "",
            f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*",
            "",
            "---",
            "",
            "## Project Overview",
            "",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| Python scripts | {total_py} |",
            f"| PowerShell scripts | {total_ps} |",
            f"| Total functions | {total_funcs} |",
            f"| Total classes | {total_classes} |",
            f"| MCP tools | {len(self.mcp_tools)} |",
            f"| MCP tool modules | {len(modules)} |",
            f"| Data files | {total_data} |",
            "",
            "---",
            "",
            "## Script Index",
            "",
            "| Script | Language | Purpose | Key Functions |",
            "|--------|----------|---------|---------------|",
        ]

        for s in self.scripts:
            purpose = s["docstring"][:80].replace("\n", " ") if s["docstring"] else "*No docstring*"
            funcs = ", ".join(f["name"] for f in s["functions"][:5])
            if len(s["functions"]) > 5:
                funcs += f" +{len(s['functions'])-5} more"
            lang = "py" if s["language"] == "python" else "ps1"
            lines.append(f"| `{s['filename']}` | {lang} | {purpose} | `{funcs}` |")

        lines += [
            "",
            "---",
            "## MCP Tools",
            "",
            f"Total: **{len(self.mcp_tools)}** tools across **{len(modules)}** modules.",
            "",
        ]

        for mod in sorted(modules):
            mod_tools = [t for t in self.mcp_tools if t["module"] == mod]
            if not mod_tools:
                continue
            lines.append(f"### {mod}")
            lines.append("")
            lines.append(f"_{len(mod_tools)} tools_")
            lines.append("")
            for t in mod_tools:
                req = ", ".join(t["required"]) if t["required"] else "None"
                params_table = ""
                if t["parameters"]:
                    param_rows = "\n".join(
                        f"| `{p['name']}` | `{p['type']}` | {p['description']} |"
                        for p in t["parameters"]
                    )
                    params_table = f"\n| Parameter | Type | Description |\n|-----------|------|-------------|\n{param_rows}\n"
                lines.append(f"#### `{t['name']}`")
                lines.append("")
                lines.append(f"**Description:** {t['description']}")
                lines.append(f"**Required:** {req}")
                if params_table:
                    lines.append(params_table)
                lines.append("")

        lines += [
            "---",
            "## Data Files",
            "",
            "| File | Category | Keys | Records |",
            "|------|----------|------|---------|",
        ]

        for d in self.data_files:
            key_sample = ", ".join(d["keys"][:5])
            if len(d["keys"]) > 5:
                key_sample += " ..."
            lines.append(
                f"| `{d['filename']}` | {d['category']} | `{key_sample}` | {d['record_count']} |"
            )

        lines += [
            "",
            "---",
            "## Integration Points",
            "",
            "### MCP Server",
            f"- Entry point: `scripts/tools-mcp-server.py` — JSON-RPC over stdio",
            f"- Exposes {len(self.mcp_tools)} tools across {len(modules)} modules",
            "- Protocol: Model Context Protocol (MCP) v2024-11-05",
            "",
            "### Data Flow",
            "- Scripts in `scripts/` produce output consumed by other scripts or the MCP server",
            "- `data/` stores structured results, registries, and configuration",
            "- MCP server routes tool calls to PowerShell scripts and Python modules",
            "",
            "### Verifier Middleware",
            "- All tool calls pass through `VerifierMiddleware` pre/post checks",
            "- Mode: advisory (logs violations, does not block)",
        ]

        md = "\n".join(lines)
        (self.docs_dir / "api-overview.md").write_text(md, encoding="utf-8")
        return md

    def generate_html(self) -> str:
        """Generate docs/api-docs.html with dark theme and search."""
        self._ensure_docs_dir()

        total_py = sum(1 for s in self.scripts if s["language"] == "python")
        total_ps = sum(1 for s in self.scripts if s["language"] == "powershell")
        total_funcs = sum(len(s["functions"]) for s in self.scripts)
        modules = sorted(set(t["module"] for t in self.mcp_tools))

        scripts_rows = "".join(
            f"""
            <tr>
                <td><code>{s['filename']}</code></td>
                <td><span class="badge badge-{'py' if s['language'] == 'python' else 'ps'}">{'py' if s['language'] == 'python' else 'ps1'}</span></td>
                <td>{self._html_escape(s['docstring'][:120])}</td>
                <td><code>{', '.join(f['name'] for f in s['functions'][:3])}</code></td>
            </tr>"""
            for s in self.scripts
        )

        tools_by_mod: Dict[str, str] = {}
        for mod in modules:
            mod_tools = [t for t in self.mcp_tools if t["module"] == mod]
            tool_cards = ""
            for t in mod_tools:
                params_rows = "".join(
                    f"<tr><td><code>{p['name']}</code></td><td><code>{p['type']}</code></td><td>{self._html_escape(p['description'])}</td></tr>"
                    for p in t["parameters"]
                )
                req = ", ".join(f"<code>{r}</code>" for r in t["required"]) if t["required"] else "<em>None</em>"
                tool_cards += f"""
                <div class="tool-card">
                    <div class="tool-header" onclick="this.parentElement.classList.toggle('expanded')">
                        <span class="tool-name">{t['name']}</span>
                        <span class="tool-params">{t['param_count']} params</span>
                        <span class="expand-icon">&#9654;</span>
                    </div>
                    <div class="tool-body">
                        <p class="tool-desc">{self._html_escape(t['description'])}</p>
                        <p><strong>Required:</strong> {req}</p>
                        {f'<table class="param-table"><thead><tr><th>Parameter</th><th>Type</th><th>Description</th></tr></thead><tbody>{params_rows}</tbody></table>' if t['parameters'] else '<p><em>No parameters</em></p>'}
                    </div>
                </div>"""
            tools_by_mod[mod] = tool_cards

        mod_sections = "".join(
            f"""
            <div class="module-section" id="module-{mod.lower().replace(' ', '-')}">
                <h3>{mod} <span class="tool-count">{len([t for t in self.mcp_tools if t['module'] == mod])} tools</span></h3>
                {tools_by_mod[mod]}
            </div>"""
            for mod in modules
        )

        data_rows = "".join(
            f"""
            <tr>
                <td><code>{d['filename']}</code></td>
                <td><span class="badge badge-{d['category']}">{d['category']}</span></td>
                <td><code>{', '.join(d['keys'][:4])}</code></td>
                <td>{d['record_count']}</td>
            </tr>"""
            for d in self.data_files
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CortexStratum API Documentation</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', Roboto, sans-serif; background: #0d1117; color: #e6edf3; line-height: 1.6; }}
  .layout {{ display: flex; min-height: 100vh; }}
  .sidebar {{ width: 280px; background: #161b22; border-right: 1px solid #30363d; padding: 24px 16px; position: fixed; top: 0; left: 0; height: 100vh; overflow-y: auto; }}
  .sidebar h2 {{ font-size: 14px; font-weight: 600; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; margin: 20px 0 8px; }}
  .sidebar h2:first-child {{ margin-top: 0; }}
  .sidebar a {{ display: block; padding: 4px 8px; color: #c9d1d9; text-decoration: none; font-size: 13px; border-radius: 6px; }}
  .sidebar a:hover {{ background: #21262d; color: #58a6ff; }}
  .sidebar .mod-link {{ padding-left: 16px; font-size: 12px; }}
  .main {{ flex: 1; margin-left: 280px; padding: 32px 48px; max-width: 960px; }}
  h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 4px; background: linear-gradient(135deg, #58a6ff, #bc8cff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  h2 {{ font-size: 20px; font-weight: 600; margin: 32px 0 12px; padding-bottom: 8px; border-bottom: 1px solid #30363d; color: #f0f6fc; }}
  h3 {{ font-size: 16px; font-weight: 600; margin: 24px 0 12px; color: #f0f6fc; display: flex; align-items: center; gap: 12px; }}
  .subtitle {{ color: #8b949e; font-size: 14px; margin-bottom: 24px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin: 16px 0 24px; }}
  .stat-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; text-align: center; }}
  .stat-card .num {{ font-size: 28px; font-weight: 700; color: #58a6ff; }}
  .stat-card .label {{ font-size: 12px; color: #8b949e; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0 24px; font-size: 13px; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #21262d; }}
  th {{ background: #161b22; color: #8b949e; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.05em; }}
  tr:hover td {{ background: #161b22; }}
  code {{ background: #21262d; padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 12px; color: #ffa657; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
  .badge-py {{ background: #1a3a2b; color: #7ee787; }}
  .badge-ps {{ background: #1a2d4a; color: #79c0ff; }}
  .badge-config {{ background: #1a2d4a; color: #79c0ff; }}
  .badge-results {{ background: #2d1a3a; color: #d2a8ff; }}
  .badge-trace {{ background: #3a2a1a; color: #ffa657; }}
  .badge-registry {{ background: #1a3a2b; color: #7ee787; }}
  .tool-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; margin: 8px 0; overflow: hidden; }}
  .tool-header {{ display: flex; align-items: center; padding: 12px 16px; cursor: pointer; gap: 12px; user-select: none; }}
  .tool-header:hover {{ background: #1c2128; }}
  .tool-name {{ font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 600; color: #58a6ff; flex: 1; }}
  .tool-params {{ font-size: 11px; color: #8b949e; background: #21262d; padding: 2px 8px; border-radius: 8px; }}
  .expand-icon {{ color: #8b949e; font-size: 10px; transition: transform 0.2s; }}
  .tool-card.expanded .expand-icon {{ transform: rotate(90deg); }}
  .tool-body {{ display: none; padding: 0 16px 16px; }}
  .tool-card.expanded .tool-body {{ display: block; }}
  .tool-desc {{ color: #c9d1d9; margin-bottom: 8px; }}
  .param-table {{ font-size: 12px; }}
  .param-table th {{ background: #0d1117; }}
  .module-section {{ margin-bottom: 16px; }}
  .tool-count {{ font-size: 13px; font-weight: 400; color: #8b949e; }}
  .gen-info {{ font-size: 12px; color: #484f58; margin-top: 40px; text-align: center; padding: 16px; border-top: 1px solid #21262d; }}
  #search {{ width: 100%; padding: 10px 14px; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; color: #e6edf3; font-size: 14px; margin-bottom: 16px; outline: none; }}
  #search:focus {{ border-color: #58a6ff; }}
  ::-webkit-scrollbar {{ width: 8px; }}
  ::-webkit-scrollbar-track {{ background: #0d1117; }}
  ::-webkit-scrollbar-thumb {{ background: #30363d; border-radius: 4px; }}
  @media (max-width: 768px) {{ .sidebar {{ display: none; }} .main {{ margin-left: 0; padding: 16px; }} }}
</style>
</head>
<body>
<div class="layout">
  <nav class="sidebar">
    <h2>Overview</h2>
    <a href="#overview">Project Stats</a>
    <a href="#scripts">Scripts</a>
    <h2>MCP Tools</h2>"""
        for mod in modules:
            html += f'\n    <a href="#module-{mod.lower().replace(" ", "-")}" class="mod-link">{mod}</a>'
        html += f"""
    <h2>Data</h2>
    <a href="#data-files">Data Files</a>
  </nav>
  <div class="main">
    <h1>CortexStratum</h1>
    <p class="subtitle">API Documentation &mdash; {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>

    <section id="overview">
      <h2>Project Overview</h2>
      <div class="stats-grid">
        <div class="stat-card"><div class="num">{len(self.scripts)}</div><div class="label">Scripts</div></div>
        <div class="stat-card"><div class="num">{len(self.mcp_tools)}</div><div class="label">MCP Tools</div></div>
        <div class="stat-card"><div class="num">{len(modules)}</div><div class="label">Modules</div></div>
        <div class="stat-card"><div class="num">{total_funcs}</div><div class="label">Functions</div></div>
        <div class="stat-card"><div class="num">{len(self.data_files)}</div><div class="label">Data Files</div></div>
      </div>
    </section>

    <section id="scripts">
      <h2>Script Index</h2>
      <input type="text" id="search" placeholder="Filter scripts, tools, modules..." oninput="filterDocs(this.value)">
      <table>
        <thead><tr><th>Script</th><th>Lang</th><th>Purpose</th><th>Key Functions</th></tr></thead>
        <tbody>{scripts_rows}</tbody>
      </table>
    </section>

    <section id="mcp-tools">
      <h2>MCP Tools <span style="font-size:14px;color:#8b949e;font-weight:400;">({len(self.mcp_tools)} total)</span></h2>
      {mod_sections}
    </section>

    <section id="data-files">
      <h2>Data Files</h2>
      <table>
        <thead><tr><th>File</th><th>Category</th><th>Keys</th><th>Records</th></tr></thead>
        <tbody>{data_rows}</tbody>
      </table>
    </section>

    <div class="gen-info">Generated by doc-generator.py &mdash; CortexStratum</div>
  </div>
</div>
<script>
function filterDocs(q) {{
  q = q.toLowerCase();
  document.querySelectorAll('.tool-card').forEach(c => {{
    c.style.display = c.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
  document.querySelectorAll('#scripts tbody tr').forEach(r => {{
    r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
  document.querySelectorAll('.module-section').forEach(s => {{
    const visible = Array.from(s.querySelectorAll('.tool-card')).some(c => c.style.display !== 'none');
    s.style.display = visible || q === '' ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""
        (self.docs_dir / "api-docs.html").write_text(html, encoding="utf-8")
        return html

    def generate_json_index(self) -> str:
        """Generate data/doc-index.json — machine-readable index."""
        self._ensure_docs_dir()
        index = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project": "CortexStratum",
            "version": "1.0.0",
            "scripts": [
                {
                    "filename": s["filename"],
                    "language": s["language"],
                    "docstring_preview": s["docstring"][:200] if s["docstring"] else "",
                    "function_count": len(s["functions"]),
                    "functions": [f["name"] for f in s["functions"]],
                    "classes": [c["name"] for c in s["classes"]],
                }
                for s in self.scripts
            ],
            "mcp_tools": [
                {
                    "name": t["name"],
                    "module": t["module"],
                    "description": t["description"],
                    "param_count": t["param_count"],
                    "required": t["required"],
                }
                for t in self.mcp_tools
            ],
            "data_files": [
                {
                    "filename": d["filename"],
                    "category": d["category"],
                    "record_count": d["record_count"],
                    "key_count": len(d["keys"]),
                }
                for d in self.data_files
            ],
            "summary": {
                "total_scripts": len(self.scripts),
                "total_python": sum(1 for s in self.scripts if s["language"] == "python"),
                "total_powershell": sum(1 for s in self.scripts if s["language"] == "powershell"),
                "total_mcp_tools": len(self.mcp_tools),
                "total_mcp_modules": len(set(t["module"] for t in self.mcp_tools)),
                "total_data_files": len(self.data_files),
            },
        }
        path = self.data_dir / "doc-index.json"
        path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def generate_tool_inventory(self) -> str:
        """Generate data/tool-inventory.json — flat list of all MCP tools."""
        inventory = [
            {
                "id": t["name"],
                "module": t["module"],
                "name": t["name"],
                "description": t["description"],
                "param_count": t["param_count"],
                "has_return_value": t["has_return_value"],
            }
            for t in self.mcp_tools
        ]
        path = self.data_dir / "tool-inventory.json"
        path.write_text(
            json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return str(path)

    def _ensure_docs_dir(self):
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _html_escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    # ------------------------------------------------------------------
    # Print helpers
    # ------------------------------------------------------------------

    def print_summary(self):
        print(f"\n{B}{'='*60}{N}")
        print(f"{BOLD}CortexStratum Documentation Summary{N}")
        print(f"{B}{'='*60}{N}")

        total_py = sum(1 for s in self.scripts if s["language"] == "python")
        total_ps = sum(1 for s in self.scripts if s["language"] == "powershell")
        total_funcs = sum(len(s["functions"]) for s in self.scripts)
        total_classes = sum(len(s["classes"]) for s in self.scripts)
        modules = sorted(set(t["module"] for t in self.mcp_tools))

        print(f"\n  {G}Scripts{N}:    {total_py} Python, {total_ps} PowerShell ({len(self.scripts)} total)")
        print(f"  {G}Functions{N}:  {total_funcs}")
        print(f"  {G}Classes{N}:    {total_classes}")
        print(f"  {G}MCP Tools{N}:  {len(self.mcp_tools)} across {len(modules)} modules")
        print(f"  {G}Data Files{N}: {len(self.data_files)}")

        print(f"\n  {BOLD}Scripts:{N}")
        for s in self.scripts:
            purpose = s["docstring"][:60].replace("\n", " ") if s["docstring"] else ""
            icon = "[py]" if s["language"] == "python" else "[ps]"
            print(f"    {icon:5s} {s['filename']:35s} {DIM}{purpose}{N}")

        print(f"\n  {BOLD}MCP Modules:{N}")
        for mod in modules:
            count = sum(1 for t in self.mcp_tools if t["module"] == mod)
            print(f"    {C}{mod:20s}{N} {count} tools")

    def run_all(self):
        """Run full scan and generate all outputs."""
        print(f"{BOLD}Scanning scripts...{N}")
        self.scan_scripts()
        print(f"  Found {len(self.scripts)} scripts")

        print(f"{BOLD}Scanning MCP tools...{N}")
        self.scan_mcp_tools()
        print(f"  Found {len(self.mcp_tools)} tools")

        print(f"{BOLD}Scanning data files...{N}")
        self.scan_data_files()
        print(f"  Found {len(self.data_files)} data files")

        self.print_summary()

        print(f"\n{BOLD}Generating markdown...{N}")
        self.generate_markdown()
        print(f"  {G}ok{N} docs/api-overview.md")

        print(f"{BOLD}Generating HTML...{N}")
        self.generate_html()
        print(f"  {G}ok{N} docs/api-docs.html")

        print(f"{BOLD}Generating JSON index...{N}")
        idx_path = self.generate_json_index()
        print(f"  {G}ok{N} {idx_path}")

        print(f"{BOLD}Generating tool inventory...{N}")
        inv_path = self.generate_tool_inventory()
        print(f"  {G}ok{N} {inv_path}")

        print(f"\n{G}{'='*60}{N}")
        print(f"{G}Documentation generated successfully.{N}")
        print(f"{G}{'='*60}{N}")


def watch_mode(dg: DocGenerator):
    """Watch scripts/ for changes and regenerate docs."""
    print(f"{BOLD}Watch mode enabled. Press Ctrl+C to stop.{N}")
    last_mtimes = {}
    for f in SCRIPTS_DIR.iterdir():
        if f.suffix in (".py", ".ps1"):
            last_mtimes[f] = f.stat().st_mtime

    try:
        while True:
            changed = False
            for f in SCRIPTS_DIR.iterdir():
                if f.suffix not in (".py", ".ps1"):
                    continue
                mtime = f.stat().st_mtime
                if last_mtimes.get(f, 0) != mtime:
                    print(f"  {Y}Change detected: {f.name}{N}")
                    last_mtimes[f] = mtime
                    changed = True
            if changed:
                dg.run_all()
                print(f"  {G}Regenerated.{N}")
            time.sleep(2)
    except KeyboardInterrupt:
        print(f"\n{Y}Watch mode stopped.{N}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CortexStratum Documentation Generator")
    parser.add_argument("--scan", action="store_true", help="Quick scan, print summary")
    parser.add_argument("--generate-md", action="store_true", help="Generate markdown docs")
    parser.add_argument("--generate-html", action="store_true", help="Generate HTML docs")
    parser.add_argument("--generate-all", action="store_true", help="Generate everything")
    parser.add_argument("--watch", action="store_true", help="Watch mode")

    args = parser.parse_args()

    dg = DocGenerator()

    if args.scan:
        dg.scan_scripts()
        dg.scan_mcp_tools()
        dg.scan_data_files()
        dg.print_summary()

    elif args.generate_md:
        dg.scan_scripts()
        dg.scan_mcp_tools()
        dg.scan_data_files()
        dg.generate_markdown()
        print(f"{G}ok{N} docs/api-overview.md")

    elif args.generate_html:
        dg.scan_scripts()
        dg.scan_mcp_tools()
        dg.scan_data_files()
        dg.generate_html()
        print(f"{G}ok{N} docs/api-docs.html")

    elif args.generate_all:
        dg.run_all()

    elif args.watch:
        dg.scan_scripts()
        dg.scan_mcp_tools()
        dg.scan_data_files()
        watch_mode(dg)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
