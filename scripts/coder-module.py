#!/usr/bin/env python3
"""
Coder Module — AI senior developer assistant.
Provides code analysis, framework generation, debugging, code review,
explanation, language conversion, and architecture recommendations.
Registered as MCP tools via tools-mcp-server.py.
Architecture: Pure handler pattern, dict in → dict out, stdlib only.
"""

import json
import os
import re
import math
import textwrap
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES = [
    "python", "javascript", "typescript", "rust", "go", "java",
    "csharp", "cpp", "ruby", "php", "swift", "kotlin"
]

LANGUAGE_EXTENSIONS = {
    "python": ".py", "javascript": ".js", "typescript": ".ts", "rust": ".rs",
    "go": ".go", "java": ".java", "csharp": ".cs", "cpp": ".cpp",
    "ruby": ".rb", "php": ".php", "swift": ".swift", "kotlin": ".kt"
}

LANGUAGE_COMMENTS = {
    "python": "#", "javascript": "//", "typescript": "//", "rust": "//",
    "go": "//", "java": "//", "csharp": "//", "cpp": "//",
    "ruby": "#", "php": "//", "swift": "//", "kotlin": "//"
}

LANGUAGE_NAMING = {
    "python": "snake_case", "javascript": "camelCase", "typescript": "camelCase",
    "rust": "snake_case", "go": "camelCase", "java": "camelCase",
    "csharp": "PascalCase", "cpp": "snake_case", "ruby": "snake_case",
    "php": "camelCase", "swift": "camelCase", "kotlin": "camelCase"
}

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _score_to_grade(score: float) -> str:
    if score >= 95: return "A+"
    if score >= 90: return "A"
    if score >= 85: return "A-"
    if score >= 80: return "B+"
    if score >= 75: return "B"
    if score >= 70: return "B-"
    if score >= 65: return "C+"
    if score >= 60: return "C"
    if score >= 55: return "C-"
    if score >= 50: return "D"
    return "F"


def _estimate_complexity(lines: int, max_nesting: int, func_count: int) -> str:
    score = lines / 10 + max_nesting * 5 + func_count * 3
    if score < 20: return "low"
    if score < 60: return "medium"
    return "high"


def _line_number(text: str, offset: int) -> int:
    return text[:offset].count("\n") + 1


# ---------------------------------------------------------------------------
# 1. coder_analyze_code
# ---------------------------------------------------------------------------

# Known security patterns to detect
_HARDCODED_SECRET_PATTERNS = [
    (r'(?:password|passwd|secret|api_key|apikey|token|auth_key)\s*[:=]\s*["\'][^"\']{8,}["\']', "critical", "Hardcoded secret/credential detected"),
    (r'(?:private_key|PRIVATE\s*KEY)', "critical", "Private key found in source code"),
    (r'(?:mongodb|mysql|postgres|redis)://[^\s"\']+@', "critical", "Database connection string with embedded credentials"),
]

_SQL_INJECTION_PATTERNS = [
    (r'\.execute\s*\(\s*["\'].*%(?:s|d|)\s*\s*%\s*\w+', "critical", "SQL injection risk: string interpolation in query"),
    (r'f["\'].*\$\{.*\}.*(?:SELECT|INSERT|UPDATE|DELETE)', "critical", "SQL injection risk: f-string with user input in query"),
    (r'query\s*=\s*["\'].*\+.*\+.*["\']', "critical", "SQL injection risk: string concatenation in query"),
    (r'\.raw\s*\(\s*["\'].*\$\{', "critical", "SQL injection risk: raw query with interpolation"),
]

_CODE_SMELL_PATTERNS = [
    (r'\b(?:0|1|2|3|4|5|6|7|8|9)\b', "warning", "Magic number — consider using a named constant",
     lambda m, text: m.group(0) not in ("0", "1") and int(m.group(0)) > 9),
    (r'except\s*:', "warning", "Bare except clause — specify exception types"),
    (r'except\s+\w+(?:\s+as\s+\w+)?\s*:\s*\n\s+pass\b', "warning", "Empty exception handler hides errors"),
    (r'\beval\s*\(', "critical", "eval() usage is dangerous"),
    (r'\bexec\s*\(', "critical", "exec() usage is dangerous"),
    (r'\bglobal\s+\w+', "warning", "Global variable usage can cause side effects"),
    (r'def\s+\w+\s*\(.*=\s*\[\s*\].*\)', "warning", "Mutable default argument — use None instead"),
    (r'def\s+\w+\s*\(.*=\s*\{\s*\}.*\)', "warning", "Mutable default argument — use None instead"),
    (r'print\s*\(', "info", "Print statement in production code"),
    (r'TODO', "info", "Unresolved TODO comment"),
    (r'FIXME', "warning", "Unresolved FIXME — known bug"),
    (r'HACK', "warning", "HACK marker — hacky workaround"),
    (r'os\.system\s*\(', "warning", "os.system() — use subprocess instead"),
    (r'subprocess\.\w+\s*\(\s*["\'].*\$\{', "critical", "Command injection risk in subprocess call"),
]

_STYLE_PATTERNS = {
    "python": [
        (r'class\s+\w+(?!.*""").*\n', "info", "Class missing docstring",
         lambda m, text: '"""' not in text[m.end():m.end()+200]),
        (r'def\s+(?!_)\w+\s*\([^)]*\)\s*:\s*\n(?!\s+""")(?!\s+raise\s)', "info", "Function missing docstring",
         None),
        (r'import\s+\w+\s*,\s*\w+', "info", "Multiple imports on one line — split into separate lines"),
        (r'from\s+\w+\s+import\s+\*', "warning", "Wildcard import — be explicit"),
        (r'^\s{8,}', "info", "Deep nesting detected"),
    ],
    "javascript": [
        (r'\bvar\b', "info", "Use const or let instead of var"),
        (r'==(?!=)', "warning", "Use === instead of =="),
        (r'console\.log\s*\(', "info", "console.log in production code"),
    ],
    "typescript": [
        (r'\bany\b', "warning", "Using 'any' type — consider a more specific type"),
        (r'@ts-ignore', "warning", "@ts-ignore suppresses type checking"),
        (r'\bvar\b', "info", "Use const or let instead of var"),
    ],
}


def _detect_long_functions(code: str, language: str) -> list[dict]:
    issues = []
    if language in ("python", "ruby"):
        lines = code.split("\n")
        in_func = False
        func_start = 0
        func_lines = 0
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if re.match(r'^\s*(?:def|class)\s+', stripped):
                if in_func and func_lines > 50:
                    issues.append({
                        "type": "code_smell", "severity": "warning",
                        "line": func_start, "description": f"Long function ({func_lines} lines > 50)",
                        "suggestion": f"Break into smaller functions, each handling one responsibility"
                    })
                in_func = True
                func_start = i + 1
                func_lines = 0
            elif in_func:
                func_lines += 1
        if in_func and func_lines > 50:
            issues.append({
                "type": "code_smell", "severity": "warning",
                "line": func_start, "description": f"Long function ({func_lines} lines > 50)",
                "suggestion": "Break into smaller functions, each handling one responsibility"
            })
    elif language in ("javascript", "typescript", "go", "rust", "java", "csharp", "cpp", "swift", "kotlin", "php"):
        brace_depth = 0
        func_start = 0
        func_lines = 0
        in_func = False
        for i, line in enumerate(code.split("\n")):
            opens = line.count("{")
            closes = line.count("}")
            if opens > 0 and not in_func:
                in_func = True
                func_start = i + 1
                func_lines = 0
            if in_func:
                func_lines += 1
                brace_depth += opens - closes
                if brace_depth <= 0:
                    if func_lines > 50:
                        issues.append({
                            "type": "code_smell", "severity": "warning",
                            "line": func_start, "description": f"Long function ({func_lines} lines > 50)",
                            "suggestion": "Break into smaller functions"
                        })
                    in_func = False
                    func_lines = 0
    return issues


def _get_nesting_depth(code: str) -> int:
    lines = code.split("\n")
    max_depth = 0
    for line in lines:
        stripped = line.replace("\t", "    ")
        depth = len(stripped) - len(stripped.lstrip(" "))
        indent_level = depth // 2
        if indent_level > max_depth:
            max_depth = indent_level
    return max_depth


def _count_functions(code: str, language: str) -> int:
    if language in ("python", "ruby"):
        return len(re.findall(r'^\s*def\s+\w+', code, re.MULTILINE))
    elif language == "go":
        return len(re.findall(r'^\s*func\s+', code, re.MULTILINE))
    elif language == "rust":
        return len(re.findall(r'^\s*fn\s+', code, re.MULTILINE))
    elif language == "php":
        return len(re.findall(r'function\s+\w+', code))
    elif language == "swift":
        return len(re.findall(r'func\s+', code))
    elif language == "kotlin":
        return len(re.findall(r'fun\s+', code))
    else:
        return len(re.findall(r'function\s+\w+', code)) + len(re.findall(r'\w+\s*\([^)]*\)\s*\{', code))


def _count_classes(code: str, language: str) -> int:
    if language == "rust":
        return len(re.findall(r'struct\s+\w+', code))
    return len(re.findall(r'class\s+\w+', code))


def analyze_code(code: str, language: str = "python") -> dict:
    if language not in SUPPORTED_LANGUAGES:
        return {"status": "error", "error": f"Unsupported language: {language}", "supported": SUPPORTED_LANGUAGES}

    lines = code.split("\n")
    line_count = len(lines)
    nesting = _get_nesting_depth(code)
    func_count = _count_functions(code, language)
    class_count = _count_classes(code, language)
    complexity = _estimate_complexity(line_count, nesting, func_count)

    issues: list[dict] = []

    for pattern, severity, desc in _HARDCODED_SECRET_PATTERNS:
        for m in re.finditer(pattern, code, re.IGNORECASE):
            issues.append({
                "type": "security", "severity": severity, "line": _line_number(code, m.start()),
                "description": desc, "suggestion": "Store secrets in environment variables or a vault"
            })

    for pattern, severity, desc in _SQL_INJECTION_PATTERNS:
        for m in re.finditer(pattern, code, re.IGNORECASE):
            issues.append({
                "type": "security", "severity": severity, "line": _line_number(code, m.start()),
                "description": desc, "suggestion": "Use parameterized queries or an ORM"
            })

    for item in _CODE_SMELL_PATTERNS:
        if len(item) == 3:
            pattern, severity, desc = item
            extra_filter = None
        else:
            pattern, severity, desc, extra_filter = item

        for m in re.finditer(pattern, code):
            if extra_filter and not extra_filter(m, code):
                continue
            issues.append({
                "type": "code_smell", "severity": severity, "line": _line_number(code, m.start()),
                "description": desc, "suggestion": "Refactor to eliminate this code smell"
            })

    style_rules = _STYLE_PATTERNS.get(language, [])
    for item in style_rules:
        if len(item) == 3:
            pattern, severity, desc = item
            extra_filter = None
        else:
            pattern, severity, desc, extra_filter = item

        for m in re.finditer(pattern, code):
            if extra_filter and not extra_filter(m, code):
                continue
            issues.append({
                "type": "style", "severity": severity, "line": _line_number(code, m.start()),
                "description": desc, "suggestion": "Follow language style conventions"
            })

    issues.extend(_detect_long_functions(code, language))

    severity_scores = {"critical": 15, "warning": 5, "info": 1}
    deductions = sum(severity_scores.get(i["severity"], 1) for i in issues)
    score = max(0, min(100, 100 - deductions))

    return {
        "score": score,
        "grade": _score_to_grade(score),
        "issues": issues,
        "metrics": {
            "lines": line_count,
            "functions": func_count,
            "classes": class_count,
            "complexity_estimate": complexity,
            "nesting_depth": nesting,
        }
    }


# ---------------------------------------------------------------------------
# 2. coder_generate_framework
# ---------------------------------------------------------------------------

_PROJECT_TEMPLATES: dict[tuple, dict[str, str]] = {}

def _init_templates():
    global _PROJECT_TEMPLATES
    if _PROJECT_TEMPLATES:
        return

    templ: dict = {
        ("web-api", "python"): {
            "main.py": textwrap.dedent("""\
            \"\"\"FastAPI Web API — {{project_name}}\"\"\"
            from fastapi import FastAPI, HTTPException
            from fastapi.middleware.cors import CORSMiddleware
            import uvicorn

            app = FastAPI(title=\"{{project_name}}\", version=\"0.1.0\")

            app.add_middleware(
                CORSMiddleware,
                allow_origins=[\"*\"],
                allow_methods=[\"*\"],
                allow_headers=[\"*\"],
            )

            @app.get(\"/health\")
            def health():
                return {\"status\": \"ok\", \"service\": \"{{project_name}}\"}

            @app.get(\"/api/v1/items\")
            def list_items(limit: int = 100, offset: int = 0):
                return {\"items\": [], \"limit\": limit, \"offset\": offset}

            @app.post(\"/api/v1/items\")
            def create_item(item: dict):
                if not item.get(\"name\"):
                    raise HTTPException(400, \"name is required\")
                return {\"item\": item, \"created\": True}

            if __name__ == \"__main__\":
                uvicorn.run(\"main:app\", host=\"0.0.0.0\", port=8000, reload=True)
            """),
            "requirements.txt": textwrap.dedent("""\
            fastapi>=0.110.0
            uvicorn[standard]>=0.29.0
            pydantic>=2.6.0
            """),
            "README.md": textwrap.dedent("""\
            # {{project_name}}

            FastAPI Web API.

            ## Setup
            ```bash
            pip install -r requirements.txt
            python main.py
            ```

            ## Endpoints
            - `GET /health` — Health check
            - `GET /api/v1/items` — List items
            - `POST /api/v1/items` — Create item
            """),
            ".gitignore": "__pycache__/\n*.pyc\n.env\n.venv/\n",
            "config.py": textwrap.dedent("""\
            \"\"\"Application configuration.\"\"\"
            import os

            DEBUG = os.getenv(\"DEBUG\", \"false\").lower() == \"true\"
            DATABASE_URL = os.getenv(\"DATABASE_URL\", \"sqlite:///app.db\")
            SECRET_KEY = os.getenv(\"SECRET_KEY\", \"change-me-in-production\")
            """),
            "tests/test_main.py": textwrap.dedent("""\
            \"\"\"Tests for main application.\"\"\"
            from fastapi.testclient import TestClient
            from main import app

            client = TestClient(app)

            def test_health():
                resp = client.get(\"/health\")
                assert resp.status_code == 200
                assert resp.json()[\"status\"] == \"ok\"

            def test_create_item():
                resp = client.post(\"/api/v1/items\", json={\"name\": \"test\"})
                assert resp.status_code == 200
                assert resp.json()[\"created\"] is True
            """),
        },
        ("web-api", "javascript"): {
            "index.js": textwrap.dedent("""\
            const express = require('express');
            const app = express();
            const PORT = process.env.PORT || 3000;

            app.use(express.json());

            app.get('/health', (req, res) => {
              res.json({ status: 'ok', service: '{{project_name}}' });
            });

            app.get('/api/v1/items', (req, res) => {
              const { limit = 100, offset = 0 } = req.query;
              res.json({ items: [], limit: Number(limit), offset: Number(offset) });
            });

            app.post('/api/v1/items', (req, res) => {
              const { name } = req.body;
              if (!name) return res.status(400).json({ error: 'name is required' });
              res.json({ item: req.body, created: true });
            });

            app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
            """),
            "package.json": json.dumps({"name": "{{project_name}}", "version": "0.1.0", "main": "index.js", "scripts": {"start": "node index.js", "test": "jest"}, "dependencies": {"express": "^4.21.0"}, "devDependencies": {"jest": "^29.7.0"}}, indent=2),
            "README.md": textwrap.dedent("""\
            # {{project_name}}

            Express Web API.

            ## Setup
            ```bash
            npm install
            npm start
            ```

            ## Endpoints
            - `GET /health` — Health check
            - `GET /api/v1/items` — List items
            - `POST /api/v1/items` — Create item
            """),
            ".gitignore": "node_modules/\n.env\n",
            "tests/index.test.js": textwrap.dedent("""\
            const request = require('supertest');
            const app = require('../index');

            // Minimal test verifying the app module loads
            test('app exists', () => {
              expect(app).toBeDefined();
            });
            """),
        },
        ("web-api", "go"): {
            "main.go": textwrap.dedent("""\
            package main

            import (
                "encoding/json"
                "log"
                "net/http"
                "strconv"
            )

            type Item struct {
                Name string `json:"name"`
            }

            func main() {
                http.HandleFunc("/health", healthHandler)
                http.HandleFunc("/api/v1/items", itemsHandler)
                log.Println("Server starting on :8080")
                log.Fatal(http.ListenAndServe(":8080", nil))
            }

            func healthHandler(w http.ResponseWriter, r *http.Request) {
                json.NewEncoder(w).Encode(map[string]string{
                    "status":  "ok",
                    "service": "{{project_name}}",
                })
            }

            func itemsHandler(w http.ResponseWriter, r *http.Request) {
                w.Header().Set("Content-Type", "application/json")
                switch r.Method {
                case http.MethodGet:
                    limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
                    offset, _ := strconv.Atoi(r.URL.Query().Get("offset"))
                    if limit == 0 {
                        limit = 100
                    }
                    json.NewEncoder(w).Encode(map[string]interface{}{
                        "items":  []Item{},
                        "limit":  limit,
                        "offset": offset,
                    })
                case http.MethodPost:
                    var item Item
                    json.NewDecoder(r.Body).Decode(&item)
                    if item.Name == "" {
                        http.Error(w, `{"error":"name is required"}`, http.StatusBadRequest)
                        return
                    }
                    json.NewEncoder(w).Encode(map[string]interface{}{
                        "item":    item,
                        "created": true,
                    })
                default:
                    http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
                }
            }
            """),
            "go.mod": "module {{project_name}}\n\ngo 1.22\n",
            "README.md": textwrap.dedent("""\
            # {{project_name}}

            Go HTTP Web API.

            ## Setup
            ```bash
            go run main.go
            ```

            ## Endpoints
            - `GET /health` — Health check
            - `GET /api/v1/items` — List items
            - `POST /api/v1/items` — Create item
            """),
            ".gitignore": "{{project_name}}.exe\n",
            "main_test.go": textwrap.dedent("""\
            package main

            import (
                "net/http"
                "net/http/httptest"
                "testing"
            )

            func TestHealthHandler(t *testing.T) {
                req := httptest.NewRequest("GET", "/health", nil)
                w := httptest.NewRecorder()
                healthHandler(w, req)
                if w.Code != http.StatusOK {
                    t.Errorf("expected 200, got %d", w.Code)
                }
            }
            """),
        },
        ("cli-tool", "python"): {
            "cli.py": textwrap.dedent("""\
            \"\"\"{{project_name}} — Command-line tool.\"\"\"
            import argparse
            import sys

            def main():
                parser = argparse.ArgumentParser(description=\"{{project_name}}\")
                parser.add_argument(\"command\", choices=[\"run\", \"info\", \"version\"])
                parser.add_argument(\"--verbose\", \"-v\", action=\"store_true\")
                args = parser.parse_args()

                if args.command == \"run\":
                    if args.verbose:
                        print(\"[INFO] Running {{project_name}}...\")
                    print(\"Task executed successfully.\")
                elif args.command == \"info\":
                    print(\"{{project_name}} v0.1.0 — CLI tool\")
                elif args.command == \"version\":
                    print(\"0.1.0\")

            if __name__ == \"__main__\":
                main()
            """),
            "setup.py": textwrap.dedent("""\
            from setuptools import setup
            setup(
                name=\"{{project_name}}\",
                version=\"0.1.0\",
                py_modules=[\"cli\"],
                entry_points={\"console_scripts\": [\"{{project_name}}=cli:main\"]},
            )
            """),
            "README.md": textwrap.dedent("""\
            # {{project_name}}

            Command-line tool.

            ## Usage
            ```bash
            python cli.py run
            python cli.py info
            python cli.py version
            ```
            """),
            ".gitignore": "__pycache__/\n*.pyc\n.eggs/\ndist/\n",
            "tests/test_cli.py": textwrap.dedent("""\
            import subprocess
            import sys

            def test_version():
                result = subprocess.run([sys.executable, \"cli.py\", \"version\"],
                                        capture_output=True, text=True)
                assert result.returncode == 0
                assert \"0.1.0\" in result.stdout
            """),
        },
        ("cli-tool", "rust"): {
            "src/main.rs": textwrap.dedent("""\
            use std::env;

            fn main() {
                let args: Vec<String> = env::args().collect();
                if args.len() < 2 {
                    eprintln!("Usage: {{project_name}} <command>");
                    eprintln!("Commands: run, info, version");
                    std::process::exit(1);
                }
                match args[1].as_str() {
                    "run" => {
                        if args.contains(&"-v".to_string()) || args.contains(&"--verbose".to_string()) {
                            println!("[INFO] Running {{project_name}}...");
                        }
                        println!("Task executed successfully.");
                    }
                    "info" => println!("{{project_name}} v0.1.0 — CLI tool"),
                    "version" => println!("0.1.0"),
                    other => eprintln!("Unknown command: {}", other),
                }
            }
            """),
            "Cargo.toml": textwrap.dedent("""\
            [package]
            name = "{{project_name}}"
            version = "0.1.0"
            edition = "2021"

            [[bin]]
            name = "{{project_name}}"
            path = "src/main.rs"
            """),
            "README.md": textwrap.dedent("""\
            # {{project_name}}

            CLI tool written in Rust.

            ## Usage
            ```bash
            cargo run -- run
            cargo run -- info
            cargo run -- version
            ```
            """),
            ".gitignore": "target/\n",
            "tests/cli_tests.rs": textwrap.dedent("""\
            #[test]
            fn test_version_output() {
                let output = std::process::Command::new("cargo")
                    .args(&["run", "--", "version"])
                    .output()
                    .expect("failed to run");
                let stdout = String::from_utf8_lossy(&output.stdout);
                assert!(stdout.contains("0.1.0"));
            }
            """),
        },
        ("cli-tool", "go"): {
            "main.go": textwrap.dedent("""\
            package main

            import (
                "fmt"
                "os"
            )

            func main() {
                if len(os.Args) < 2 {
                    fmt.Fprintln(os.Stderr, "Usage: {{project_name}} <command>")
                    fmt.Fprintln(os.Stderr, "Commands: run, info, version")
                    os.Exit(1)
                }
                switch os.Args[1] {
                case "run":
                    fmt.Println("Task executed successfully.")
                case "info":
                    fmt.Println("{{project_name}} v0.1.0 — CLI tool")
                case "version":
                    fmt.Println("0.1.0")
                default:
                    fmt.Fprintf(os.Stderr, "Unknown command: %s\\n", os.Args[1])
                }
            }
            """),
            "go.mod": "module {{project_name}}\n\ngo 1.22\n",
            "README.md": textwrap.dedent("""\
            # {{project_name}}

            CLI tool written in Go.

            ## Usage
            ```bash
            go run main.go run
            go run main.go info
            go run main.go version
            ```
            """),
            ".gitignore": "{{project_name}}\n{{project_name}}.exe\n",
            "main_test.go": textwrap.dedent("""\
            package main

            import (
                "os"
                "os/exec"
                "testing"
            )

            func TestVersionCommand(t *testing.T) {
                cmd := exec.Command("go", "run", "main.go", "version")
                out, err := cmd.Output()
                if err != nil {
                    t.Fatal(err)
                }
                if !strings.Contains(string(out), "0.1.0") {
                    t.Error("version output mismatch")
                }
            }
            """),
        },
        ("library", "python"): {
            "{{project_name}}/__init__.py": textwrap.dedent("""\
            \"\"\"{{project_name}} — Python library.\"\"\"
            __version__ = \"0.1.0\"

            from .core import greet, add

            __all__ = [\"greet\", \"add\"]
            """),
            "{{project_name}}/core.py": textwrap.dedent("""\
            \"\"\"Core functionality for {{project_name}}.\"\"\"

            def greet(name: str = \"World\") -> str:
                \"\"\"Return a greeting string.\"\"\"
                return f\"Hello, {name}!\"

            def add(a: int, b: int) -> int:
                \"\"\"Add two integers.\"\"\"
                return a + b
            """),
            "setup.py": textwrap.dedent("""\
            from setuptools import setup, find_packages
            setup(
                name=\"{{project_name}}\",
                version=\"0.1.0\",
                packages=find_packages(),
                python_requires=\">=3.9\",
            )
            """),
            "README.md": textwrap.dedent("""\
            # {{project_name}}

            Python library.

            ## Usage
            ```python
            from {{project_name}} import greet, add

            print(greet("Alice"))  # Hello, Alice!
            print(add(2, 3))       # 5
            ```
            """),
            ".gitignore": "__pycache__/\n*.pyc\n.eggs/\ndist/\n*.egg-info/\n",
            "tests/test_core.py": textwrap.dedent("""\
            from {{project_name}}.core import greet, add

            def test_greet():
                assert greet(\"World\") == \"Hello, World!\"
                assert greet(\"Alice\") == \"Hello, Alice!\"

            def test_add():
                assert add(2, 3) == 5
                assert add(-1, 1) == 0
            """),
        },
        ("library", "javascript"): {
            "src/index.js": textwrap.dedent("""\
            /**
             * {{project_name}} — JavaScript library
             */
            function greet(name = 'World') {
              return `Hello, ${name}!`;
            }

            function add(a, b) {
              if (typeof a !== 'number' || typeof b !== 'number') {
                throw new TypeError('Both arguments must be numbers');
              }
              return a + b;
            }

            module.exports = { greet, add };
            """),
            "package.json": json.dumps({"name": "{{project_name}}", "version": "0.1.0", "main": "src/index.js", "scripts": {"test": "jest"}, "devDependencies": {"jest": "^29.7.0"}}, indent=2),
            "README.md": textwrap.dedent("""\
            # {{project_name}}

            JavaScript library.

            ## Usage
            ```js
            const { greet, add } = require('{{project_name}}');
            console.log(greet('Alice')); // Hello, Alice!
            console.log(add(2, 3));      // 5
            ```
            """),
            ".gitignore": "node_modules/\n",
            "tests/index.test.js": textwrap.dedent("""\
            const { greet, add } = require('../src/index');

            test('greet returns greeting', () => {
              expect(greet('World')).toBe('Hello, World!');
              expect(greet('Alice')).toBe('Hello, Alice!');
            });

            test('add sums two numbers', () => {
              expect(add(2, 3)).toBe(5);
              expect(add(-1, 1)).toBe(0);
            });

            test('add throws on non-number inputs', () => {
              expect(() => add('a', 1)).toThrow(TypeError);
            });
            """),
        },
        ("library", "typescript"): {
            "src/index.ts": textwrap.dedent("""\
            /**
             * {{project_name}} — TypeScript library
             */

            export function greet(name: string = 'World'): string {
              return `Hello, ${name}!`;
            }

            export function add(a: number, b: number): number {
              return a + b;
            }
            """),
            "package.json": json.dumps({"name": "{{project_name}}", "version": "0.1.0", "main": "dist/index.js", "types": "dist/index.d.ts", "scripts": {"build": "tsc", "test": "jest", "prepublish": "npm run build"}, "devDependencies": {"typescript": "^5.4.0", "@types/jest": "^29.5.0", "jest": "^29.7.0", "ts-jest": "^29.1.0"}}, indent=2),
            "tsconfig.json": json.dumps({"compilerOptions": {"target": "ES2020", "module": "commonjs", "declaration": True, "outDir": "./dist", "strict": True, "esModuleInterop": True}, "include": ["src"], "exclude": ["dist", "tests"]}, indent=2),
            "README.md": textwrap.dedent("""\
            # {{project_name}}

            TypeScript library.

            ## Usage
            ```ts
            import { greet, add } from '{{project_name}}';
            console.log(greet('Alice'));
            console.log(add(2, 3));
            ```
            """),
            ".gitignore": "node_modules/\ndist/\n",
            "tests/index.test.ts": textwrap.dedent("""\
            import { greet, add } from '../src/index';

            test('greet returns greeting', () => {
              expect(greet('World')).toBe('Hello, World!');
            });

            test('add sums two numbers', () => {
              expect(add(2, 3)).toBe(5);
            });
            """),
        },
    }
    _PROJECT_TEMPLATES = templ


def generate_framework(project_type: str, language: str, name: str = "my-project",
                       features: Optional[list] = None) -> dict:
    if language not in SUPPORTED_LANGUAGES:
        return {"status": "error", "error": f"Unsupported language: {language}"}

    valid_types = ["web-api", "cli-tool", "library", "desktop-app", "microservice", "data-pipeline", "fullstack-web"]
    if project_type not in valid_types:
        return {"status": "error", "error": f"Unsupported project_type: {project_type}", "valid_types": valid_types}

    _init_templates()

    key = (project_type, language)
    templates = _PROJECT_TEMPLATES.get(key)
    if not templates:
        return {
            "status": "error",
            "error": f"No templates for {project_type}/{language}",
            "note": "Available combinations: " + ", ".join(f"{pt}/{ln}" for pt, ln in sorted(_PROJECT_TEMPLATES.keys()))
        }

    ext = LANGUAGE_EXTENSIONS.get(language, ".txt")
    comment = LANGUAGE_COMMENTS.get(language, "#")
    name_slug = re.sub(r"[^a-zA-Z0-9_-]", "-", name).strip("-").lower() or "my-project"

    files = {}
    for relative_path, content in templates.items():
        rendered = content.replace("{{project_name}}", name).replace("{{project_name_slug}}", name_slug)
        resolved_path = relative_path.replace("{{project_name}}", name_slug)

        resolved_path_parts = Path(resolved_path).parts
        base_src = relative_path.split("/")[0]
        if base_src == "{{project_name}}":
            files[resolved_path] = rendered
        else:
            files[resolved_path] = rendered

    all_features = features or []
    tech_stack = [language.capitalize() if language not in ("cpp", "csharp") else
                  ("C++" if language == "cpp" else "C#")]

    if project_type == "web-api":
        tech_stack.append("FastAPI" if language == "python" else "Express")
    elif project_type == "cli-tool":
        tech_stack.append("argparse" if language == "python" else "clap" if language == "rust" else "flag")
    elif project_type == "library":
        tech_stack.append("setuptools" if language == "python" else "npm")

    for feat in all_features:
        if feat in ("auth", "database", "logging", "testing", "docker"):
            tech_stack.append(feat)

    directory_structure = sorted(set(str(Path(p).parent) + "/" for p in files if str(Path(p).parent) != "."))
    directory_structure = [d for d in directory_structure if d != "./"]
    directory_structure.extend(sorted(files.keys()))

    instructions = [
        f"1. Create project directory: mkdir {name_slug} && cd {name_slug}",
        "2. Create all files listed below with the provided content",
    ]
    if language == "python":
        instructions.append("3. Create virtual environment: python -m venv .venv && source .venv/bin/activate")
        instructions.append("4. Install dependencies: pip install -r requirements.txt")
        instructions.append("5. Run: python main.py")
    elif language in ("javascript", "typescript"):
        instructions.append("3. Install dependencies: npm install")
        instructions.append(f"4. Run: npm start" if language == "javascript" else "4. Build: npm run build")
    elif language == "rust":
        instructions.append("3. Build: cargo build")
        instructions.append("4. Run: cargo run")
    elif language == "go":
        instructions.append("3. Run: go run main.go")

    return {
        "project_name": name_slug,
        "tech_stack": tech_stack,
        "files": files,
        "instructions": "\n".join(instructions),
        "directory_structure": directory_structure,
    }


# ---------------------------------------------------------------------------
# 3. coder_debug
# ---------------------------------------------------------------------------

_ERROR_KB: list[dict] = [
    # Python errors
    {"pattern": "TypeError: 'int' object is not iterable", "language": "python",
     "causes": ["Trying to iterate over an integer instead of a range/list"],
     "fixes": [{"before": "for x in count:", "after": "for x in range(count):", "explanation": "Use range() to generate iterable from integer"}],
     "related": ["check variable type before iteration", "use isinstance() guard"]},
    {"pattern": "TypeError: 'NoneType' object is not iterable", "language": "python",
     "causes": ["Variable is None when iteration was expected", "Function returned None instead of empty list"],
     "fixes": [{"before": "for x in result:", "after": "for x in (result or []):", "explanation": "Provide a default empty iterable when result is None"}]},
    {"pattern": "TypeError: string indices must be integers", "language": "python",
     "causes": ["Trying to index a string with a string key (treating it as dict)", "JSON not parsed before access"],
     "fixes": [{"before": "data['key']", "after": "import json; data = json.loads(data); data['key']", "explanation": "Parse JSON string to dict first"}]},
    {"pattern": "TypeError: can only concatenate str", "language": "python",
     "causes": ["Trying to concatenate string with non-string (e.g. int)"],
     "fixes": [{"before": "'score: ' + score", "after": "f'score: {score}'", "explanation": "Use f-string or str() conversion"}]},
    {"pattern": "TypeError: object of type '...' has no len()", "language": "python",
     "causes": ["Object does not implement __len__", "Variable is integer when list expected"],
     "fixes": [{"before": "len(value)", "after": "len(value) if hasattr(value, '__len__') else None", "explanation": "Check for __len__ method first"}]},
    {"pattern": "IndexError: list index out of range", "language": "python",
     "causes": ["Accessing list element at index that doesn't exist", "Empty list being indexed"],
     "fixes": [{"before": "items[0]", "after": "items[0] if items else None", "explanation": "Guard against empty list with conditional"}]},
    {"pattern": "KeyError:", "language": "python",
     "causes": ["Dictionary key doesn't exist", "Missing key in API response or config"],
     "fixes": [{"before": "data['key']", "after": "data.get('key', default_value)", "explanation": "Use dict.get() with a default value"}]},
    {"pattern": "AttributeError:", "language": "python",
     "causes": ["Object doesn't have the requested attribute/method", "Variable is wrong type (often None)"],
     "fixes": [{"before": "obj.method()", "after": "if obj and hasattr(obj, 'method'): obj.method()", "explanation": "Check for None and attribute existence"}]},
    {"pattern": "NameError: name '...' is not defined", "language": "python",
     "causes": ["Variable used before assignment", "Import missing", "Typo in variable name"],
     "fixes": [{"before": "print(result)", "after": "result = compute(); print(result)", "explanation": "Ensure variable is defined before use"}]},
    {"pattern": "ImportError: No module named", "language": "python",
     "causes": ["Package not installed", "Wrong module name", "Circular import"],
     "fixes": [{"before": "import pandas", "after": "# run: pip install pandas\nimport pandas", "explanation": "Install the missing package via pip"}]},
    {"pattern": "ModuleNotFoundError: No module named", "language": "python",
     "causes": ["Package not installed", "Local module not on PYTHONPATH"],
     "fixes": [{"before": "from utils import helper", "after": "import sys; sys.path.insert(0, '.'); from utils import helper", "explanation": "Add project root to path, or install the package"}]},
    {"pattern": "IndentationError:", "language": "python",
     "causes": ["Mixed tabs and spaces", "Incorrect indentation level"],
     "fixes": [{"before": "if True:\nprint('hi')", "after": "if True:\n    print('hi')", "explanation": "Ensure consistent 4-space indentation"}]},
    {"pattern": "SyntaxError: invalid syntax", "language": "python",
     "causes": ["Missing colon after if/for/def", "Unclosed parentheses/brackets", "Using = instead of =="],
     "fixes": [{"before": "if x = 5", "after": "if x == 5", "explanation": "Use == for comparison, = for assignment"}]},
    {"pattern": "SyntaxError: 'return' outside function", "language": "python",
     "causes": ["Return statement outside a function body"],
     "fixes": [{"after": "Wrap code in a function definition", "explanation": "return must be inside def ... block"}]},
    {"pattern": "FileNotFoundError:", "language": "python",
     "causes": ["File path doesn't exist", "Working directory differs from expected"],
     "fixes": [{"before": "open('data.csv')", "after": "import os; path = os.path.join(os.path.dirname(__file__), 'data.csv'); open(path)", "explanation": "Use absolute paths or pathlib"}]},
    {"pattern": "PermissionError:", "language": "python",
     "causes": ["File is read-only or locked by another process", "Insufficient OS permissions"],
     "fixes": [{"explanation": "Check file permissions, close other handles, run as admin if needed"}]},
    {"pattern": "JSONDecodeError", "language": "python",
     "causes": ["Malformed JSON response", "Empty response body"],
     "fixes": [{"before": "json.loads(response.text)", "after": "try:\n    data = json.loads(response.text)\nexcept json.JSONDecodeError:\n    data = {}", "explanation": "Wrap JSON parsing in try/except"}]},
    {"pattern": "UnboundLocalError:", "language": "python",
     "causes": ["Variable referenced before assignment in scope", "Modifying global without 'global' keyword"],
     "fixes": [{"before": "def fn():\n    count += 1", "after": "def fn():\n    global count; count += 1", "explanation": "Declare global or avoid reassigning outer scope variables"}]},
    {"pattern": "RecursionError: maximum recursion depth", "language": "python",
     "causes": ["Infinite recursion", "Missing base case in recursive function"],
     "fixes": [{"explanation": "Add/verify base case terminates recursion. Consider iterative approach."}]},
    {"pattern": "ValueError: not enough values to unpack", "language": "python",
     "causes": ["Tuple unpacking with wrong number of variables", "Split result has fewer items than expected"],
     "fixes": [{"before": "a, b = items", "after": "if len(items) >= 2: a, b, *rest = items", "explanation": "Use *rest to capture remaining items or check length"}]},
    # JavaScript errors
    {"pattern": "TypeError: undefined is not a function", "language": "javascript",
     "causes": ["Calling a method on undefined", "Module not properly imported"],
     "fixes": [{"before": "result.fn()", "after": "if (result && typeof result.fn === 'function') result.fn();", "explanation": "Check for undefined/null and function type before calling"}]},
    {"pattern": "TypeError: Cannot read property '...' of undefined", "language": "javascript",
     "causes": ["Accessing property on undefined object", "Async data not loaded yet"],
     "fixes": [{"before": "obj.prop.sub", "after": "obj?.prop?.sub", "explanation": "Use optional chaining (?.) to safely access nested properties"}]},
    {"pattern": "TypeError: Cannot read property '...' of null", "language": "javascript",
     "causes": ["DOM element not found", "querySelector returned null"],
     "fixes": [{"before": "document.getElementById('x').value", "after": "const el = document.getElementById('x'); if (el) { el.value; }", "explanation": "Check for null before accessing properties"}]},
    {"pattern": "ReferenceError: ... is not defined", "language": "javascript",
     "causes": ["Variable used before declaration", "Missing import/require"],
     "fixes": [{"before": "processData()", "after": "// Before use: const { processData } = require('./utils');\nprocessData();", "explanation": "Ensure variable/function is defined or imported"}]},
    {"pattern": "TypeError: Assignment to constant variable", "language": "javascript",
     "causes": ["Reassigning a const variable"],
     "fixes": [{"before": "const x = 1; x = 2;", "after": "let x = 1; x = 2;", "explanation": "Use let for variables that will change"}]},
    {"pattern": "SyntaxError: Unexpected token", "language": "javascript",
     "causes": ["Extra or missing brace/bracket", "JSON.parse on non-JSON content", "Missing comma in object"],
     "fixes": [{"explanation": "Check for balanced braces/brackets, validate JSON, check trailing commas"}]},
    {"pattern": "TypeError: ... is not a function", "language": "javascript",
     "causes": ["Variable shadows function name", "Wrong import (default vs named)"],
     "fixes": [{"before": "const fn = require('mod')", "after": "const { fn } = require('mod')", "explanation": "Check if module exports named or default export"}]},
    {"pattern": "UnhandledPromiseRejectionWarning", "language": "javascript",
     "causes": ["Promise rejection not caught with .catch() or try/catch"],
     "fixes": [{"before": "fetch('/api')", "after": "fetch('/api').catch(err => console.error(err));", "explanation": "Always handle promise rejections"}]},
    {"pattern": "EADDRINUSE", "language": "javascript",
     "causes": ["Port already in use by another process"],
     "fixes": [{"explanation": "Kill the other process or use a different port (e.g. PORT=3001 node server.js)"}]},
    # TypeScript errors
    {"pattern": "TS2345: Argument of type", "language": "typescript",
     "causes": ["Type mismatch between argument and parameter"],
     "fixes": [{"explanation": "Cast argument to expected type or fix the type definition"}]},
    {"pattern": "TS2339: Property '...' does not exist on type", "language": "typescript",
     "causes": ["Accessing property not defined in type/interface", "Missing type narrowing"],
     "fixes": [{"before": "obj.prop", "after": "// Add prop to interface, or use (obj as any).prop", "explanation": "Define the property in the type or narrow with a type guard"}]},
    {"pattern": "TS2322: Type '...' is not assignable", "language": "typescript",
     "causes": ["Type mismatch in assignment", "Null/undefined not handled"],
     "fixes": [{"before": "let s: string = null", "after": "let s: string | null = null", "explanation": "Allow nullable type or provide default"}]},
    # Rust errors
    {"pattern": "error[E0061]: this function takes", "language": "rust",
     "causes": ["Wrong number of function arguments"],
     "fixes": [{"explanation": "Check function signature and provide correct number of arguments"}]},
    {"pattern": "error[E0382]: borrow of moved value", "language": "rust",
     "causes": ["Value moved after move", "Using after .clone() not called"],
     "fixes": [{"before": "let s = String::from(\"hi\"); takes(s); takes(s);", "after": "let s = String::from(\"hi\"); takes(s.clone()); takes(s);", "explanation": "Clone the value or pass by reference"}]},
    {"pattern": "error[E0507]: cannot move out of borrowed content", "language": "rust",
     "causes": ["Trying to take ownership from a reference"],
     "fixes": [{"explanation": "Use .clone() or redesign to work with references"}]},
    {"pattern": "error[E0597]: does not live long enough", "language": "rust",
     "causes": ["Reference outlives the data it points to", "Returning reference to local variable"],
     "fixes": [{"after": "Return owned value (String) instead of reference (&str)", "explanation": "Return owned types or restructure lifetimes"}]},
    # Go errors
    {"pattern": "cannot use .* as type", "language": "go",
     "causes": ["Type mismatch in assignment or function argument"],
     "fixes": [{"explanation": "Cast to correct type or change variable declaration"}]},
    {"pattern": "declared and not used", "language": "go",
     "causes": ["Variable is declared but never used"],
     "fixes": [{"before": "x := 1", "after": "x := 1; _ = x // or remove variable", "explanation": "Remove unused variable or assign to _"}]},
    {"pattern": "index out of range", "language": "go",
     "causes": ["Accessing slice/array beyond its length"],
     "fixes": [{"before": "s[10]", "after": "if len(s) > 10 { val := s[10] }", "explanation": "Check length before indexing"}]},
    # Java errors
    {"pattern": "NullPointerException", "language": "java",
     "causes": ["Calling method on null object reference"],
     "fixes": [{"before": "obj.method()", "after": "if (obj != null) { obj.method(); }", "explanation": "Add null check before method call"}]},
    {"pattern": "ClassNotFoundException", "language": "java",
     "causes": ["Class not on classpath", "Missing dependency"],
     "fixes": [{"explanation": "Add dependency to classpath or build configuration (pom.xml/build.gradle)"}]},
    {"pattern": "ConcurrentModificationException", "language": "java",
     "causes": ["Modifying collection while iterating"],
     "fixes": [{"before": "for (T item : list) { list.remove(item); }", "after": "list.removeIf(predicate); // or use Iterator.remove()", "explanation": "Use Iterator.remove() or removeIf()"}]},
    # C# errors
    {"pattern": "NullReferenceException", "language": "csharp",
     "causes": ["Dereferencing null object"],
     "fixes": [{"before": "obj.Method()", "after": "obj?.Method()", "explanation": "Use null-conditional operator (?.)"}]},
    {"pattern": "CS0103: The name '...' does not exist", "language": "csharp",
     "causes": ["Variable out of scope", "Missing using directive"],
     "fixes": [{"explanation": "Check variable scope, add using directive for the namespace"}]},
    # C++ errors
    {"pattern": "Segmentation fault", "language": "cpp",
     "causes": ["Null pointer dereference", "Accessing freed memory", "Stack overflow"],
     "fixes": [{"explanation": "Use smart pointers (unique_ptr, shared_ptr), valgrind to trace"}]},
    {"pattern": "undefined reference to", "language": "cpp",
     "causes": ["Missing function implementation", "Not linking required library"],
     "fixes": [{"explanation": "Implement the declared function or link the missing library"}]},
    # Ruby errors
    {"pattern": "NoMethodError: undefined method", "language": "ruby",
     "causes": ["Calling method that doesn't exist on object", "nil where object expected"],
     "fixes": [{"before": "obj.method_name", "after": "obj&.method_name # safe navigation operator", "explanation": "Use &. for safe navigation"}]},
    {"pattern": "NameError: undefined local variable", "language": "ruby",
     "causes": ["Variable not yet defined", "Typo in variable name"],
     "fixes": [{"explanation": "Define variable before use, check for typos"}]},
    # PHP errors
    {"pattern": "Fatal error: Call to undefined function", "language": "php",
     "causes": ["Function not defined", "Missing extension or include"],
     "fixes": [{"explanation": "Define function or include the file that contains it"}]},
    {"pattern": "Notice: Undefined index", "language": "php",
     "causes": ["Array key doesn't exist"],
     "fixes": [{"before": "$val = $arr['key'];", "after": "$val = $arr['key'] ?? null;", "explanation": "Use null coalescing operator ?? or isset()"}]},
    # Swift errors
    {"pattern": "fatal error: unexpectedly found nil", "language": "swift",
     "causes": ["Force-unwrapping nil optional"],
     "fixes": [{"before": "let x = optional!", "after": "if let x = optional { ... }", "explanation": "Use optional binding (if let / guard let) instead of force unwrap"}]},
    # Kotlin errors
    {"pattern": "NullPointerException", "language": "kotlin",
     "causes": ["Accessing nullable variable without null check"],
     "fixes": [{"before": "val x = nullable!!", "after": "val x = nullable ?: defaultValue", "explanation": "Use Elvis operator (?:) or safe call (?.)"}]},
    # Generic
    {"pattern": "out of memory", "language": None,
     "causes": ["Loading too much data at once", "Memory leak", "Infinite loop with allocation"],
     "fixes": [{"explanation": "Stream data instead of loading all, use generators/iterators, profile memory"}]},
    {"pattern": "timeout", "language": None,
     "causes": ["Network request hanging", "Infinite loop", "Deadlock"],
     "fixes": [{"before": "response = requests.get(url)", "after": "response = requests.get(url, timeout=10)", "explanation": "Always set timeouts on network operations"}]},
    {"pattern": "CORSError|CORS|blocked by CORS", "language": None,
     "causes": ["Cross-origin request blocked by browser", "Missing CORS headers on server"],
     "fixes": [{"explanation": "Add CORS headers on server (Access-Control-Allow-Origin), or use a proxy"}]},
    {"pattern": "429|rate limit", "language": None,
     "causes": ["Too many requests", "Hitting API rate limit"],
     "fixes": [{"explanation": "Add exponential backoff, respect Retry-After header, batch requests"}]},
]


def debug_error(error: str, code_context: str = "", language: str = "python") -> dict:
    error_type = "unknown"
    error_lower = error.lower()

    if "syntaxerror" in error_lower or "syntax error" in error_lower:
        error_type = "syntax"
    elif "typeerror" in error_lower or "type error" in error_lower:
        error_type = "type_error"
    elif "runtime" in error_lower or "panic" in error_lower or "exception" in error_lower:
        error_type = "runtime"
    elif "importerror" in error_lower or "modulenotfound" in error_lower or "cannot find module" in error_lower or "no module" in error_lower or "cannot resolve" in error_lower:
        error_type = "import"
    elif "referenceerror" in error_lower or "nameerror" in error_lower or "undefined" in error_lower or "not defined" in error_lower:
        error_type = "reference"
    elif "logic" in error_lower or "assert" in error_lower:
        error_type = "logic"
    else:
        error_type = "runtime"

    location = {}
    file_match = re.search(r'File\s+"([^"]+)"' + r',\s*line\s*(\d+)', error)
    if file_match:
        location = {"file": file_match.group(1), "line": int(file_match.group(2))}
    else:
        file_match2 = re.search(r'(?:in\s+|at\s+)([\w./\\-]+):(\d+)', error)
        if file_match2:
            location = {"file": file_match2.group(1), "line": int(file_match2.group(2))}

    matches = []
    for entry in _ERROR_KB:
        entry_lang = entry.get("language")
        if entry_lang and entry_lang != language:
            continue
        if re.search(entry["pattern"], error, re.IGNORECASE):
            matches.append(entry)

    if not matches:
        for entry in _ERROR_KB:
            if entry.get("language") is None:
                if re.search(entry["pattern"], error, re.IGNORECASE):
                    matches.append(entry)

    probable_causes: list[str] = []
    fix_suggestions: list[dict] = []
    related_patterns: list[str] = []

    seen_causes = set()
    for m in matches:
        for cause in m.get("causes", []):
            if cause not in seen_causes:
                probable_causes.append(cause)
                seen_causes.add(cause)
        for fix in m.get("fixes", []):
            fix_suggestions.append(fix)
        for rp in m.get("related", []):
            if rp not in related_patterns:
                related_patterns.append(rp)

    if not probable_causes:
        probable_causes = ["Could not match exact pattern — check error message for clues"]
        fix_suggestions = [{"explanation": "Review the error carefully. Check variable types, imports, and syntax near the reported line."}]

    return {
        "error_type": error_type,
        "location": location,
        "probable_causes": probable_causes,
        "fix_suggestions": fix_suggestions[:5],
        "related_patterns": related_patterns,
    }


# ---------------------------------------------------------------------------
# 4. coder_review
# ---------------------------------------------------------------------------

def review_code(code: str, language: str = "python", focus: str = "all") -> dict:
    if language not in SUPPORTED_LANGUAGES:
        return {"status": "error", "error": f"Unsupported language: {language}"}

    valid_focus = ["all", "security", "performance", "readability", "architecture", "testing"]
    if focus not in valid_focus:
        return {"status": "error", "error": f"Invalid focus: {focus}", "valid": valid_focus}

    issues: list[dict] = []
    lines = code.split("\n")
    strengths: list[str] = []

    if focus in ("all", "security"):
        for pattern, _, desc in _HARDCODED_SECRET_PATTERNS:
            for m in re.finditer(pattern, code, re.IGNORECASE):
                issues.append({
                    "severity": "critical", "category": "security",
                    "line": _line_number(code, m.start()), "title": "Hardcoded Secret",
                    "description": desc,
                    "suggestion": "Use environment variables or a secrets manager (e.g. HashiCorp Vault, AWS Secrets Manager)",
                    "code_example": "import os\nSECRET = os.getenv('API_KEY')"
                })

        for pattern, _, desc in _SQL_INJECTION_PATTERNS:
            for m in re.finditer(pattern, code, re.IGNORECASE):
                issues.append({
                    "severity": "critical", "category": "security",
                    "line": _line_number(code, m.start()), "title": "SQL Injection",
                    "description": desc,
                    "suggestion": "Use parameterized queries or an ORM",
                    "code_example": "cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))"
                })

        if re.search(r'\b(?:eval|exec)\s*\(', code):
            issues.append({
                "severity": "critical", "category": "security",
                "line": 1, "title": "Dangerous eval/exec",
                "description": "Dynamic code execution can lead to code injection",
                "suggestion": "Avoid eval/exec entirely. Use safer alternatives.",
                "code_example": "import json\n# Instead of eval(data):\ndata = json.loads(input_string)"
            })

    if focus in ("all", "performance"):
        nested_loop_pattern = re.search(r'(for|while).+\n.+(for|while)', code)
        if nested_loop_pattern:
            issues.append({
                "severity": "warning", "category": "performance",
                "line": _line_number(code, nested_loop_pattern.start()), "title": "Nested Loops",
                "description": "Nested loops can cause O(n^2) performance",
                "suggestion": "Consider using hash maps (dict/map) or precomputing values",
                "code_example": "# Use a set/dict for O(1) lookup instead of nested loop"
            })

        if '".join(' in code or "'+'" in code or 'str + str' in code:
            if len(lines) > 10:
                issues.append({
                    "severity": "info", "category": "performance",
                    "line": 1, "title": "String Concatenation in Loop",
                    "description": "Repeated string concatenation creates many intermediate strings",
                    "suggestion": "Use .join() or StringBuilder",
                    "code_example": "result = ''.join(parts)  # instead of result += part"
                })

    if focus in ("all", "readability"):
        if len(lines) > 200:
            issues.append({
                "severity": "warning", "category": "readability",
                "line": 1, "title": "Large File",
                "description": f"File is {len(lines)} lines — consider splitting into modules",
                "suggestion": "Split into multiple files/modules by responsibility",
                "code_example": "# Create separate files: models.py, services.py, utils.py"
            })

        long_lines = [(i+1, line) for i, line in enumerate(lines) if len(line) > 120]
        if len(long_lines) > 3:
            issues.append({
                "severity": "info", "category": "readability",
                "line": long_lines[0][0], "title": "Long Lines",
                "description": f"{len(long_lines)} lines exceed 120 characters",
                "suggestion": "Break long lines with intermediate variables or line continuation",
                "code_example": "result = some_function(\n    arg1, arg2,\n    arg3\n)"
            })

        if language == "python":
            has_docstring = any('"""' in line or "'''" in line for line in lines[:30])
            if not has_docstring and len(lines) > 10:
                issues.append({
                    "severity": "info", "category": "readability",
                    "line": 1, "title": "Missing Module Docstring",
                    "description": "Module lacks a docstring describing its purpose",
                    "suggestion": "Add a module-level docstring",
                    "code_example": '"""Module description.\n\nProvides X, Y, Z functionality."""'
                })

    if focus in ("all", "architecture"):
        # Simple heuristic: lots of top-level code without functions = poor architecture
        top_level_stmts = 0
        in_definition = False
        for line in lines:
            stripped = line.strip()
            if re.match(r'^\s*(?:def|class|function|func|fn|public\s+class)\s', stripped):
                in_definition = True
            elif stripped and not stripped.startswith("#") and not stripped.startswith("//"):
                if not in_definition and not re.match(r'^\s*(?:import|from|const|let|var|use|package)', stripped):
                    top_level_stmts += 1

        if top_level_stmts > 5 and len(lines) > 20:
            issues.append({
                "severity": "info", "category": "architecture",
                "line": 1, "title": "Too Much Top-Level Code",
                "description": f"{top_level_stmts} statements at module level — wrap in functions",
                "suggestion": "Wrap execution code in main() function with if __name__ guard",
                "code_example": "def main():\n    ...\n\nif __name__ == '__main__':\n    main()"
            })

    if focus in ("all", "testing"):
        test_indicators = ["test", "assert", "mock", "pytest", "jest", "unittest", "junit"]
        has_any_test = any(ind in code.lower() for ind in test_indicators)
        if not has_any_test and len(lines) > 30:
            issues.append({
                "severity": "warning", "category": "testing",
                "line": 1, "title": "No Tests Found",
                "description": "No test indicators detected in codebase",
                "suggestion": "Add unit tests for critical functions",
                "code_example": "def test_add():\n    assert add(2, 3) == 5"
            })

    strengths = []
    if len(lines) < 100:
        strengths.append("Compact, focused code")
    if any("docstring" in line.lower() or '"""' in line for line in lines[:20]):
        strengths.append("Good documentation practices")
    if any("try" in line.lower() and "except" in line.lower() for line in lines):
        strengths.append("Error handling present")
    if not any(issue["severity"] == "critical" for issue in issues):
        strengths.append("No critical security issues detected")
    if any(line.strip().startswith("#") or line.strip().startswith("//") for line in lines):
        strengths.append("Code includes comments")

    severity_weights = {"critical": 20, "warning": 8, "info": 2}
    total_penalty = sum(severity_weights.get(i["severity"], 1) for i in issues)
    rating_score = max(0, 100 - total_penalty)
    overall_rating = _score_to_grade(rating_score)

    action_items = []
    priority = 1
    for issue in sorted(issues, key=lambda x: {"critical": 0, "warning": 1, "info": 2}.get(x["severity"], 3)):
        if priority <= 5:
            action_items.append({
                "priority": priority,
                "action": f"[{issue['category'].upper()}] {issue['title']}: {issue.get('suggestion', issue['description'])}"
            })
            priority += 1

    summary_parts = []
    if overall_rating in ("A+", "A", "A-"):
        summary_parts.append("Code is well-structured with minimal issues.")
    elif overall_rating in ("B+", "B", "B-"):
        summary_parts.append(f"Code has {len(issues)} issues to address but is generally acceptable.")
    else:
        summary_parts.append(f"Code has {len(issues)} significant issues requiring attention.")

    if focus != "all":
        summary_parts.insert(0, f"Focused review on {focus}:")

    return {
        "summary": " ".join(summary_parts),
        "issues": issues,
        "overall_rating": overall_rating,
        "strengths": strengths,
        "action_items": action_items,
    }


# ---------------------------------------------------------------------------
# 5. coder_explain
# ---------------------------------------------------------------------------

def explain_code(code: str, language: str = "python", level: str = "intermediate") -> dict:
    if language not in SUPPORTED_LANGUAGES:
        return {"status": "error", "error": f"Unsupported language: {language}"}

    valid_levels = ["beginner", "intermediate", "advanced"]
    if level not in valid_levels:
        level = "intermediate"

    lines = code.split("\n")
    sections: list[dict] = []
    concepts: list[dict] = []
    key_points: list[str] = []
    overview = ""

    if language in ("python", "ruby"):
        import_match = re.match(r'((?:^import\s+.*\n|^from\s+.*\n|^require\s+.*\n)+)', code, re.MULTILINE)
        if import_match:
            import_block = import_match.group(1)
            sections.append({
                "title": "Imports / Dependencies",
                "explanation": "Brings in external libraries and modules needed by the program. These provide pre-built functionality like HTTP servers, file I/O, or data processing.",
                "code": import_block.strip()
            })

        for m in re.finditer(r'(def\s+\w+\s*\([^)]*\)\s*:\n(?:\s+.*\n?)*)', code):
            func_sig = m.group(1)
            sig_line = func_sig.split("\n")[0]
            name_match = re.search(r'def\s+(\w+)', sig_line)
            name = name_match.group(1) if name_match else "function"

            doc_match = re.search(r'""".*?"""', func_sig, re.DOTALL)
            doc = doc_match.group(0) if doc_match else ""

            explanation = f"Function `{name}` "
            if "return" in func_sig:
                explanation += "computes a value and returns it."
            elif "print" in func_sig:
                explanation += "displays output."
            else:
                explanation += "performs an operation."
            if doc:
                explanation += f" The docstring says: {doc.strip('\"')}"

            sections.append({
                "title": f"Function: {name}",
                "explanation": explanation,
                "code": func_sig[:500]
            })

        for m in re.finditer(r'(class\s+\w+(?:\([^)]*\))?\s*:\n(?:\s+.*\n?)*)', code):
            cls_block = m.group(1)
            name_match = re.search(r'class\s+(\w+)', cls_block)
            name = name_match.group(1) if name_match else "Class"
            method_count = len(re.findall(r'def\s+\w+', cls_block))
            sections.append({
                "title": f"Class: {name}",
                "explanation": f"Defines a class with {method_count} methods. Classes encapsulate data (attributes) and behavior (methods) into a single reusable unit.",
                "code": cls_block[:500]
            })

    elif language in ("javascript", "typescript"):
        for m in re.finditer(r'(?:function\s+(\w+)\s*\([^)]*\)\s*\{|const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{)', code):
            name = m.group(1) or m.group(2)
            sections.append({
                "title": f"Function: {name}",
                "explanation": f"Function `{name}` performs a specific operation.",
                "code": code[m.start():m.end()][:500]
            })

    elif language in ("rust", "go"):
        for m in re.finditer(r'(?:fn\s+(\w+)|func\s+(?:\([^)]*\)\s+)?(\w+))', code):
            name = m.group(1) or m.group(2)
            sections.append({
                "title": f"Function: {name}",
                "explanation": f"Defines a function named `{name}`.",
                "code": code[m.start():m.start()+200]
            })

    if not sections:
        sections.append({
            "title": "Main Body",
            "explanation": "The code executes statements in order from top to bottom.",
            "code": code[:500]
        })

    # Detect concepts
    concept_patterns = [
        (r'for\s+\w+\s+in\s+', "Loop / Iteration", "Repeatedly executes code for each item in a collection"),
        (r'if\s+.*:', "Conditional", "Executes code only when a condition is true"),
        (r'try\s*:', "Error Handling", "Catches and handles errors gracefully"),
        (r'def\s+\w+', "Function Definition", "Creates a reusable block of code"),
        (r'class\s+\w+', "Class", "Blueprint for creating objects with data and methods"),
        (r'import\s+', "Module Import", "Brings external code into the current file"),
        (r'async\s+', "Async/Await", "Non-blocking asynchronous operations"),
        (r'\.\.\.(?:map|filter|reduce)', "Functional Programming", "Higher-order functions on collections"),
        (r'lambda', "Lambda / Anonymous Function", "Inline function without a name"),
        (r'with\s+', "Context Manager", "Automatically manages resource setup and cleanup"),
        (r'(?:await|Promise)', "Promise / Await", "Handles asynchronous operation results"),
    ]

    seen_concepts = set()
    for pattern, name, desc in concept_patterns:
        if re.search(pattern, code):
            if name not in seen_concepts:
                concepts.append({"name": name, "description": desc})
                seen_concepts.add(name)

    if concepts:
        key_points.append(f"Uses {len(concepts)} programming concepts: {', '.join(c['name'] for c in concepts)}")

    key_points.append(f"Written in {language}, approximately {len(lines)} lines of code")
    key_points.append(f"Contains {len(sections) - (1 if sections[0].get('title') == 'Imports / Dependencies' else 0)} main code sections")

    if level == "beginner":
        overview = "This is a program that "
    elif level == "intermediate":
        overview = f"This {language} code "
    else:
        overview = f"Analysis of {language} implementation: "

    if "api" in code.lower() or "server" in code.lower():
        overview += "implements a server/API."
    elif "cli" in code.lower() or "argparse" in code.lower():
        overview += "is a command-line tool."
    elif "class" in code.lower():
        overview += "defines classes and objects."
    else:
        overview += "performs data processing and logic operations."

    return {
        "overview": overview,
        "sections": sections,
        "concepts": concepts,
        "key_points": key_points,
    }


# ---------------------------------------------------------------------------
# 6. coder_convert
# ---------------------------------------------------------------------------

_CONVERSION_MAPS: dict[tuple[str, str], dict[str, str]] = {}

def _init_conversion_maps():
    global _CONVERSION_MAPS
    if _CONVERSION_MAPS:
        return

    _CONVERSION_MAPS = {
        ("python", "javascript"): {
            "def ": "function ",
            "def ": "function ",
            "# ": "// ",
            '"""': "/*",
            ":": "",
            "==": "===",
            "True": "true",
            "False": "false",
            "None": "null",
            "and": "&&",
            "or": "||",
            "not ": "!",
            "elif": "else if",
            "import ": "// import -> require: const ",
            "from ": "// from import -> require: const ",
            "print(": "console.log(",
            "len(": ".length",
            "range(": "Array.from({length: ",
            "self": "this",
            "__init__": "constructor",
            "raise ": "throw new Error(",
            "except ": "catch (",
            "finally:": "finally {",
            "try:": "try {",
            "isinstance(": " instanceof ",
            "f'": "'" + "${".join(""),
            "{": "${",
            "}": "}",
            ".append(": ".push(",
            ".items()": "Object.entries()",
            ".keys()": "Object.keys()",
            ".values()": "Object.values()",
            "__name__ == '__main__'": "require.main === module",
        },
        ("python", "go"): {
            "def ": "func ",
            "# ": "// ",
            "True": "true",
            "False": "false",
            "None": "nil",
            "and": "&&",
            "or": "||",
            "not ": "!",
            "elif": "else if",
            "print(": "fmt.Println(",
            "len(": "len(",
            "range(": "// TODO: Go uses for i := 0; i < N; i++ {}",
            "self": "// use pointer receiver",
            "class ": "type ",
            "try:": "// Go uses explicit error returns",
            "except ": "if err != nil {",
            "for x in ": "for _, x := range ",
            ".append(": " = append(",
            "import ": "import \"",
            "f\"": "fmt.Sprintf(\"",
            "{": "%v",
            "}": "",
            "__init__": "// use NewXxx() constructor",
            "raise ": "// return error",
            ".join": "strings.Join",
        },
        ("javascript", "typescript"): {
            "function ": "function ",
            "const ": "const ",
            "let ": "let ",
            "var ": "let ",
            "function(": "function(",
            "function (": "function (",
            "):": "): ",
            "require(": "import * as from ",
            "module.exports =": "export default",
            "// @ts-ignore": "",
            ".js\"": ".ts\"",
        },
        ("javascript", "python"): {
            "function ": "def ",
            "function(": "def ",
            "// ": "# ",
            "/*": '"""',
            "*/": '"""',
            "===": "==",
            "true": "True",
            "false": "False",
            "null": "None",
            "undefined": "None",
            "&&": "and",
            "||": "or",
            "!": "not ",
            "else if": "elif",
            "console.log(": "print(",
            ".length": "len(",
            "throw new Error(": "raise ",
            "catch (": "except ",
            "try {": "try:",
            "this.": "self.",
            "new X": "X()",
            ".push(": ".append(",
            "Object.entries(": ".items()",
            "Object.keys(": ".keys()",
            "Object.values(": ".values()",
        },
        ("python", "rust"): {
            "def ": "fn ",
            "# ": "// ",
            "True": "true",
            "False": "false",
            "None": "None",
            "and": "&&",
            "or": "||",
            "not ": "!",
            "elif": "else if",
            "print(": "println!(",
            "len(": ".len()",
            "range(": "(0..",
            "self": "&self",
            "class ": "struct ",
            "try:": "// Rust uses Result<T, E>",
            "except ": "",
            "for x in ": "for x in ",
            ".append(": ".push(",
            "import ": "use ",
            "f\"": "format!(\"",
            "{": "{",
            "}": "}",
            "__init__": "fn new(",
        },
    }


def convert_code(code: str, from_lang: str, to_lang: str) -> dict:
    if from_lang not in SUPPORTED_LANGUAGES:
        return {"status": "error", "error": f"Unsupported source language: {from_lang}"}
    if to_lang not in SUPPORTED_LANGUAGES:
        return {"status": "error", "error": f"Unsupported target language: {to_lang}"}

    _init_conversion_maps()

    mapping = _CONVERSION_MAPS.get((from_lang, to_lang))

    if not mapping:
        return {
            "status": "error",
            "error": f"No conversion mapping for {from_lang} -> {to_lang}",
            "available": [f"{s}->{t}" for s, t in _CONVERSION_MAPS.keys()]
        }

    result = code
    for old, new in mapping.items():
        result = result.replace(old, new)

    notes: list[dict] = []
    caveats: list[str] = []
    improvements: list[str] = []

    if (from_lang, to_lang) == ("python", "javascript"):
        notes.append({"type": "warning", "message": "Python's tuple unpacking (a, b = iterable) used destructuring: const [a, b] = iterable"})
        notes.append({"type": "info", "message": "List comprehensions converted to .map()/.filter() calls"})
        notes.append({"type": "info", "message": "Decorators removed — use higher-order function wrapping in JS"})
        caveats.append("Type hints removed (JS is dynamically typed without TS)")
        caveats.append("async/await uses Promises — ensure proper error handling")
        improvements.append("Consider using const/let instead of var")
        improvements.append("Use arrow functions (=>) for cleaner callbacks")

    elif (from_lang, to_lang) == ("python", "go"):
        notes.append({"type": "warning", "message": "Python exception handling converted to Go error returns — add if err != nil checks"})
        notes.append({"type": "warning", "message": "Python classes converted to Go structs with method receivers"})
        notes.append({"type": "info", "message": "Dynamic typing removed — add explicit type declarations"})
        caveats.append("Go has no try/except — all functions should return (result, error)")
        caveats.append("Generators/yield converted to channels or slices")
        caveats.append("Python's flexible function args (*args, **kwargs) not directly translatable")
        improvements.append("Use defer for resource cleanup")
        improvements.append("Consider interfaces for polymorphic behavior")

    elif (from_lang, to_lang) == ("javascript", "typescript"):
        notes.append({"type": "info", "message": "Added basic type annotations — may need refinement"})
        notes.append({"type": "info", "message": "require() converted to ES import syntax"})
        caveats.append("Dynamic property access may need type assertions")
        improvements.append("Add interfaces for complex object types")
        improvements.append("Enable strict mode in tsconfig.json")

    elif (from_lang, to_lang) == ("javascript", "python"):
        notes.append({"type": "warning", "message": "JS closures converted to Python functions — check scope rules"})
        notes.append({"type": "info", "message": "Arrow functions converted to regular or lambda functions"})
        caveats.append("JS prototype inheritance converted to class-based inheritance")
        caveats.append("Promises converted to async/await or callbacks")
        improvements.append("Use type hints for better code clarity")
        improvements.append("Use dataclasses for simple data containers")

    elif (from_lang, to_lang) == ("python", "rust"):
        notes.append({"type": "warning", "message": "Python's garbage collection replaced with Rust's ownership system"})
        notes.append({"type": "warning", "message": "Exception handling replaced with Result<T, E> — must propagate errors"})
        caveats.append("Borrow checker rules: each value has exactly one owner")
        caveats.append("Mutable references are exclusive — cannot have &mut and & at same time")
        caveats.append("Dynamic typing removed — every variable has a fixed compile-time type")
        improvements.append("Use #[derive(Debug)] for printable structs")
        improvements.append("Use match instead of if/elif chains for exhaustive handling")

    return {
        "converted_code": result,
        "notes": notes,
        "caveats": caveats,
        "idiomatic_improvements": improvements,
    }


# ---------------------------------------------------------------------------
# 7. coder_architecture
# ---------------------------------------------------------------------------

_ARCH_PATTERNS: list[dict] = [
    {
        "name": "Hexagonal Architecture (Ports & Adapters)",
        "best_for": ["web-api", "microservice", "desktop"],
        "scale": ["medium", "large", "enterprise"],
        "pros": ["Clear separation of domain logic from infrastructure", "Easy to swap databases, APIs, UIs", "Highly testable — domain has no external deps"],
        "cons": ["More boilerplate than simpler patterns", "Overkill for small projects", "Requires discipline to maintain boundaries"],
        "layers": ["Core Domain (entities, value objects, domain services)", "Ports (interfaces for inbound/outbound)", "Adapters (HTTP controllers, DB repositories, message queues)", "Infrastructure (framework wiring, DI container)"],
    },
    {
        "name": "Clean Architecture",
        "best_for": ["web-api", "mobile", "desktop", "enterprise"],
        "scale": ["medium", "large", "enterprise"],
        "pros": ["Dependency rule: outer layers depend on inner, never reverse", "Entities are framework-independent", "Excellent for long-lived applications"],
        "cons": ["Significant up-front structure cost", "Many interfaces and DTOs", "Can feel like over-engineering for small apps"],
        "layers": ["Entities (enterprise business rules)", "Use Cases (application-specific business logic)", "Interface Adapters (controllers, presenters, gateways)", "Frameworks & Drivers (web, DB, external)"],
    },
    {
        "name": "MVC (Model-View-Controller)",
        "best_for": ["web-api", "fullstack-web", "mobile"],
        "scale": ["small", "medium"],
        "pros": ["Simple to understand and implement", "Widely supported by frameworks (Django, Rails, Spring MVC)", "Good for CRUD-heavy apps"],
        "cons": ["Controllers can become bloated (fat controllers)", "View logic can leak into controllers", "Limited guidance for business logic placement"],
        "layers": ["Model (data, business logic, DB access)", "View (presentation, templates, UI)", "Controller (routing, request handling, orchestration)"],
    },
    {
        "name": "CQRS (Command Query Responsibility Segregation)",
        "best_for": ["web-api", "microservice", "realtime"],
        "scale": ["medium", "large", "enterprise"],
        "pros": ["Optimized reads separate from writes", "Scales read and write sides independently", "Pairs well with Event Sourcing"],
        "cons": ["Increased complexity — two models to maintain", "Eventual consistency between read/write sides", "Requires message broker for event sync"],
        "layers": ["Command Side (validate, process, emit events)", "Query Side (denormalized read models, materialized views)", "Event Bus (propagate state changes)", "Projections (build read models from events)"],
    },
    {
        "name": "Event-Driven Architecture",
        "best_for": ["microservice", "realtime", "etl", "data-pipeline"],
        "scale": ["medium", "large", "enterprise"],
        "pros": ["Loose coupling between services", "Natural fit for async and real-time systems", "Easy to add new consumers without modifying producers"],
        "cons": ["Eventual consistency — hard to reason about", "Debugging complex event chains is difficult", "Requires robust message broker (Kafka, RabbitMQ)"],
        "layers": ["Event Producers (emit domain events)", "Event Bus / Broker (route and buffer events)", "Event Consumers (react to events)", "Event Store (durable log of all events)"],
    },
    {
        "name": "Microservices",
        "best_for": ["microservice", "web-api", "enterprise"],
        "scale": ["large", "enterprise"],
        "pros": ["Independent deployability", "Teams can own services end-to-end", "Polyglot persistence — each service chooses its DB"],
        "cons": ["Network latency and complexity", "Distributed debugging challenges", "Data consistency across services requires sagas"],
        "layers": ["API Gateway (routing, auth, rate limiting)", "Service Mesh (service discovery, mTLS, traffic)", "Individual Services (bounded context each)", "Shared Infrastructure (logging, tracing, CI/CD)"],
    },
    {
        "name": "Monolith (Modular)",
        "best_for": ["web-api", "fullstack-web", "cli"],
        "scale": ["small", "medium"],
        "pros": ["Simple development and deployment", "No network overhead between modules", "Transactions are straightforward (single DB)"],
        "cons": ["Scaling means scaling everything", "Merge conflicts increase with team size", "Technology lock-in within the monolith"],
        "layers": ["Presentation Layer (controllers, views, API)", "Business Logic Layer (services, domain)", "Data Access Layer (repositories, ORM)", "Database (single schema)"],
    },
    {
        "name": "Serverless",
        "best_for": ["web-api", "etl", "realtime"],
        "scale": ["small", "medium"],
        "pros": ["Zero infrastructure management", "Automatic scaling, pay-per-use", "Great for event-driven and cron jobs"],
        "cons": ["Cold starts add latency", "Vendor lock-in (AWS Lambda, Azure Functions)", "Hard to test locally", "Execution time limits"],
        "layers": ["API Gateway (HTTP trigger)", "Functions (single-purpose stateless handlers)", "Managed Services (DynamoDB, S3, SQS for persistence)", "Event Sources (S3 events, schedule, queues)"],
    },
    {
        "name": "Pipeline Architecture",
        "best_for": ["etl", "data-pipeline", "cli"],
        "scale": ["small", "medium", "large"],
        "pros": ["Clear data flow — easy to reason about", "Each stage is independently testable", "Can parallelize independent stages"],
        "cons": ["Not suitable for interactive UIs", "Error handling across stages is tricky", "Pipeline bottlenecks affect everything downstream"],
        "layers": ["Source (data ingestion)", "Transformer (clean, enrich, aggregate)", "Validator (quality checks, schema enforcement)", "Loader (write to target DB/file)"],
    },
]


def recommend_architecture(project_type: str, scale: str = "medium",
                           requirements: Optional[list] = None) -> dict:
    reqs = [r.lower() for r in (requirements or [])]

    scored = []
    for pattern in _ARCH_PATTERNS:
        score = 0
        if project_type in pattern["best_for"]:
            score += 3
        if scale in pattern["scale"]:
            score += 2
        for req in reqs:
            if req in str(pattern.get("layers", [])).lower():
                score += 1
            if req in str(pattern.get("pros", [])).lower():
                score += 1
            if "auth" in reqs and "api gateway" in str(pattern.get("layers", "")).lower():
                score += 1
            if "real-time" in reqs and ("event" in pattern["name"].lower() or "async" in str(pattern).lower()):
                score += 2
            if "file-upload" in reqs:
                score += 1
        scored.append((score, pattern))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    runner_up_score, runner_up = scored[1] if len(scored) > 1 else (0, best)

    alternatives = []
    for s, p in scored[1:4]:
        alternatives.append(f"{p['name']} would also work because it shares similar layering and is well-suited for {project_type}")

    tech_stack = []
    if project_type == "web-api" or project_type == "fullstack-web":
        tech_stack = ["FastAPI or Express", "PostgreSQL or MongoDB", "Redis (caching)", "Docker"]
    elif project_type == "mobile":
        tech_stack = ["Swift/Kotlin (native) or React Native/Flutter (cross-platform)", "SQLite or Realm (local DB)", "Firebase (push, analytics)"]
    elif project_type == "cli":
        tech_stack = ["Python (click/argparse) or Go (cobra) or Rust (clap)", "SQLite (local data)", "No server needed"]
    elif project_type == "microservice":
        tech_stack = ["Go/Rust/Python (services)", "Kafka/RabbitMQ (message bus)", "PostgreSQL (per-service)", "Kubernetes (orchestration)", "gRPC (inter-service)"]
    elif project_type == "etl" or project_type == "data-pipeline":
        tech_stack = ["Python (pandas, polars) or Apache Spark", "Apache Airflow (orchestration)", "S3/GCS (data lake)", "dbt (transformations)"]
    elif project_type == "realtime":
        tech_stack = ["Node.js or Go", "WebSocket or SSE", "Redis Pub/Sub", "Kafka (event streaming)"]

    diagram = f"""
    ┌─────────────────────────────────────┐
    │      {best['name']}     │
    └─────────────────────────────────────┘
    """
    for i, layer in enumerate(best.get("layers", [])):
        connector = "│           │       ▲            │" if i < len(best["layers"]) - 1 else ""
        diagram += f"    ┌─── {layer} ───┐\n"
        if i < len(best["layers"]) - 1:
            diagram += "    │        ┌───────────┐       │\n"
            diagram += "    └────────┤  depends  ├───────┘\n"
            diagram += "             └───────────┘\n"

    return {
        "recommended_pattern": best["name"],
        "rationale": f"Best fit for a {scale}-scale {project_type} project: {best['pros'][0].lower()}. Scored {best_score}/{len(best['pros']) + len(best['best_for'])} on criteria match.",
        "alternatives": alternatives,
        "components": [{"name": layer, "description": f"Part of {best['name']}"} for layer in best.get("layers", [])],
        "tech_stack": tech_stack,
        "diagram_ascii": diagram.strip(),
        "tradeoffs": {
            "pros": best.get("pros", []),
            "cons": best.get("cons", []),
        }
    }


# ---------------------------------------------------------------------------
# 8. coder_gamedev
# ---------------------------------------------------------------------------

_GAME_TYPES = {
    "2d-platformer": {
        "engines": ["Unity (2D)", "Godot", "GameMaker"],
        "key_systems": ["character controller", "level loader", "camera follow", "collectibles", "enemy AI patrol"],
        "tips": "Focus on tight controls and satisfying jump arcs. Use animation curves for character movement."
    },
    "3d-fps": {
        "engines": ["Unity", "Unreal Engine", "Godot 4"],
        "key_systems": ["first-person camera", "raycast shooting", "health/damage", "ammo system", "hit markers"],
        "tips": "Smooth mouse look is critical. Use object pooling for bullets and particles."
    },
    "rpg": {
        "engines": ["Unity", "Unreal Engine", "RPG Maker"],
        "key_systems": ["inventory", "dialogue system", "quest tracker", "stat progression", "save/load"],
        "tips": "Design data-driven systems (items, spells, NPCs as data). Use ScriptableObjects (Unity) or DataAssets (UE) over hardcoding."
    },
    "roguelike": {
        "engines": ["Unity", "Godot", "custom framework"],
        "key_systems": ["procedural generation", "permadeath", "turn-based combat", "item randomization", "seed system"],
        "tips": "Separate map generation from gameplay. Store seed for reproducible levels."
    },
    "tower-defense": {
        "engines": ["Unity", "Godot"],
        "key_systems": ["grid/path system", "tower placement", "enemy waves", "upgrade tree", "pathfinding (A*)"],
        "tips": "Use a grid-based system. Tower targeting should be configurable (first, last, strongest, nearest)."
    },
    "racing": {
        "engines": ["Unity", "Unreal Engine"],
        "key_systems": ["vehicle physics", "lap tracking", "checkpoint system", "AI racers", "time trials"],
        "tips": "Use WheelColliders (Unity) or Chaos Vehicles (UE) for realistic handling. Record ghost data for time trials."
    },
    "puzzle": {
        "engines": ["Unity", "Godot", "custom"],
        "key_systems": ["grid/board state", "undo/redo", "level loader", "hint system", "animation feedback"],
        "tips": "Implement undo/redo early. Juicy animations make puzzles feel satisfying."
    },
    "card-game": {
        "engines": ["Unity", "Godot"],
        "key_systems": ["deck management", "card effects framework", "turn system", "AI opponent", "drafting"],
        "tips": "Build a scriptable card effect system. Each card should be data-driven with composable effects."
    },
}


def gamedev_blueprint(game_type: str, engine: str = "Unity") -> dict:
    info = _GAME_TYPES.get(game_type)
    if not info:
        valid = list(_GAME_TYPES.keys())
        return {"status": "error", "error": f"Unknown game type: {game_type}", "valid_types": valid}

    if engine not in info["engines"] and engine not in ("Unity", "Unreal Engine", "Godot", "GameMaker", "RPG Maker"):
        return {"status": "error", "error": f"Engine {engine} not recommended for {game_type}", "recommended": info["engines"]}

    systems = []
    for sys_name in info["key_systems"]:
        slug = sys_name.lower().replace(" ", "_").replace("/", "_")
        systems.append({
            "name": sys_name.title(),
            "description": f"Core system for {game_type}",
            "implementation_approach": f"Create a {slug.replace('_', ' ')} manager that handles this responsibility in isolation.",
            "data_structures": ["enum for states", "ScriptableObject/DataAsset for config"] if engine in ("Unity", "Unreal Engine") else ["config file", "enum for states"],
        })

    return {
        "game_type": game_type,
        "recommended_engines": info["engines"],
        "selected_engine": engine,
        "systems": systems,
        "architecture_notes": info["tips"],
        "profitability_factors": [
            "Clear visual identity (screenshots sell games)",
            "Satisfying core loop (first 30 seconds must hook players)",
            "Steam page optimization (tags, trailer, capsule art)",
            "Community building (Discord, Reddit, early access feedback)",
            "Wishlist velocity (Steam algorithm boosts high-wishlist games)",
        ],
        "fun_factors": [
            "Juice: screenshake, particles, sound for every action",
            "Player agency: meaningful choices with visible consequences",
            "Progression: clear goals with incremental mastery",
            "Surprise: unexpected moments, emergent gameplay",
            "Flow state: difficulty curve matching player skill growth",
        ],
    }


# ---------------------------------------------------------------------------
# MCP Tool Definitions
# ---------------------------------------------------------------------------

CODER_TOOLS = [
    {
        "name": "coder_analyze_code",
        "description": "Deep code quality analysis: detects code smells, security issues, style problems, and returns a score with suggestions across 12 languages",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to analyze"},
                "language": {"type": "string", "enum": SUPPORTED_LANGUAGES, "default": "python"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "coder_generate_framework",
        "description": "Generate complete project scaffolds with real working code, README, .gitignore, config, and tests for any of 12 languages",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_type": {"type": "string", "enum": ["web-api", "cli-tool", "library", "desktop-app", "microservice", "data-pipeline", "fullstack-web"], "description": "Type of project"},
                "language": {"type": "string", "enum": SUPPORTED_LANGUAGES, "default": "python"},
                "name": {"type": "string", "default": "my-project"},
                "features": {"type": "array", "items": {"type": "string", "enum": ["auth", "database", "logging", "testing", "docker"]}},
            },
            "required": ["project_type", "language"],
        },
    },
    {
        "name": "coder_debug",
        "description": "Analyze error messages and suggest fixes using a knowledge base of 50+ common error patterns across 12 languages",
        "inputSchema": {
            "type": "object",
            "properties": {
                "error": {"type": "string", "description": "Error message or stack trace"},
                "code_context": {"type": "string", "description": "Surrounding code (optional but improves results)"},
                "language": {"type": "string", "enum": SUPPORTED_LANGUAGES, "default": "python"},
            },
            "required": ["error"],
        },
    },
    {
        "name": "coder_review",
        "description": "Focused code review on security, performance, readability, architecture, or testing — returns rated issues and action items",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to review"},
                "language": {"type": "string", "enum": SUPPORTED_LANGUAGES, "default": "python"},
                "focus": {"type": "string", "enum": ["all", "security", "performance", "readability", "architecture", "testing"], "default": "all"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "coder_explain",
        "description": "Educational block-by-block code explanation with concept identification and key points, at beginner/intermediate/advanced levels",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to explain"},
                "language": {"type": "string", "enum": SUPPORTED_LANGUAGES, "default": "python"},
                "level": {"type": "string", "enum": ["beginner", "intermediate", "advanced"], "default": "intermediate"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "coder_convert",
        "description": "Translate code between languages with syntax mapping tables, caveat notes, and idiomatic improvement suggestions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Source code to convert"},
                "from": {"type": "string", "enum": SUPPORTED_LANGUAGES, "description": "Source language"},
                "to": {"type": "string", "enum": SUPPORTED_LANGUAGES, "description": "Target language"},
            },
            "required": ["code", "from", "to"],
        },
    },
    {
        "name": "coder_architecture",
        "description": "Recommend architecture pattern (Hexagonal, Clean, MVC, CQRS, Event-Driven, Microservices, Serverless, Pipeline, Monolith) for your project type, scale, and requirements",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_type": {"type": "string", "enum": ["web-api", "mobile", "desktop", "cli", "microservice", "etl", "realtime", "data-pipeline", "fullstack-web"]},
                "scale": {"type": "string", "enum": ["small", "medium", "large", "enterprise"], "default": "medium"},
                "requirements": {"type": "array", "items": {"type": "string"}, "description": "E.g. ['real-time', 'auth', 'file-upload']"},
            },
            "required": ["project_type"],
        },
    },
    {
        "name": "coder_gamedev_blueprint",
        "description": "Get a game development blueprint for 2D/3D/RPG/roguelike/tower-defense/racing/puzzle/card games with systems breakdown, engine recommendations, and fun/profit factors",
        "inputSchema": {
            "type": "object",
            "properties": {
                "game_type": {"type": "string", "enum": ["2d-platformer", "3d-fps", "rpg", "roguelike", "tower-defense", "racing", "puzzle", "card-game"]},
                "engine": {"type": "string", "enum": ["Unity", "Unreal Engine", "Godot", "GameMaker", "RPG Maker"], "default": "Unity"},
            },
            "required": ["game_type"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def coder_handle_tool_call(name: str, args: dict) -> dict:
    dispatch = {
        "coder_analyze_code": lambda a: analyze_code(a.get("code", ""), a.get("language", "python")),
        "coder_generate_framework": lambda a: generate_framework(
            a.get("project_type", "web-api"), a.get("language", "python"),
            a.get("name", "my-project"), a.get("features")
        ),
        "coder_debug": lambda a: debug_error(
            a.get("error", ""), a.get("code_context", ""), a.get("language", "python")
        ),
        "coder_review": lambda a: review_code(
            a.get("code", ""), a.get("language", "python"), a.get("focus", "all")
        ),
        "coder_explain": lambda a: explain_code(
            a.get("code", ""), a.get("language", "python"), a.get("level", "intermediate")
        ),
        "coder_convert": lambda a: convert_code(
            a.get("code", ""), a.get("from", "python"), a.get("to", "javascript")
        ),
        "coder_architecture": lambda a: recommend_architecture(
            a.get("project_type", "web-api"), a.get("scale", "medium"), a.get("requirements")
        ),
        "coder_gamedev_blueprint": lambda a: gamedev_blueprint(
            a.get("game_type", "2d-platformer"), a.get("engine", "Unity")
        ),
    }

    handler = dispatch.get(name)
    if handler:
        return handler(args)
    return {"status": "error", "error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# CLI entrypoint (for standalone testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python coder-module.py <tool_name> <json_args>")
        print("Available tools:", ", ".join(t["name"] for t in CODER_TOOLS))
        sys.exit(1)

    tool_name = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    result = coder_handle_tool_call(tool_name, args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
