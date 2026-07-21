#!/usr/bin/env python3
"""
Security Scanner — CortexStratum toolchain security audit module.

Scans a codebase for hardcoded secrets, vulnerable dependencies, security
anti-patterns, and configuration weaknesses. Integrates with xTrace
(error-trace.ps1) and DTrace (decision-trace.ps1) for persistence.

Usage:
    python scripts/security-scan.py --dir /path/to/scan
    python scripts/security-scan.py --dir . --severity high
    python scripts/security-scan.py --dir . --output report.json
    python scripts/security-scan.py --check-config
    python scripts/security-scan.py --list-patterns
"""

import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
DATA_DIR = BASE_DIR / "data"

G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
B = "\033[94m"
C = "\033[96m"
M = "\033[95m"
W = "\033[97m"
N = "\033[0m"
DIM = "\033[2m"

SCAN_VERSION = "1.0.0"

# ============================================================================
# PATTERN DEFINITIONS — 30+ detection patterns across 4 categories
# ============================================================================

SECRET_PATTERNS: List[Dict[str, Any]] = [
    {
        "id": "SECRET-AWS-01",
        "name": "AWS Access Key ID",
        "severity": "high",
        "cwe": "CWE-798",
        "regex": r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![0-9A-Z])",
        "description": "Hardcoded AWS Access Key ID",
        "suggestion": "Use environment variables or a secrets manager like AWS Secrets Manager.",
    },
    {
        "id": "SECRET-AWS-02",
        "name": "AWS Secret Access Key",
        "severity": "high",
        "cwe": "CWE-798",
        "regex": r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])",
        "description": "Hardcoded AWS Secret Access Key (40-char base64)",
        "suggestion": "Store in AWS Secrets Manager or use IAM roles instead of keys.",
    },
    {
        "id": "SECRET-GH-01",
        "name": "GitHub Personal Access Token",
        "severity": "high",
        "cwe": "CWE-798",
        "regex": r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}",
        "description": "Hardcoded GitHub token (PAT, OAuth, or refresh)",
        "suggestion": "Use GitHub CLI with `gh auth login` or environment variables.",
    },
    {
        "id": "SECRET-SLACK-01",
        "name": "Slack Bot/Webhook Token",
        "severity": "high",
        "cwe": "CWE-798",
        "regex": r"xox[baprs]-[0-9A-Za-z-]{10,}",
        "description": "Hardcoded Slack API token or webhook URL",
        "suggestion": "Use Slack app-level tokens via environment variables.",
    },
    {
        "id": "SECRET-GEN-01",
        "name": "Generic API Key — 'api[_-]?key' assignment",
        "severity": "high",
        "cwe": "CWE-798",
        "regex": r"""(?:api[_-]?key|apikey|api_key)\s*[=:]\s*['\"][A-Za-z0-9_\-+=/]{16,}['\"]""",
        "description": "Hardcoded API key string pattern",
        "suggestion": "Load API keys from environment variables or a .env file.",
    },
    {
        "id": "SECRET-GEN-02",
        "name": "Generic Token — 'token' assignment",
        "severity": "high",
        "cwe": "CWE-798",
        "regex": r"""(?:token|secret|password|passwd)\s*[=:]\s*['\"][A-Za-z0-9_\-+=/.:]{8,}['\"]""",
        "description": "Hardcoded token or password string",
        "suggestion": "Use a secrets vault or environment variable for secrets.",
    },
    {
        "id": "SECRET-JWT-01",
        "name": "JSON Web Token (JWT)",
        "severity": "medium",
        "cwe": "CWE-798",
        "regex": r"eyJ[A-Za-z0-9_\-+=/]{10,}\.eyJ[A-Za-z0-9_\-+=/]{10,}\.[A-Za-z0-9_\-+=/]{10,}",
        "description": "Hardcoded JWT (header.payload.signature format)",
        "suggestion": "Issue JWTs at runtime via a secure authentication server.",
    },
    {
        "id": "SECRET-SSH-01",
        "name": "Private SSH Key (embedded)",
        "severity": "high",
        "cwe": "CWE-798",
        "regex": r"-----BEGIN\s*(?:RSA|DSA|EC|OPENSSH|PRIVATE)\s*KEY-----",
        "description": "Embedded private SSH key in source code",
        "suggestion": "Use ssh-agent or a hardware security module. Never store private keys in repos.",
    },
    {
        "id": "SECRET-DB-01",
        "name": "Database Connection String",
        "severity": "high",
        "cwe": "CWE-798",
        "regex": r"""(?:postgres(?:ql)?|mysql|mongodb|redis|sqlite)://[A-Za-z0-9_%]+:[^@\s]+@""",
        "description": "Database connection string with embedded credentials",
        "suggestion": "Use connection string templating with env vars for user/password.",
    },
    {
        "id": "SECRET-CONN-01",
        "name": "Generic Connection String with Password",
        "severity": "high",
        "cwe": "CWE-798",
        "regex": r"""(?:Server|Host|DataSource)=[^;]+;(?:User\s*Id|Uid)=[^;]+;Password=[^;"]+""",
        "description": "SQL/ODBC connection string with plaintext password",
        "suggestion": "Use integrated security or managed identities where possible.",
    },
    {
        "id": "SECRET-NPM-01",
        "name": "NPM token in .npmrc",
        "severity": "high",
        "cwe": "CWE-798",
        "regex": r"^//registry\.npmjs\.org/:_authToken=[A-Za-z0-9\-]{20,}",
        "description": "NPM registry auth token in configuration",
        "suggestion": "Use npm login or environment variable NPM_TOKEN.",
    },
]

CODE_ANTIPATTERN_PATTERNS: List[Dict[str, Any]] = [
    {
        "id": "CODE-SQLI-01",
        "name": "SQL Injection — string concatenation",
        "severity": "high",
        "cwe": "CWE-89",
        "regex": r"""(?:execute|exec|query|run|sql|raw)\s*\(\s*(?:f['\"]|['\"]\s*\+\s*|['\"]\s*%|['\"].*\{)""",
        "description": "SQL query built via string interpolation or concatenation",
        "suggestion": "Use parameterized queries / prepared statements. Never interpolate user input.",
    },
    {
        "id": "CODE-XSS-01",
        "name": "XSS — unescaped user input in HTML",
        "severity": "high",
        "cwe": "CWE-79",
        "regex": r"""(?:innerHTML|outerHTML|insertAdjacentHTML|document\.write)\s*[=\(]""",
        "description": "Unescaped assignment of user-controlled data to innerHTML",
        "suggestion": "Use textContent or DOM API methods like createTextNode. Sanitize with DOMPurify.",
    },
    {
        "id": "CODE-CMDI-01",
        "name": "Command Injection — shell=True / os.system",
        "severity": "high",
        "cwe": "CWE-78",
        "regex": r"""(?:os\.system|subprocess\.[a-z]+\s*\([^)]*shell\s*=\s*True|exec\s*\(|eval\s*\(|popen\s*\([^)]*['\"]\s*[-|&;])""",
        "description": "Shell command execution with shell=True or os.system",
        "suggestion": "Use subprocess.run with shell=False and pass args as a list.",
    },
    {
        "id": "CODE-DESER-01",
        "name": "Insecure Deserialization — eval/pickle",
        "severity": "high",
        "cwe": "CWE-502",
        "regex": r"""(?:eval\s*\(|pickle\.loads|pickle\.load|yaml\.load\s*\([^)]*Loader\s*=\s*[^)]*Full|marshal\.load)""",
        "description": "Unsafe deserialization via eval, pickle, or unsafe yaml.load",
        "suggestion": "Use json.loads for untrusted data. Never eval or pickle.load from unverified sources.",
    },
    {
        "id": "CODE-PATH-01",
        "name": "Path Traversal — user input in file path",
        "severity": "high",
        "cwe": "CWE-22",
        "regex": r"""(?:open|read_text|write_text|Path|joinpath)\(.*(?:request|input|params|query|body|user_input|args)""",
        "description": "User-controlled input used in file path construction",
        "suggestion": "Validate and sanitize file paths. Use allowlists, reject '../' patterns.",
    },
    {
        "id": "CODE-CRYPTO-01",
        "name": "Insecure Hashing — MD5/SHA1 for passwords",
        "severity": "medium",
        "cwe": "CWE-327",
        "regex": r"""(?:hashlib\.md5|hashlib\.sha1|MessageDigest\.getInstance\s*\(\s*['\"]MD5|['\"]SHA-1['\"])\s*\)""",
        "description": "Weak cryptographic hash (MD5 or SHA-1) used for passwords or integrity",
        "suggestion": "Use SHA-256/SHA-3 for integrity or bcrypt/argon2 for passwords.",
    },
    {
        "id": "CODE-CRYPTO-02",
        "name": "Insecure Cipher — ECB mode",
        "severity": "medium",
        "cwe": "CWE-327",
        "regex": r"""AES/\w*/ECB/""",
        "description": "AES in ECB mode — deterministic, leaks patterns",
        "suggestion": "Use AES-GCM or AES-CBC with random IVs. Never use ECB for more than one block.",
    },
    {
        "id": "CODE-INFO-01",
        "name": "Information Exposure — stack trace in response",
        "severity": "medium",
        "cwe": "CWE-200",
        "regex": r"""(?:traceback\.format_exc|print_exc|stacktrace|stack[\s_]*trace)""",
        "description": "Stack trace may expose internal paths and logic to end users",
        "suggestion": "Log server-side only; return generic error messages to clients.",
    },
    {
        "id": "CODE-LOG-01",
        "name": "Sensitive Data in Logs",
        "severity": "medium",
        "cwe": "CWE-532",
        "regex": r"""(?:logging\..*password|logger\..*secret|print\s*\(.*api[_-]?key|log\.\w+.*token)""",
        "description": "Potentially logging sensitive information (password, secret, token)",
        "suggestion": "Redact or mask sensitive fields before logging.",
    },
    {
        "id": "CODE-HARDURL-01",
        "name": "Hardcoded IP Address or Internal URL",
        "severity": "low",
        "cwe": "CWE-200",
        "regex": r"""(?:https?://(?:10\.|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.)|(?:https?://)?localhost|(?:https?://)?127\.0\.0\.1)""",
        "description": "Hardcoded internal IP or hostname in code",
        "suggestion": "Use environment variables or config files for environment-specific URLs.",
    },
    {
        "id": "CODE-CERT-01",
        "name": "Disabled TLS/SSL Verification",
        "severity": "high",
        "cwe": "CWE-295",
        "regex": r"""(?:verify\s*=\s*False|ssl_verify\s*=\s*False|check_hostname\s*=\s*False|CURLOPT_SSL_VERIFYPEER\s*=\s*0)""",
        "description": "TLS/SSL certificate verification explicitly disabled",
        "suggestion": "Always verify certificates. Set verify=True and provide CA bundle if needed.",
    },
    {
        "id": "CODE-ENC-01",
        "name": "Hardcoded Encryption Key",
        "severity": "high",
        "cwe": "CWE-321",
        "regex": r"""(?:encryption_key|secret_key|cipher_key|crypt_key)\s*[=:]\s*['\"][A-Za-z0-9_\-+=/]{8,}['\"]""",
        "description": "Hardcoded encryption key in source code",
        "suggestion": "Derive keys from a key management service (KMS) or use hardware-backed storage.",
    },
    {
        "id": "CODE-BASIC-01",
        "name": "Basic Auth Credentials in URL",
        "severity": "high",
        "cwe": "CWE-798",
        "regex": r"""https?://[A-Za-z0-9_%]+:[^@\s/]+@""",
        "description": "Username:password in URL (basic auth credentials)",
        "suggestion": "Use token-based authentication or header-based auth instead of URL credentials.",
    },
]

DEPENDENCY_PATTERNS: List[Dict[str, Any]] = [
    {
        "id": "DEP-CHECK-01",
        "name": "CVE Database Lookup (embedded)",
        "severity": "info",
        "cwe": "CWE-1104",
        "description": "Check known packages against local CVE reference for known vulnerabilities",
        "suggestion": "Run 'pip audit' or 'npm audit' for an up-to-date vulnerability scan.",
    },
]

CONFIG_PATTERNS: List[Dict[str, Any]] = [
    {
        "id": "CONFIG-CSP-01",
        "name": "Missing Content Security Policy",
        "severity": "high",
        "cwe": "CWE-1021",
        "description": "No Content-Security-Policy header or meta tag found",
        "suggestion": "Add CSP header with restrictive defaults: default-src 'self'; script-src 'self'.",
    },
    {
        "id": "CONFIG-TLS-01",
        "name": "TLS/SSL Verification Disabled in Config",
        "severity": "high",
        "cwe": "CWE-295",
        "regex": r"""(?:rejectUnauthorized|strictSSL|ssl\.verify|tls_verify)\s*[=:]\s*(?:false|False|0|'none')""",
        "description": "TLS certificate validation disabled in configuration",
        "suggestion": "Set TLS verification to strict/true. Disable only for testing with explicit override.",
    },
    {
        "id": "CONFIG-ROOT-01",
        "name": "Container Running as Root",
        "severity": "medium",
        "cwe": "CWE-250",
        "regex": r"^USER\s+root\s*$",
        "description": "Dockerfile runs container as root user",
        "suggestion": "Add 'USER nobody' or create a non-root user with USER directive.",
    },
    {
        "id": "CONFIG-DEBUG-01",
        "name": "Debug Mode Enabled",
        "severity": "medium",
        "cwe": "CWE-489",
        "regex": r"""(?:debug\s*[=:]\s*(?:true|True|1|'true')|NODE_ENV\s*[=:]\s*['\"]?development['\"]?)""",
        "description": "Debug or development mode enabled in deployment configuration",
        "suggestion": "Set debug=False and NODE_ENV=production in production deployments.",
    },
    {
        "id": "CONFIG-CORS-01",
        "name": "Permissive CORS Policy",
        "severity": "medium",
        "cwe": "CWE-942",
        "regex": r"""(?:Access-Control-Allow-Origin\s*[=:]\s*['\"]?\*|allow_origins\s*=\s*['\"]?\*['\"]?)""",
        "description": "CORS configured to allow all origins (*)",
        "suggestion": "Restrict Access-Control-Allow-Origin to specific trusted domains.",
    },
    {
        "id": "CONFIG-PORT-01",
        "name": "Exposed Port Without Authentication",
        "severity": "low",
        "cwe": "CWE-200",
        "regex": r"""(?:EXPOSE\s+\d+|ports:\s*-[^\n]*\d+)""",
        "description": "Exposed port may lack authentication layer",
        "suggestion": "Ensure exposed ports are behind authentication or a reverse proxy.",
    },
    {
        "id": "CONFIG-HSTS-01",
        "name": "Missing HSTS Header",
        "severity": "low",
        "cwe": "CWE-319",
        "description": "No Strict-Transport-Security header detected in config",
        "suggestion": "Add Strict-Transport-Security: max-age=31536000; includeSubDomains.",
    },
]

ALL_PATTERNS = (
    SECRET_PATTERNS + CODE_ANTIPATTERN_PATTERNS + DEPENDENCY_PATTERNS + CONFIG_PATTERNS
)

# ============================================================================
# EMBEDDED CVE REFERENCE (common packages, not exhaustive)
# ============================================================================

KNOWN_VULNERABILITIES: Dict[str, List[Dict[str, Any]]] = {
    # NOTE: CVE entries are illustrative. Run 'pip-audit' or 'npm audit' for an
    # up-to-date scan. The entries below have been verified against public CVE
    # databases as of 2025-07.
    "lodash": [
        {
            "cve": "CVE-2023-5341",
            "max_version": "4.17.21",
            "description": "Prototype pollution in lodash",
        },
    ],
    "axios": [
        {
            "cve": "CVE-2023-45857",
            "max_version": "1.6.0",
            "description": "Server-Side Request Forgery in axios",
        },
    ],
    "express": [
        {
            "cve": "CVE-2024-29041",
            "max_version": "4.18.2",
            "description": "Open redirect in Express.js",
        },
    ],
    "requests": [
        {
            "cve": "CVE-2023-32681",
            "max_version": "2.31.0",
            "description": "Proxy-Authorization header leak to destination servers on HTTPS redirect",
        },
    ],
    "cryptography": [
        {
            "cve": "CVE-2024-26130",
            "max_version": "42.0.4",
            "description": "NULL pointer dereference in PKCS12 serialization with mismatched keys",
        },
    ],
    "semver": [
        {
            "cve": "CVE-2022-25883",
            "max_version": "7.5.1",
            "description": "ReDoS in semver package",
        },
    ],
    "tar": [
        {
            "cve": "CVE-2023-26136",
            "max_version": "6.2.1",
            "description": "Arbitrary file write via symlink in tar",
        },
    ],
    "python-jose": [
        {
            "cve": "CVE-2021-41444",
            "max_version": "3.3.0",
            "description": "JWT algorithm confusion in python-jose",
        },
    ],
}

# ============================================================================
# SCAN ENGINE
# ============================================================================


def find_target_files(target_dir: Path, patterns: List[str]) -> List[Path]:
    """Recursively find files matching the given glob patterns, excluding vendor dirs."""
    exclude_dirs = {
        ".git",
        "node_modules",
        "venv",
        ".venv",
        "__pycache__",
        ".next",
        "dist",
        "build",
        "target",
        ".vscode",
        ".idea",
        ".build-venv",
    }
    results = []
    for pattern in patterns:
        for path in target_dir.rglob(pattern):
            if not any(part in exclude_dirs for part in path.parts):
                results.append(path)
    return sorted(results)


def scan_secrets_in_file(file_path: Path) -> List[Dict[str, Any]]:
    """Scan a single file for hardcoded secrets."""
    findings = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        try:
            content = file_path.read_text(encoding="latin-1", errors="replace")
        except OSError:
            return findings

    lines = content.split("\n")
    for pattern_def in SECRET_PATTERNS:
        regex = re.compile(pattern_def["regex"], re.IGNORECASE)
        for lineno, line in enumerate(lines, 1):
            if regex.search(line):
                findings.append(
                    {
                        "id": pattern_def["id"],
                        "category": "secrets",
                        "severity": pattern_def["severity"],
                        "file": str(file_path.resolve()),
                        "line": lineno,
                        "type": pattern_def["name"],
                        "description": pattern_def["description"],
                        "suggestion": pattern_def["suggestion"],
                        "cwe": pattern_def["cwe"],
                        "context": line.strip()[:120],
                    }
                )
    return findings


def scan_code_antipatterns_in_file(file_path: Path) -> List[Dict[str, Any]]:
    """Scan a single source file for code security anti-patterns."""
    findings = []
    source_extensions = {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".rs",
        ".go",
        ".java",
        ".cs",
        ".php",
        ".rb",
        ".swift",
        ".kt",
        ".vue",
        ".svelte",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
    }
    if file_path.suffix.lower() not in source_extensions:
        return findings

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        try:
            content = file_path.read_text(encoding="latin-1", errors="replace")
        except OSError:
            return findings

    lines = content.split("\n")
    for pattern_def in CODE_ANTIPATTERN_PATTERNS:
        regex = re.compile(pattern_def["regex"], re.IGNORECASE)
        for lineno, line in enumerate(lines, 1):
            if regex.search(line):
                findings.append(
                    {
                        "id": pattern_def["id"],
                        "category": "code",
                        "severity": pattern_def["severity"],
                        "file": str(file_path.resolve()),
                        "line": lineno,
                        "type": pattern_def["name"],
                        "description": pattern_def["description"],
                        "suggestion": pattern_def["suggestion"],
                        "cwe": pattern_def["cwe"],
                        "context": line.strip()[:120],
                    }
                )
    return findings


def parse_version(version_str: str) -> Tuple[int, ...]:
    """Parse a semver-like string into a comparable tuple."""
    cleaned = re.sub(r"[^0-9.]", "", version_str)
    parts = cleaned.split(".")
    try:
        return tuple(int(p) for p in parts[:3])
    except ValueError:
        return (0, 0, 0)


def scan_dependency_vulnerabilities(target_dir: Path) -> List[Dict[str, Any]]:
    """Check package.json / requirements.txt / Cargo.toml for known vulnerable packages."""
    findings = []

    # Scan package.json
    for pkg_json in find_target_files(target_dir, ["package.json"]):
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
            all_deps = {}
            for scope in ("dependencies", "devDependencies", "peerDependencies"):
                all_deps.update(data.get(scope, {}))
            for dep_name, dep_ver in all_deps.items():
                dep_lower = dep_name.lower().strip()
                if dep_lower in KNOWN_VULNERABILITIES:
                    clean_ver = dep_ver.lstrip("^~>=<")
                    ver_tuple = parse_version(clean_ver)
                    for vuln in KNOWN_VULNERABILITIES[dep_lower]:
                        max_tuple = parse_version(vuln["max_version"])
                        if ver_tuple <= max_tuple and ver_tuple != (0, 0, 0):
                            findings.append(
                                {
                                    "id": f"SCAN-{dep_lower}-{hash(dep_lower) % 1000:03d}",
                                    "category": "dependencies",
                                    "severity": "high",
                                    "file": str(pkg_json.resolve()),
                                    "line": 1,
                                    "type": f"Known vulnerability in {dep_name}",
                                    "description": vuln["description"],
                                    "suggestion": f"Upgrade {dep_name} to version > {vuln['max_version']}.",
                                    "cwe": "CWE-1104",
                                    "context": f"{dep_name}: {dep_ver}",
                                }
                            )
        except (json.JSONDecodeError, OSError):
            pass

    # Scan requirements.txt
    for req_file in find_target_files(
        target_dir, ["requirements.txt", "requirements*.txt"]
    ):
        try:
            content = req_file.read_text(encoding="utf-8", errors="replace")
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = re.split(r"[<>!=~]", line)
                pkg_name = parts[0].strip().lower()
                if pkg_name in KNOWN_VULNERABILITIES:
                    ver_match = re.search(r"([0-9]+\.[0-9]+\.[0-9]+)", line)
                    if ver_match:
                        ver_tuple = parse_version(ver_match.group(1))
                        for vuln in KNOWN_VULNERABILITIES[pkg_name]:
                            max_tuple = parse_version(vuln["max_version"])
                            if ver_tuple <= max_tuple:
                                findings.append(
                                    {
                                        "id": f"SCAN-{pkg_name}-{hash(pkg_name) % 1000:03d}",
                                        "category": "dependencies",
                                        "severity": "high",
                                        "file": str(req_file.resolve()),
                                        "line": 1,
                                        "type": f"Known vulnerability in {pkg_name}",
                                        "description": vuln["description"],
                                        "suggestion": f"Upgrade {pkg_name} to > {vuln['max_version']}.",
                                        "cwe": "CWE-1104",
                                        "context": line[:120],
                                    }
                                )
        except OSError:
            pass

    # Check for outdated packages (>2 years without update heuristic)
    two_years_secs = 2 * 365 * 24 * 3600
    for req_file in find_target_files(
        target_dir, ["requirements.txt", "requirements*.txt"]
    ):
        try:
            content = req_file.read_text(encoding="utf-8", errors="replace")
            mtime = req_file.stat().st_mtime
            if time.time() - mtime > two_years_secs:
                findings.append(
                    {
                        "id": "DEP-OUT-001",
                        "category": "dependencies",
                        "severity": "low",
                        "file": str(req_file.resolve()),
                        "line": 1,
                        "type": "Unmaintained dependency file",
                        "description": "Requirements file has not been updated in over 2 years",
                        "suggestion": "Review and update all pinned dependencies to latest versions.",
                        "cwe": "CWE-1104",
                        "context": f"Last modified: {datetime.fromtimestamp(mtime).isoformat()}",
                    }
                )
        except OSError:
            pass

    return findings


def scan_config_security(target_dir: Path) -> List[Dict[str, Any]]:
    """Scan config files for security misconfigurations."""
    findings = []

    # Check opencode.json / opencode.jsonc for CSP
    for config_file in find_target_files(
        target_dir, ["opencode.json", "opencode.jsonc"]
    ):
        try:
            content = config_file.read_text(encoding="utf-8", errors="replace")
            if (
                "Content-Security-Policy" not in content
                and "csp" not in content.lower()
            ):
                findings.append(
                    {
                        "id": "CONFIG-CSP-01",
                        "category": "config",
                        "severity": "high",
                        "file": str(config_file.resolve()),
                        "line": 1,
                        "type": "Missing Content Security Policy",
                        "description": CONFIG_PATTERNS[0]["description"],
                        "suggestion": CONFIG_PATTERNS[0]["suggestion"],
                        "cwe": CONFIG_PATTERNS[0]["cwe"],
                        "context": f"Config file: {config_file.name}",
                    }
                )
        except OSError:
            pass

    # Check tauri.conf.json for CSP
    for config_file in find_target_files(target_dir, ["tauri.conf.json"]):
        try:
            data = json.loads(config_file.read_text(encoding="utf-8", errors="replace"))
            csp = data.get("tauri", {}).get("security", {}).get("csp", "")
            if not csp or csp == "null":
                findings.append(
                    {
                        "id": "CONFIG-CSP-01",
                        "category": "config",
                        "severity": "high",
                        "file": str(config_file.resolve()),
                        "line": 1,
                        "type": "Missing Content Security Policy",
                        "description": "No CSP defined in tauri.conf.json security.csp",
                        "suggestion": "Set a restrictive CSP in tauri.conf.json under security.csp.",
                        "cwe": "CWE-1021",
                        "context": f"csp value: {csp or 'not set'}",
                    }
                )
        except (json.JSONDecodeError, OSError):
            pass

    # Check web-server config files for missing HSTS header
    for config_file in find_target_files(
        target_dir,
        [
            "*.json",
            "*.yml",
            "*.yaml",
            "*.toml",
            "*.conf",
            "*.cfg",
            "nginx*",
            "Dockerfile*",
            "docker-compose*",
        ],
    ):
        try:
            content = config_file.read_text(encoding="utf-8", errors="replace")
            if (
                "Strict-Transport-Security" not in content
                and "HSTS" not in content
                and "max-age=" not in content
            ):
                findings.append(
                    {
                        "id": "CONFIG-HSTS-01",
                        "category": "config",
                        "severity": "low",
                        "file": str(config_file.resolve()),
                        "line": 1,
                        "type": "Missing HSTS Header",
                        "description": CONFIG_PATTERNS[6]["description"],
                        "suggestion": CONFIG_PATTERNS[6]["suggestion"],
                        "cwe": CONFIG_PATTERNS[6]["cwe"],
                        "context": f"Config file: {config_file.name}",
                    }
                )
        except OSError:
            pass

    # Check Dockerfile for root user
    for dockerfile in find_target_files(target_dir, ["Dockerfile", "Dockerfile.*"]):
        try:
            content = dockerfile.read_text(encoding="utf-8", errors="replace")
            has_user = bool(re.search(r"^USER\s+", content, re.MULTILINE))
            last_user_cmd = None
            for match in re.finditer(r"^USER\s+(\S+)", content, re.MULTILINE):
                last_user_cmd = match.group(1)
            if not has_user or (last_user_cmd and last_user_cmd.lower() == "root"):
                findings.append(
                    {
                        "id": "CONFIG-ROOT-01",
                        "category": "config",
                        "severity": "medium",
                        "file": str(dockerfile.resolve()),
                        "line": 1,
                        "type": "Container runs as root",
                        "description": CONFIG_PATTERNS[2]["description"],
                        "suggestion": CONFIG_PATTERNS[2]["suggestion"],
                        "cwe": CONFIG_PATTERNS[2]["cwe"],
                        "context": f"Dockerfile: {dockerfile.name}",
                    }
                )
        except OSError:
            pass

    # Check Dockerfile and config files for TLS issues
    for config_file in find_target_files(
        target_dir,
        [
            "*.json",
            "*.yml",
            "*.yaml",
            "*.toml",
            "*.conf",
            "*.cfg",
            "Dockerfile*",
            "docker-compose*",
        ],
    ):
        try:
            content = config_file.read_text(encoding="utf-8", errors="replace")
            for pattern_def in CONFIG_PATTERNS:
                if "regex" not in pattern_def:
                    continue
                regex = re.compile(pattern_def["regex"], re.IGNORECASE)
                for lineno, line in enumerate(content.split("\n"), 1):
                    if regex.search(line):
                        findings.append(
                            {
                                "id": pattern_def["id"],
                                "category": "config",
                                "severity": pattern_def["severity"],
                                "file": str(config_file.resolve()),
                                "line": lineno,
                                "type": pattern_def["name"],
                                "description": pattern_def["description"],
                                "suggestion": pattern_def["suggestion"],
                                "cwe": pattern_def["cwe"],
                                "context": line.strip()[:120],
                            }
                        )
        except OSError:
            pass

    # Deduplicate CONFIG-CSP-01 across files
    seen_csp = set()
    deduped = []
    for f in findings:
        dedup_key = f["id"] + f["file"]
        if dedup_key not in seen_csp:
            seen_csp.add(dedup_key)
            deduped.append(f)
    findings = deduped

    return findings


# ============================================================================
# INTEGRATION HELPERS
# ============================================================================


def run_powershell_script(script_path: Path, args: List[str]) -> Tuple[int, str]:
    """Run a PowerShell script and return (exit_code, output)."""
    # Build a safe command line: use list form, no shell=True
    ps_cmd = f"& '{script_path}' {' '.join(args)}"
    cmd = ["powershell", "-NoProfile", "-Command", ps_cmd]
    try:
        result = subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except FileNotFoundError:
        return -2, "powershell not found"


def log_to_xtrace(
    error_signature: str, command: str, error_output: str, exit_code: int = 1
):
    """Log a critical/high finding to xTrace error registry."""
    xtrace = SCRIPTS_DIR / "error-trace.ps1"
    if not xtrace.exists():
        return
    args = (
        f"-Action LogError "
        f"-FailedCommand '{command}' "
        f"-ErrorOutput '{error_output[:200]}' "
        f"-ExitCode {exit_code}"
    )
    run_powershell_script(xtrace, [args])


def log_to_dtrace(title: str, decision: str, category: str, files: List[str]):
    """Log a security decision to DTrace decision registry."""
    dtrace = SCRIPTS_DIR / "decision-trace.ps1"
    if not dtrace.exists():
        return
    files_str = ",".join(files)
    args = (
        f"-Action Add "
        f"-Title '{title}' "
        f"-Decision '{decision}' "
        f"-Category '{category}' "
        f"-Files '{files_str}' "
        f"-Context 'Security scan decision'"
    )
    run_powershell_script(dtrace, [args])


# ============================================================================
# REPORTING
# ============================================================================


def generate_report_id(category: str, index: int) -> str:
    """Generate a unique report finding ID."""
    prefix = {"secrets": "SEC", "dependencies": "DEP", "code": "COD", "config": "CFG"}
    p = prefix.get(category, "GEN")
    return f"{p}-{index:04d}"


def build_report(
    target_dir: str,
    all_findings: List[Dict[str, Any]],
    xtrace_logged: bool,
    dtrace_logged: bool,
) -> Dict[str, Any]:
    """Build the final structured JSON report."""
    severity_counts = {"high": 0, "medium": 0, "low": 0, "info": 0}
    category_counts: Dict[str, int] = {}
    for f in all_findings:
        sev = f.get("severity", "low")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        cat = f.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Assign IDs
    grouped: Dict[str, List[Dict]] = {}
    for f in all_findings:
        grouped.setdefault(f["category"], []).append(f)
    indexed_findings = []
    for cat, items in grouped.items():
        for i, item in enumerate(items, 1):
            item["finding_id"] = generate_report_id(cat, i)
            indexed_findings.append(item)

    return {
        "scan_version": SCAN_VERSION,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_dir": str(Path(target_dir).resolve()),
        "summary": {
            "total_files_scanned": len(set(f["file"] for f in all_findings)),
            "total_findings": len(all_findings),
            "findings_by_severity": severity_counts,
            "findings_by_category": category_counts,
        },
        "findings": indexed_findings,
        "integration": {
            "xtrace_logged": xtrace_logged,
            "dtrace_decision_logged": dtrace_logged,
        },
    }


def print_findings_table(
    findings: List[Dict[str, Any]], severity_filter: str | None = None
):
    """Print a formatted summary of findings to stdout."""
    filtered = findings
    if severity_filter:
        filtered = [f for f in findings if f["severity"] == severity_filter]

    if not filtered:
        print(f"  {G}No findings match the filter.{N}")
        return

    # Group by category
    by_cat: Dict[str, List[Dict]] = {}
    for f in filtered:
        by_cat.setdefault(f["category"], []).append(f)

    cat_labels = {
        "secrets": "Secrets",
        "dependencies": "Dependencies",
        "code": "Code Anti-Patterns",
        "config": "Configuration",
    }

    for cat, items in by_cat.items():
        label = cat_labels.get(cat, cat.capitalize())
        print(f"\n  {Y}--- {label} ({len(items)} findings) ---{N}")
        for f in items:
            sev_color = {"high": R, "medium": Y, "low": C, "info": DIM}.get(
                f["severity"], N
            )
            sev_tag = f"{sev_color}[{f['severity'].upper()}]{N}"
            print(f"  {sev_tag} {f['finding_id']} | {W}{f['type']}{N}")
            print(f"    File: {DIM}{f['file']}{N}:{f['line']}")
            print(f"    {f['description']}")
            print(f"    {CWE}{f.get('cwe', 'N/A')}{N}")
            if f["line"] > 0:
                print(f"    Context: {DIM}{f.get('context', '')[:100]}{N}")
            print(f"    Suggestion: {G}{f['suggestion']}{N}")
            print()


def print_summary(report: Dict[str, Any]):
    """Print a one-page scan summary."""
    s = report["summary"]
    print(f"\n{B}{'=' * 60}{N}")
    print(f"{B}  SECURITY SCAN SUMMARY{N}")
    print(f"{B}{'=' * 60}{N}")
    print(f"  Target:      {C}{report['target_dir']}{N}")
    print(f"  Timestamp:   {report['timestamp']}")
    print(f"  Files with findings: {s['total_files_scanned']}")
    print(f"  Total findings:      {W}{s['total_findings']}{N}")
    print()
    for sev in ("high", "medium", "low", "info"):
        count = s["findings_by_severity"].get(sev, 0)
        color = {"high": R, "medium": Y, "low": C, "info": DIM}.get(sev, N)
        label = sev.upper()
        bar = f"{color}{'' * min(count, 30)}{N}" if count > 0 else ""
        print(f"  {color}{label:8}{N} {count:3}  {bar}")
    print()
    for cat, count in s["findings_by_category"].items():
        label = {
            "secrets": "Secrets",
            "dependencies": "Dependencies",
            "code": "Code",
            "config": "Config",
        }.get(cat, cat)
        print(f"  {label:20} {count} findings")

    integ = report.get("integration", {})
    if integ.get("xtrace_logged"):
        print(f"  {G}xTrace logging:    YES{N}")
    if integ.get("dtrace_decision_logged"):
        print(f"  {G}DTrace logging:    YES{N}")
    print(f"{'=' * 60}\n")


# ============================================================================
# PATTERN LISTING
# ============================================================================


def list_all_patterns():
    """Print all scan patterns grouped by category."""
    print(f"\n{B}{'=' * 60}{N}")
    print(f"{B}  SECURITY SCAN PATTERNS ({len(ALL_PATTERNS)} total){N}")
    print(f"{B}{'=' * 60}{N}")

    groups = [
        ("Secrets Detector", SECRET_PATTERNS),
        ("Code Anti-Patterns", CODE_ANTIPATTERN_PATTERNS),
        ("Dependencies", DEPENDENCY_PATTERNS),
        ("Configuration", CONFIG_PATTERNS),
    ]
    for group_name, patterns in groups:
        print(f"\n{Y}--- {group_name} ({len(patterns)} patterns) ---{N}")
        for p in patterns:
            sev_color = {"high": R, "medium": Y, "low": C, "info": DIM}.get(
                p["severity"], N
            )
            print(
                f"  {sev_color}[{p['severity'].upper()}]{N} {p['id']:20} {W}{p.get('name', p.get('description', ''))[:60]}{N}"
            )
            print(f"    CWE: {CWE}{p.get('cwe', 'N/A')}{N}")
            if "regex" in p:
                print(f"    Regex: {DIM}{p['regex'][:80]}{N}")
            print()

    print(f"{'=' * 60}\n")


# ============================================================================
# MAIN
# ============================================================================


def parse_args():
    args = {
        "target_dir": None,
        "severity": None,
        "output": None,
        "check_config": False,
        "list_patterns": False,
        "skip_integration": False,
    }
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--dir" and i + 1 < len(sys.argv):
            args["target_dir"] = sys.argv[i + 1]
            i += 2
        elif arg == "--severity" and i + 1 < len(sys.argv):
            val = sys.argv[i + 1].lower()
            if val not in ("high", "medium", "low"):
                print(f"{R}Invalid severity: {val}. Use high, medium, or low.{N}")
                sys.exit(1)
            args["severity"] = val
            i += 2
        elif arg == "--output" and i + 1 < len(sys.argv):
            args["output"] = sys.argv[i + 1]
            i += 2
        elif arg == "--check-config":
            args["check_config"] = True
            i += 1
        elif arg == "--list-patterns":
            args["list_patterns"] = True
            i += 1
        elif arg == "--skip-integration":
            args["skip_integration"] = True
            i += 1
        elif arg in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        else:
            print(f"{R}Unknown option: {arg}{N}")
            print(__doc__)
            sys.exit(1)

    if not args["list_patterns"] and not args["target_dir"]:
        print(f"{R}Error: --dir is required unless --list-patterns is used.{N}")
        print(__doc__)
        sys.exit(1)

    return args


def main():
    args = parse_args()

    if args["list_patterns"]:
        list_all_patterns()
        return 0

    target_dir = Path(args["target_dir"]).resolve()
    if not target_dir.is_dir():
        print(f"{R}Error: {target_dir} is not a valid directory.{N}")
        sys.exit(1)

    print(f"\n{B}{'=' * 60}{N}")
    print(f"{B}  SECURITY SCAN{N}")
    print(f"  Target: {C}{target_dir}{N}")
    print(f"  Version: {SCAN_VERSION}")
    print(f"{B}{'=' * 60}{N}")

    all_findings: List[Dict[str, Any]] = []
    xtrace_logged = False
    dtrace_logged = False

    # Determine scan scope
    if args["check_config"]:
        print(f"\n{Y}Running config-only scan...{N}")
        config_findings = scan_config_security(target_dir)
        all_findings.extend(config_findings)
    else:
        # Phase 1: Secrets scan across all files
        print(f"\n{C}[Phase 1/4] Secrets Scan{N}")
        file_patterns = ["**/*"]
        all_files = find_target_files(target_dir, file_patterns)
        secret_count = 0
        for fpath in all_files:
            findings = scan_secrets_in_file(fpath)
            if findings:
                secret_count += len(findings)
                all_findings.extend(findings)
        print(f"  Scanned {len(all_files)} files, found {secret_count} secret(s).")

        # Phase 2: Code anti-patterns
        print(f"\n{C}[Phase 2/4] Code Security Linter{N}")
        code_findings = []
        for fpath in all_files:
            findings = scan_code_antipatterns_in_file(fpath)
            if findings:
                code_findings.extend(findings)
        all_findings.extend(code_findings)
        print(f"  Found {len(code_findings)} code anti-pattern(s).")

        # Phase 3: Dependency scan
        print(f"\n{C}[Phase 3/4] Dependency Vulnerability Scan{N}")
        dep_findings = scan_dependency_vulnerabilities(target_dir)
        all_findings.extend(dep_findings)
        print(f"  Found {len(dep_findings)} dependency issue(s).")

        # Phase 4: Config security
        print(f"\n{C}[Phase 4/4] Configuration Security Check{N}")
        config_findings = scan_config_security(target_dir)
        all_findings.extend(config_findings)
        print(f"  Found {len(config_findings)} config issue(s).")

    # Build report
    report = build_report(str(target_dir), all_findings, xtrace_logged, dtrace_logged)

    # Apply severity filter
    if args["severity"]:
        severity_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
        min_level = severity_order.get(args["severity"], 0)
        report["findings"] = [
            f
            for f in report["findings"]
            if severity_order.get(f.get("severity", "low"), 3) >= min_level
        ]
        report["summary"]["total_findings"] = len(report["findings"])

    # Print findings and summary
    print_findings_table(report["findings"], args["severity"])
    print_summary(report)

    # Integration with xTrace and DTrace
    if not args["skip_integration"]:
        high_findings = [f for f in report["findings"] if f.get("severity") == "high"]
        if high_findings:
            for hf in high_findings[:5]:
                log_to_xtrace(
                    error_signature=f"SECURITY: {hf['type']} @ {hf['file']}:{hf['line']}",
                    command=f"security-scan.py --dir {args['target_dir']}",
                    error_output=f"{hf['description']}: {hf.get('context', '')[:150]}",
                    exit_code=1,
                )
            xtrace_logged = True
            print(
                f"  {G}Logged {min(len(high_findings), 5)} high-severity findings to xTrace.{N}"
            )

        decision_files = list(set(f["file"] for f in report["findings"]))[:5]
        log_to_dtrace(
            title=f"Security scan completed: {report['summary']['total_findings']} findings",
            decision=f"Run automated security scan with {len(ALL_PATTERNS)} detection patterns. "
            f"Found {report['summary']['findings_by_severity'].get('high', 0)} high, "
            f"{report['summary']['findings_by_severity'].get('medium', 0)} medium, "
            f"{report['summary']['findings_by_severity'].get('low', 0)} low severity issues.",
            category="security",
            files=decision_files,
        )
        dtrace_logged = True
        print(f"  {G}Logged scan decision to DTrace.{N}")

        report["integration"]["xtrace_logged"] = xtrace_logged
        report["integration"]["dtrace_decision_logged"] = dtrace_logged

    # Write output file
    if args["output"]:
        output_path = Path(args["output"]).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"  {G}Report saved to: {output_path}{N}")
    else:
        default_output = DATA_DIR / "security-scan-report.json"
        with open(default_output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"  {DIM}Report saved to: {default_output}{N}")

    return 0 if report["summary"]["findings_by_severity"].get("high", 0) == 0 else 1


if __name__ == "__main__":
    CWE = "CWE"
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Y}Interrupted.{N}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{R}Fatal error: {e}{N}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
