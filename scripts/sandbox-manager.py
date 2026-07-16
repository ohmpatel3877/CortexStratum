#!/usr/bin/env python3
"""
Sandbox Manager — Lightweight code execution sandbox for running untrusted
or isolated code snippets. Uses file-based isolation with temp directories,
timeouts, and output capture. No Docker dependency.

Usage:
    python scripts/sandbox-manager.py --run --language python --code "print('hello')"
    python scripts/sandbox-manager.py --run --file path/to/script.py
    python scripts/sandbox-manager.py --verify
    python scripts/sandbox-manager.py --check-safety --code "risky code here"
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SANDBOX_BASE = Path(os.environ.get("TEMP", "C:\\Users\\ohmpa\\AppData\\Local\\Temp")) / "opencode" / "sandbox"
SANDBOX_LOG = DATA_DIR / "sandbox-log.json"

G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
B = "\033[94m"
C = "\033[96m"
N = "\033[0m"
DIM = "\033[2m"

BLOCKLIST_PATTERNS: List[Dict[str, Any]] = [
    {"pattern": r"os\.system\s*\(", "weight": 9, "reason": "os.system allows arbitrary command execution"},
    {"pattern": r"os\.popen\s*\(", "weight": 9, "reason": "os.popen allows arbitrary command execution"},
    {"pattern": r"os\.fork\s*\(", "weight": 8, "reason": "Process forking is prohibited in sandbox"},
    {"pattern": r"os\.kill\s*\(", "weight": 7, "reason": "Process killing is prohibited in sandbox"},
    {"pattern": r"subprocess\.(call|run|Popen|check_call|check_output)\s*\(", "weight": 9, "reason": "Subprocess execution is prohibited"},
    {"pattern": r"eval\s*\(", "weight": 9, "reason": "eval() allows arbitrary code execution"},
    {"pattern": r"exec\s*\(", "weight": 9, "reason": "exec() allows arbitrary code execution"},
    {"pattern": r"__import__\s*\(", "weight": 8, "reason": "Dynamic imports can bypass safety checks"},
    {"pattern": r"compile\s*\(", "weight": 8, "reason": "compile() can be used to generate executable code"},
    {"pattern": r"open\s*\(\s*['\"][^'\"]+['\"]\s*,\s*['\"]w", "weight": 6, "reason": "File writes can modify the filesystem"},
    {"pattern": r"open\s*\(\s*['\"][^'\"]+['\"]\s*,\s*['\"]a", "weight": 6, "reason": "File appends can modify the filesystem"},
    {"pattern": r"shutil\.rmtree\s*\(", "weight": 9, "reason": "Recursive directory deletion is destructive"},
    {"pattern": r"shutil\.move\s*\(", "weight": 6, "reason": "File moves can alter filesystem structure"},
    {"pattern": r"os\.remove\s*\(", "weight": 8, "reason": "File deletion is destructive"},
    {"pattern": r"os\.rmdir\s*\(", "weight": 8, "reason": "Directory deletion is destructive"},
    {"pattern": r"os\.unlink\s*\(", "weight": 8, "reason": "File unlink is destructive"},
    {"pattern": r"os\.chmod\s*\(", "weight": 6, "reason": "Permission changes are prohibited"},
    {"pattern": r"os\.chown\s*\(", "weight": 6, "reason": "Ownership changes are prohibited"},
    {"pattern": r"ctypes\.", "weight": 8, "reason": "ctypes allows C-level memory manipulation"},
    {"pattern": r"socket\.", "weight": 7, "reason": "Network socket operations are restricted"},
    {"pattern": r"requests\.", "weight": 5, "reason": "Network requests are restricted without --network flag"},
    {"pattern": r"urllib\.(request|urlopen)", "weight": 5, "reason": "Network requests are restricted without --network flag"},
    {"pattern": r"http\.client\.", "weight": 5, "reason": "HTTP client operations are restricted"},
]

SANDBOX_VERSION = "1.0.0"

PS_BLOCKLIST_PATTERNS: List[Dict[str, Any]] = [
    {"pattern": r"Remove-Item\s+-Recurse", "weight": 9, "reason": "Recursive deletion is destructive"},
    {"pattern": r"Remove-Item.*-Force", "weight": 8, "reason": "Force deletion is destructive"},
    {"pattern": r"Stop-Process|kill\s+", "weight": 8, "reason": "Process termination is prohibited"},
    {"pattern": r"Start-Process.*-Verb\s+RunAs", "weight": 9, "reason": "Elevated execution is prohibited"},
    {"pattern": r"Invoke-Command|Invoke-Expression", "weight": 9, "reason": "Remote/invoke execution is prohibited"},
    {"pattern": r"New-Object.*Net\.WebClient", "weight": 7, "reason": "Network downloads are restricted"},
    {"pattern": r"\[System\.IO\.File\]::", "weight": 6, "reason": "Direct .NET file I/O is restricted"},
    {"pattern": r"Add-Type.*-AssemblyName", "weight": 7, "reason": "Loading arbitrary assemblies is restricted"},
    {"pattern": r"Set-ExecutionPolicy", "weight": 9, "reason": "Changing execution policy is prohibited"},
    {"pattern": r"Register-ScheduledJob|Register-ScheduledTask", "weight": 9, "reason": "Scheduled task creation is prohibited"},
]


class SandboxError(Exception):
    """Base exception for sandbox operations."""


class SafetyViolation(SandboxError):
    """Raised when code fails safety checks."""


def _compute_code_hash(code: str) -> str:
    """Compute SHA-256 hash of code snippet."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _load_log() -> List[Dict[str, Any]]:
    """Load sandbox execution log from disk."""
    if not SANDBOX_LOG.exists():
        return []
    try:
        data = SANDBOX_LOG.read_text(encoding="utf-8")
        return json.loads(data) if data.strip() else []
    except (json.JSONDecodeError, OSError):
        return []


def _append_log(entry: Dict[str, Any]) -> None:
    """Append an entry to the sandbox execution log."""
    log = _load_log()
    log.append(entry)
    SANDBOX_LOG.parent.mkdir(parents=True, exist_ok=True)
    SANDBOX_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


class SandboxManager:
    """Isolated code execution environment using temp directories and timeouts."""

    def __init__(self, keep_files: bool = False):
        self.keep_files = keep_files
        self.sandbox_base = SANDBOX_BASE

    def _create_sandbox_dir(self) -> Path:
        """Create a unique temp directory for sandboxed execution."""
        sandbox_path = self.sandbox_base / str(uuid.uuid4())
        sandbox_path.mkdir(parents=True, exist_ok=True)
        return sandbox_path

    def _cleanup(self, sandbox_path: Path) -> None:
        """Remove sandbox directory unless keep_files is True."""
        if not self.keep_files and sandbox_path.exists():
            shutil.rmtree(sandbox_path, ignore_errors=True)

    def _run_subprocess(
        self,
        cmd: List[str],
        cwd: Path,
        timeout: int,
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Execute a subprocess with timeout and output capture."""
        start = time.monotonic()
        process = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        output = {"stdout": "", "stderr": ""}
        killed = False

        def _kill():
            nonlocal killed
            try:
                process.kill()
                killed = True
            except OSError:
                pass

        timer = threading.Timer(timeout, _kill)
        timer.start()

        try:
            stdout_data, stderr_data = process.communicate()
            output["stdout"] = stdout_data or ""
            output["stderr"] = stderr_data or ""
        finally:
            timer.cancel()

        duration = round(time.monotonic() - start, 3)
        process.poll()

        return {
            "success": process.returncode == 0 and not killed,
            "stdout": output["stdout"],
            "stderr": output["stderr"],
            "returncode": process.returncode if not killed else -9,
            "duration": duration,
            "killed": killed,
        }

    def evaluate_code_safety(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Static safety analysis of code before execution.

        Scans for dangerous patterns and returns a safety assessment.

        Args:
            code: Source code to analyze.
            language: 'python' or 'powershell'.

        Returns:
            Dict with safe (bool), warnings (list), and risk_score (0-10).
        """
        warnings: List[str] = []
        total_weight = 0

        patterns = BLOCKLIST_PATTERNS if language == "python" else PS_BLOCKLIST_PATTERNS
        if language not in ("python", "powershell"):
            patterns = BLOCKLIST_PATTERNS + PS_BLOCKLIST_PATTERNS

        for entry in patterns:
            import re
            if re.search(entry["pattern"], code, re.IGNORECASE):
                warnings.append(entry["reason"])
                total_weight += entry["weight"]

        risk_score = min(10, total_weight)

        return {
            "safe": risk_score <= 7,
            "warnings": warnings,
            "risk_score": risk_score,
        }

    def execute_python(
        self,
        code: str,
        timeout: int = 30,
        network: bool = False,
    ) -> Dict[str, Any]:
        """Execute Python code in an isolated sandbox directory.

        Args:
            code: Python source code to execute.
            timeout: Maximum execution time in seconds (default 30).
            network: Allow network access (default False).

        Returns:
            Dict with success, stdout, stderr, returncode, duration, sandbox_path.
        """
        safety = self.evaluate_code_safety(code, "python")
        if not safety["safe"]:
            raise SafetyViolation(
                f"Code safety check failed (risk: {safety['risk_score']}/10): "
                f"{'; '.join(safety['warnings'][:3])}"
            )

        sandbox_path = self._create_sandbox_dir()
        script_path = sandbox_path / "script.py"

        try:
            script_path.write_text(code, encoding="utf-8")
            env = os.environ.copy()
            if not network:
                env.pop("HTTP_PROXY", None)
                env.pop("HTTPS_PROXY", None)
                env.pop("http_proxy", None)
                env.pop("https_proxy", None)

            result = self._run_subprocess(
                [sys.executable, str(script_path)],
                sandbox_path,
                timeout,
                env=env,
            )
            result["sandbox_path"] = str(sandbox_path)
            if not self.keep_files:
                self._cleanup(sandbox_path)
                result["sandbox_path"] = str(sandbox_path) + " (cleaned)"

            entry = {
                "id": str(uuid.uuid4()),
                "timestamp": _now_iso(),
                "language": "python",
                "code_hash": _compute_code_hash(code),
                "success": result["success"],
                "duration": result["duration"],
                "returncode": result["returncode"],
                "risk_score": safety["risk_score"],
                "safety_warnings": safety["warnings"],
            }
            _append_log(entry)

            return result

        except SafetyViolation:
            self._cleanup(sandbox_path)
            raise
        except Exception as e:
            self._cleanup(sandbox_path)
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "duration": 0.0,
                "sandbox_path": str(sandbox_path) + " (cleaned)",
                "killed": False,
            }

    def execute_powershell(self, script: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute PowerShell script in an isolated sandbox directory.

        Args:
            script: PowerShell script content.
            timeout: Maximum execution time in seconds (default 30).

        Returns:
            Dict with success, stdout, stderr, returncode, duration, sandbox_path.
        """
        safety = self.evaluate_code_safety(script, "powershell")
        if not safety["safe"]:
            raise SafetyViolation(
                f"Code safety check failed (risk: {safety['risk_score']}/10): "
                f"{'; '.join(safety['warnings'][:3])}"
            )

        sandbox_path = self._create_sandbox_dir()
        script_path = sandbox_path / "script.ps1"

        try:
            script_path.write_text(script, encoding="utf-8")

            result = self._run_subprocess(
                ["pwsh", "-NoProfile", "-File", str(script_path)],
                sandbox_path,
                timeout,
            )
            result["sandbox_path"] = str(sandbox_path)
            if not self.keep_files:
                self._cleanup(sandbox_path)
                result["sandbox_path"] = str(sandbox_path) + " (cleaned)"

            entry = {
                "id": str(uuid.uuid4()),
                "timestamp": _now_iso(),
                "language": "powershell",
                "code_hash": _compute_code_hash(script),
                "success": result["success"],
                "duration": result["duration"],
                "returncode": result["returncode"],
                "risk_score": safety["risk_score"],
                "safety_warnings": safety["warnings"],
            }
            _append_log(entry)

            return result

        except SafetyViolation:
            self._cleanup(sandbox_path)
            raise
        except Exception as e:
            self._cleanup(sandbox_path)
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "duration": 0.0,
                "sandbox_path": str(sandbox_path) + " (cleaned)",
                "killed": False,
            }

    def execute_shell(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute a shell command in an isolated sandbox directory.

        WARNING: shell=True is used. Only call with trusted commands.

        Args:
            command: Shell command string.
            timeout: Maximum execution time in seconds (default 30).

        Returns:
            Dict with success, stdout, stderr, returncode, duration, sandbox_path.
        """
        sandbox_path = self._create_sandbox_dir()

        try:
            start = time.monotonic()
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=str(sandbox_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            killed = False

            def _kill():
                nonlocal killed
                try:
                    process.kill()
                    killed = True
                except OSError:
                    pass

            timer = threading.Timer(timeout, _kill)
            timer.start()

            try:
                stdout_data, stderr_data = process.communicate()
            finally:
                timer.cancel()

            duration = round(time.monotonic() - start, 3)
            process.poll()

            result = {
                "success": process.returncode == 0 and not killed,
                "stdout": stdout_data or "",
                "stderr": stderr_data or "",
                "returncode": process.returncode if not killed else -9,
                "duration": duration,
                "killed": killed,
                "sandbox_path": str(sandbox_path),
            }

            if not self.keep_files:
                self._cleanup(sandbox_path)
                result["sandbox_path"] = str(sandbox_path) + " (cleaned)"

            entry = {
                "id": str(uuid.uuid4()),
                "timestamp": _now_iso(),
                "language": "shell",
                "code_hash": _compute_code_hash(command),
                "success": result["success"],
                "duration": result["duration"],
                "returncode": result["returncode"],
                "risk_score": 0,
                "safety_warnings": [],
            }
            _append_log(entry)

            return result

        except Exception as e:
            self._cleanup(sandbox_path)
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "duration": 0.0,
                "sandbox_path": str(sandbox_path) + " (cleaned)",
                "killed": False,
            }

    def verify_sandbox(self) -> Dict[str, Any]:
        """Run a health check to verify the sandbox works correctly.

        Executes a trivial Python script and confirms output capture.

        Returns:
            Dict with status and details of each verification step.
        """
        results = {}

        try:
            py_result = self.execute_python(
                'print("sandbox-ok")',
                timeout=10,
            )
            results["python"] = {
                "status": "PASS" if py_result["success"] and "sandbox-ok" in py_result["stdout"] else "FAIL",
                "stdout": py_result["stdout"],
                "stderr": py_result["stderr"],
                "duration": py_result["duration"],
            }
        except Exception as e:
            results["python"] = {"status": "ERROR", "error": str(e)}

        try:
            ps_result = self.execute_powershell(
                'Write-Output "sandbox-ok"',
                timeout=10,
            )
            results["powershell"] = {
                "status": "PASS" if ps_result["success"] and "sandbox-ok" in ps_result["stdout"] else "FAIL",
                "stdout": ps_result["stdout"],
                "stderr": ps_result["stderr"],
                "duration": ps_result["duration"],
            }
        except Exception as e:
            results["powershell"] = {"status": "ERROR", "error": str(e)}

        try:
            shell_result = self.execute_shell(
                'echo sandbox-ok',
                timeout=10,
            )
            results["shell"] = {
                "status": "PASS" if shell_result["success"] and "sandbox-ok" in shell_result["stdout"] else "FAIL",
                "stdout": shell_result["stdout"],
                "stderr": shell_result["stderr"],
                "duration": shell_result["duration"],
            }
        except Exception as e:
            results["shell"] = {"status": "ERROR", "error": str(e)}

        try:
            safety = self.evaluate_code_safety(
                'import subprocess; subprocess.call(["rm", "-rf", "/"])',
                "python",
            )
            results["safety_check"] = {
                "status": "PASS" if not safety["safe"] and safety["risk_score"] > 7 else "FAIL",
                "risk_score": safety["risk_score"],
                "warnings_count": len(safety["warnings"]),
            }
        except Exception as e:
            results["safety_check"] = {"status": "ERROR", "error": str(e)}

        all_pass = all(
            r.get("status") == "PASS" for r in results.values()
        )

        return {
            "version": SANDBOX_VERSION,
            "timestamp": _now_iso(),
            "overall": "PASS" if all_pass else "FAIL",
            "checks": results,
        }


def format_result(result: Dict[str, Any], title: str = "Execution Result") -> str:
    """Format a sandbox result dict for human-readable output."""
    status_color = G if result.get("success") else R
    status_icon = "✓" if result.get("success") else "✗"
    lines = [
        f"\n{B}{'=' * 60}{N}",
        f"{B}  {title}{N}",
        f"{B}{'=' * 60}{N}",
        f"  Status:     {status_color}{status_icon} {'SUCCESS' if result.get('success') else 'FAILED'}{N}",
        f"  Returncode: {result.get('returncode', 'N/A')}",
        f"  Duration:   {result.get('duration', 0):.3f}s",
    ]
    if result.get("killed"):
        lines.append(f"  {R}  TIMED OUT and was killed{N}")

    if result.get("stdout"):
        stdout = result["stdout"].rstrip()
        lines.append(f"\n  {C}--- stdout ---{N}")
        for line in stdout.split("\n"):
            lines.append(f"  {DIM}{line}{N}")

    if result.get("stderr"):
        stderr = result["stderr"].rstrip()
        lines.append(f"\n  {Y}--- stderr ---{N}")
        for line in stderr.split("\n"):
            lines.append(f"  {Y}{line}{N}")

    if result.get("sandbox_path"):
        lines.append(f"\n  Sandbox: {DIM}{result['sandbox_path']}{N}")

    lines.append(f"{'=' * 60}\n")
    return "\n".join(lines)


def format_safety(safety: Dict[str, Any]) -> str:
    """Format safety check result for human-readable output."""
    color = G if safety["safe"] else R
    lines = [
        f"\n{B}{'=' * 60}{N}",
        f"{B}  CODE SAFETY ASSESSMENT{N}",
        f"{B}{'=' * 60}{N}",
        f"  Safe:       {color}{'YES' if safety['safe'] else 'NO'}{N}",
        f"  Risk Score: {safety['risk_score']}/10",
    ]
    if safety["warnings"]:
        lines.append(f"\n  {Y}Warnings ({len(safety['warnings'])}):{N}")
        for w in safety["warnings"]:
            lines.append(f"    {Y}⚠ {w}{N}")
    else:
        lines.append(f"\n  {G}No warnings detected{N}")
    lines.append(f"{'=' * 60}\n")
    return "\n".join(lines)


def format_verify(result: Dict[str, Any]) -> str:
    """Format verification result for human-readable output."""
    overall_color = G if result["overall"] == "PASS" else R
    lines = [
        f"\n{B}{'=' * 60}{N}",
        f"{B}  SANDBOX VERIFICATION{N}",
        f"  Version: {result['version']}",
        f"  Overall: {overall_color}{result['overall']}{N}",
        f"{B}{'=' * 60}{N}",
    ]
    for check_name, check_result in result["checks"].items():
        label = check_name.replace("_", " ").title()
        status = check_result.get("status", "UNKNOWN")
        sc = G if status == "PASS" else (Y if status == "ERROR" else R)
        lines.append(f"\n  {label:20} {sc}{status}{N}")
        for key, val in check_result.items():
            if key != "status":
                lines.append(f"    {key:20} {DIM}{val}{N}")
    lines.append(f"{'=' * 60}\n")
    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Sandbox Manager — lightweight code execution sandbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--run", action="store_true", help="Execute code in sandbox")
    parser.add_argument("--language", choices=["python", "powershell", "shell"], default="python", help="Code language")
    parser.add_argument("--code", type=str, help="Inline code string to execute")
    parser.add_argument("--file", type=str, help="File containing code to execute")
    parser.add_argument("--timeout", type=int, default=30, help="Execution timeout in seconds")
    parser.add_argument("--network", action="store_true", help="Allow network access (Python only)")
    parser.add_argument("--verify", action="store_true", help="Run sandbox health check")
    parser.add_argument("--check-safety", action="store_true", help="Run safety check on code without executing")
    parser.add_argument("--keep-files", action="store_true", help="Keep sandbox files after execution")
    parser.add_argument("--log", action="store_true", help="Show sandbox execution log")

    args = parser.parse_args()

    if args.log:
        log = _load_log()
        if not log:
            print(f"{Y}No sandbox executions logged yet.{N}")
            return 0
        print(f"\n{B}{'=' * 60}{N}")
        print(f"{B}  SANDBOX EXECUTION LOG ({len(log)} entries){N}")
        print(f"{B}{'=' * 60}{N}")
        for entry in log[-20:]:
            color = G if entry["success"] else R
            print(f"  {color}{'✓' if entry['success'] else '✗'}{N} "
                  f"{entry['timestamp'][:19]}  "
                  f"{entry['language']:12}  "
                  f"{entry['duration']:>6.3f}s  "
                  f"risk={entry['risk_score']}/10  "
                  f"hash={entry['code_hash'][:12]}...")
        print(f"{'=' * 60}\n")
        return 0

    if args.verify:
        manager = SandboxManager(keep_files=True)
        result = manager.verify_sandbox()
        print(format_verify(result))
        return 0 if result["overall"] == "PASS" else 1

    if args.check_safety:
        if not args.code and not args.file:
            print(f"{R}Error: --code or --file required with --check-safety{N}")
            return 1
        code = args.code
        if args.file:
            code = Path(args.file).read_text(encoding="utf-8")
        manager = SandboxManager()
        safety = manager.evaluate_code_safety(code, args.language)
        print(format_safety(safety))
        return 0 if safety["safe"] else 1

    if args.run:
        if not args.code and not args.file:
            print(f"{R}Error: --code or --file required with --run{N}")
            return 1

        code = args.code
        if args.file:
            try:
                code = Path(args.file).read_text(encoding="utf-8")
            except FileNotFoundError:
                print(f"{R}Error: File not found: {args.file}{N}")
                return 1

        manager = SandboxManager(keep_files=args.keep_files)

        try:
            if args.language == "python":
                result = manager.execute_python(code, timeout=args.timeout, network=args.network)
            elif args.language == "powershell":
                result = manager.execute_powershell(code, timeout=args.timeout)
            elif args.language == "shell":
                result = manager.execute_shell(code, timeout=args.timeout)
            else:
                print(f"{R}Error: Unsupported language: {args.language}{N}")
                return 1

            print(format_result(result, f"{args.language.upper()} Execution"))
            return 0 if result["success"] else 1

        except SafetyViolation as e:
            print(f"{R}SAFETY BLOCKED: {e}{N}")
            return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
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
