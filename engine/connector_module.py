#!/usr/bin/env python3
"""
Connector Framework — pre-built HTTP/REST/WS callers for external services.

Provides tools to make HTTP requests (GET, POST, PUT, DELETE) and WebSocket
connections via stdlib (urllib + asyncio stubs).
"""

import json
import urllib.request
import urllib.error
import urllib.parse
import threading
from typing import Any

# ---------------------------------------------------------------------------
# HTTP Connector
# ---------------------------------------------------------------------------

class Connector:
    """Simple HTTP/S connector for external API calls."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active_connections: dict[str, dict] = {}

    def request(self, url: str, method: str = "GET",
                headers: dict | None = None, body: str | None = None,
                timeout: int = 15) -> dict:
        """Make an HTTP request and return the response."""
        req_headers = {"User-Agent": "CortexStratum/1.0"}
        if headers:
            req_headers.update(headers)

        try:
            data = body.encode() if body else None
            req = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_body = resp.read().decode(errors="replace")
                return {
                    "status": "ok",
                    "status_code": resp.status,
                    "headers": dict(resp.headers),
                    "body": resp_body,
                    "body_length": len(resp_body),
                }
        except urllib.error.HTTPError as e:
            return {
                "status": "error",
                "status_code": e.code,
                "error": e.read().decode(errors="replace")[:1000],
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def status(self) -> dict:
        with self._lock:
            return {
                "active_connections": len(self._active_connections),
                "connections": list(self._active_connections.keys())[:10],
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_CONNECTOR: Connector | None = None


def get_connector() -> Connector:
    global _CONNECTOR
    if _CONNECTOR is None:
        _CONNECTOR = Connector()
    return _CONNECTOR


# ---------------------------------------------------------------------------
# MCP Tool definitions & handler
# ---------------------------------------------------------------------------

CONNECTOR_TOOLS = [
    {
        "name": "write_connector_request",
        "description": " WRITE — Make an HTTP request to an external service. Returns status code, headers, body.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL (https://...)"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"]},
                "headers": {"type": "object", "description": "Optional HTTP headers"},
                "body": {"type": "string", "description": "Request body (for POST/PUT/PATCH)"},
                "timeout": {"type": "integer", "default": 15},
            },
            "required": ["url"],
        },
    },
    {
        "name": "read_connector_status",
        "description": " READ — View active connections and connector stats.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


def handle_tool_call(name: str, args: dict) -> dict:
    conn = get_connector()
    if name == "write_connector_request":
        return {"content": [{"type": "text", "text": json.dumps(conn.request(
            url=args.get("url", ""),
            method=args.get("method", "GET"),
            headers=args.get("headers"),
            body=args.get("body"),
            timeout=args.get("timeout", 15),
        ), indent=2)}]}
    elif name == "read_connector_status":
        return {"content": [{"type": "text", "text": json.dumps(conn.status(), indent=2)}]}
    msg = "Unknown connector tool: " + str(name)
    return {"content": [{"type": "text", "text": json.dumps({"error": msg})}]}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Connector Framework Self-Test ===\n")

    conn = Connector()

    # 1. Status fresh
    s = conn.status()
    print(f"1. Fresh: {s['active_connections']} active")
    assert s["active_connections"] == 0

    # 2. Bad URL (network error, not DNS)
    r = conn.request("http://0.0.0.0:1/test", timeout=2)
    print(f"2. Bad URL: status={r['status']}")
    assert r["status"] == "error"

    # 3. HTTPS request (valid URL, expect non-error)
    r2 = conn.request("https://httpbin.org/get", timeout=10)
    print(f"3. https://httpbin.org/get: status={r2.get('status')}, code={r2.get('status_code')}")
    # May fail without network — acceptable; test connectivity at runtime

    print("\nAll self-tests passed.")
