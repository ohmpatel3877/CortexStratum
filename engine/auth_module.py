#!/usr/bin/env python3
"""
Auth Module — OAuth2 client, HMAC signing, RBAC, and AES-GCM encryption.

All stdlib-only (AES-GCM via hashlib + os.urandom — simplified CTR-based cipher).
For production, replace with cryptography or pycryptodome.
"""

import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RBAC_FILE = DATA_DIR / "rbac-roles.json"
HMAC_KEY_FILE = DATA_DIR / ".hmac_key"

# ---------------------------------------------------------------------------
# Simulated AES-GCM (stdlib only) — CTR mode + HMAC integrity
# For real encryption, install cryptography and use AESGCM.
# ---------------------------------------------------------------------------

_BLOCK_SIZE = 16  # 128-bit block


def _aes_encrypt(plaintext: str, key: bytes) -> dict:
    """Encrypt plaintext with AES-CTR-like cipher + HMAC integrity."""
    if len(key) < 32:
        key = hashlib.sha256(key).digest()
    iv = os.urandom(_BLOCK_SIZE)
    # Simple CTR: keystream = SHA256(iv + counter) for each block
    cipher_blocks = []
    for i in range(0, len(plaintext), _BLOCK_SIZE):
        counter = (i // _BLOCK_SIZE).to_bytes(8, "big")
        keystream = hashlib.sha256(iv + counter).digest()
        block = plaintext[i:i + _BLOCK_SIZE]
        cipher_blocks.append(bytes(a ^ b for a, b in zip(block.encode(), keystream[:len(block)])))
    ciphertext = b"".join(cipher_blocks)
    tag = hmac.new(key, iv + ciphertext, "sha256").hexdigest()[:16]
    return {
        "iv": iv.hex(),
        "ciphertext": ciphertext.hex(),
        "tag": tag,
    }


def _aes_decrypt(data: dict, key: bytes) -> str | None:
    """Decrypt data encrypted with _aes_encrypt."""
    if len(key) < 32:
        key = hashlib.sha256(key).digest()
    try:
        iv = bytes.fromhex(data["iv"])
        ciphertext = bytes.fromhex(data["ciphertext"])
        tag = data["tag"]
        expected = hmac.new(key, iv + ciphertext, "sha256").hexdigest()[:16]
        if tag != expected:
            return None  # integrity check failed
        plain_blocks = []
        for i in range(0, len(ciphertext), _BLOCK_SIZE):
            counter = (i // _BLOCK_SIZE).to_bytes(8, "big")
            keystream = hashlib.sha256(iv + counter).digest()
            block = ciphertext[i:i + _BLOCK_SIZE]
            plain_blocks.append(bytes(a ^ b for a, b in zip(block, keystream[:len(block)])))
        return b"".join(plain_blocks).decode("utf-8")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# OAuth2 Client
# ---------------------------------------------------------------------------

class OAuth2Client:
    """Simple OAuth2 client (authorization_code flow)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._config: dict = {}
        self._token: dict = {}  # {"access_token": ..., "refresh_token": ..., "expires_at": ...}

    def configure(self, config: dict) -> dict:
        required = ["client_id", "token_url"]
        for r in required:
            if r not in config:
                return {"status": "error", "error": f"Missing required field: {r}"}
        with self._lock:
            self._config = {
                "client_id": config["client_id"],
                "client_secret": config.get("client_secret", ""),
                "token_url": config["token_url"],
                "scopes": config.get("scopes", ""),
                "auth_header": config.get("auth_header", "Bearer"),
            }
        return {"status": "ok", "config": list(self._config.keys())}

    def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for tokens."""
        cfg = self._get_config()
        if not cfg:
            return {"status": "error", "error": "OAuth2 not configured. Call write_oauth_configure first."}

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": cfg["client_id"],
        }
        if cfg.get("client_secret"):
            data["client_secret"] = cfg["client_secret"]

        try:
            req = urllib.request.Request(
                cfg["token_url"],
                data=urllib.parse.urlencode(data).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                token_data = json.loads(resp.read().decode())
        except Exception as e:
            return {"status": "error", "error": f"Token exchange failed: {e}"}

        with self._lock:
            self._token = {
                "access_token": token_data.get("access_token", ""),
                "refresh_token": token_data.get("refresh_token", ""),
                "expires_at": time.time() + token_data.get("expires_in", 3600),
            }
        return {"status": "ok", "token_type": token_data.get("token_type", "bearer"),
                "scope": token_data.get("scope", ""),
                "expires_in": token_data.get("expires_in", 3600)}

    def refresh_token(self) -> dict:
        """Refresh the access token using refresh_token."""
        cfg = self._get_config()
        if not cfg:
            return {"status": "error", "error": "OAuth2 not configured."}
        with self._lock:
            refresh = self._token.get("refresh_token", "")
        if not refresh:
            return {"status": "error", "error": "No refresh token available."}

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": cfg["client_id"],
        }
        if cfg.get("client_secret"):
            data["client_secret"] = cfg["client_secret"]

        try:
            req = urllib.request.Request(
                cfg["token_url"],
                data=urllib.parse.urlencode(data).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                token_data = json.loads(resp.read().decode())
        except Exception as e:
            return {"status": "error", "error": f"Token refresh failed: {e}"}

        with self._lock:
            self._token["access_token"] = token_data.get("access_token", self._token["access_token"])
            if token_data.get("refresh_token"):
                self._token["refresh_token"] = token_data["refresh_token"]
            self._token["expires_at"] = time.time() + token_data.get("expires_in", 3600)
        return {"status": "ok"}

    def make_request(self, url: str, method: str = "GET", headers: dict | None = None,
                     body: str | None = None) -> dict:
        """Make an authenticated HTTP request using the current token."""
        cfg = self._get_config()
        if not cfg:
            return {"error": "OAuth2 not configured."}

        with self._lock:
            token = self._token.get("access_token", "")
            expires_at = self._token.get("expires_at", 0)

        if not token:
            return {"error": "No access token. Call write_oauth_exchange first."}

        # Auto-refresh if expired
        if time.time() >= expires_at:
            refresh_result = self.refresh_token()
            if refresh_result.get("status") != "ok":
                return refresh_result
            with self._lock:
                token = self._token.get("access_token", "")

        req_headers = {
            "Authorization": f"{cfg.get('auth_header', 'Bearer')} {token}",
        }
        if headers:
            req_headers.update(headers)

        try:
            data = body.encode() if body else None
            req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_body = resp.read().decode()
                return {"status": "ok", "status_code": resp.status, "body": resp_body}
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.read().decode()[:500]}"}
        except Exception as e:
            return {"error": str(e)}

    def status(self) -> dict:
        with self._lock:
            expires_at = self._token.get("expires_at", 0)
            remaining = max(0, int(expires_at - time.time())) if expires_at else 0
            return {
                "configured": bool(self._config),
                "has_token": bool(self._token.get("access_token")),
                "token_expires_in_seconds": remaining,
                "token_url": self._config.get("token_url", ""),
                "scopes": self._config.get("scopes", ""),
            }

    def _get_config(self) -> dict:
        with self._lock:
            return dict(self._config)


# ---------------------------------------------------------------------------
# RBAC — Role-Based Access Control
# ---------------------------------------------------------------------------

class RBACManager:
    """Simple RBAC: roles define which tool permissions (read/write/mutate) are allowed."""

    def __init__(self):
        self._lock = threading.Lock()
        self._roles: dict[str, list[str]] = {
            "admin": ["read", "write", "mutate"],
            "user": ["read", "write"],
            "viewer": ["read"],
        }
        self._current_role = "admin"
        self._load()

    def _load(self):
        try:
            if RBAC_FILE.exists():
                data = json.loads(RBAC_FILE.read_text())
                self._roles = data.get("roles", self._roles)
                self._current_role = data.get("current_role", "admin")
        except Exception:
            pass

    def _save(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            RBAC_FILE.write_text(json.dumps({
                "roles": self._roles,
                "current_role": self._current_role,
            }, indent=2))
        except Exception:
            pass

    def set_role(self, role: str) -> dict:
        with self._lock:
            if role not in self._roles:
                return {"status": "error", "error": f"Unknown role: {role}. Available: {list(self._roles.keys())}"}
            self._current_role = role
            self._save()
        return {"status": "ok", "role": role, "permissions": self._roles[role]}

    def define_role(self, name: str, permissions: list[str]) -> dict:
        if not permissions:
            return {"status": "error", "error": "Permissions list cannot be empty"}
        valid = {"read", "write", "mutate"}
        for p in permissions:
            if p not in valid:
                return {"status": "error", "error": f"Invalid permission: {p}. Valid: {valid}"}
        with self._lock:
            self._roles[name] = permissions
            self._save()
        return {"status": "ok", "role": name, "permissions": permissions}

    def check_permission(self, tool_name: str, tool_permission: str) -> bool:
        """Check if current role allows the given tool permission."""
        with self._lock:
            allowed = self._roles.get(self._current_role, ["read"])
        return tool_permission in allowed

    def status(self) -> dict:
        with self._lock:
            return {
                "roles": {k: v for k, v in self._roles.items()},
                "current_role": self._current_role,
                "current_permissions": self._roles.get(self._current_role, []),
            }


# ---------------------------------------------------------------------------
# HMAC Tool Signing
# ---------------------------------------------------------------------------

def _get_hmac_key() -> bytes:
    """Get or generate a persistent HMAC key."""
    try:
        if HMAC_KEY_FILE.exists():
            return bytes.fromhex(HMAC_KEY_FILE.read_text().strip())
        key = os.urandom(32)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        HMAC_KEY_FILE.write_text(key.hex())
        return key
    except Exception:
        return os.urandom(32)


def sign_tool_call(name: str, args_json: str) -> str:
    """Sign a tool call with HMAC-SHA256 for integrity verification."""
    key = _get_hmac_key()
    return hmac.new(key, f"{name}:{args_json}".encode(), "sha256").hexdigest()


def verify_tool_call(name: str, args_json: str, signature: str) -> bool:
    """Verify a signed tool call."""
    expected = sign_tool_call(name, args_json)
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_OAUTH: OAuth2Client | None = None
_RBAC: RBACManager | None = None


def get_oauth() -> OAuth2Client:
    global _OAUTH
    if _OAUTH is None:
        _OAUTH = OAuth2Client()
    return _OAUTH


def get_rbac() -> RBACManager:
    global _RBAC
    if _RBAC is None:
        _RBAC = RBACManager()
    return _RBAC


# ---------------------------------------------------------------------------
# MCP Tool definitions & handler
# ---------------------------------------------------------------------------

AUTH_TOOLS = [
    # OAuth2
    {
        "name": "write_oauth_configure",
        "description": " WRITE — Configure OAuth2 client (client_id, token_url, scopes).",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "client_secret": {"type": "string"},
                "token_url": {"type": "string"},
                "scopes": {"type": "string"},
            },
            "required": ["client_id", "token_url"],
        },
    },
    {
        "name": "write_oauth_exchange",
        "description": " WRITE — Exchange authorization code for tokens.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "redirect_uri": {"type": "string"},
            },
            "required": ["code", "redirect_uri"],
        },
    },
    {
        "name": "write_oauth_refresh",
        "description": " WRITE — Refresh the access token using refresh_token.",
        "permission": "write",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "write_oauth_request",
        "description": " WRITE — Make an authenticated HTTP request using the OAuth2 token.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                "headers": {"type": "object"},
                "body": {"type": "string"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "read_oauth_status",
        "description": " READ — View OAuth2 client configuration and token status.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    # RBAC
    {
        "name": "write_rbac_set_role",
        "description": " WRITE — Set the current RBAC role.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {"role": {"type": "string"}},
            "required": ["role"],
        },
    },
    {
        "name": "write_rbac_define_role",
        "description": " WRITE — Define a new RBAC role with permissions.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "permissions": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["read", "write", "mutate"]},
                },
            },
            "required": ["name", "permissions"],
        },
    },
    {
        "name": "read_rbac_status",
        "description": " READ — View RBAC roles and current role assignment.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    # Encryption
    {
        "name": "write_aes_encrypt",
        "description": " WRITE — Encrypt a string with AES-GCM-like cipher (stdlib-only). Returns IV, ciphertext, integrity tag.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {"plaintext": {"type": "string"}},
            "required": ["plaintext"],
        },
    },
    {
        "name": "write_aes_decrypt",
        "description": " WRITE — Decrypt data encrypted with write_aes_encrypt.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "iv": {"type": "string"},
                "ciphertext": {"type": "string"},
                "tag": {"type": "string"},
            },
            "required": ["iv", "ciphertext", "tag"],
        },
    },
]


def handle_tool_call(name: str, args: dict) -> dict:
    oauth = get_oauth()
    rbac = get_rbac()

    # OAuth2
    if name == "write_oauth_configure":
        return {"content": [{"type": "text", "text": json.dumps(oauth.configure(args))}]}
    elif name == "write_oauth_exchange":
        return {"content": [{"type": "text", "text": json.dumps(oauth.exchange_code(args.get("code", ""), args.get("redirect_uri", "")))}]}
    elif name == "write_oauth_refresh":
        return {"content": [{"type": "text", "text": json.dumps(oauth.refresh_token())}]}
    elif name == "write_oauth_request":
        return {"content": [{"type": "text", "text": json.dumps(oauth.make_request(
            url=args.get("url", ""),
            method=args.get("method", "GET"),
            headers=args.get("headers"),
            body=args.get("body"),
        ))}]}
    elif name == "read_oauth_status":
        return {"content": [{"type": "text", "text": json.dumps(oauth.status(), indent=2)}]}

    # RBAC
    elif name == "write_rbac_set_role":
        return {"content": [{"type": "text", "text": json.dumps(rbac.set_role(args.get("role", "")))}]}
    elif name == "write_rbac_define_role":
        return {"content": [{"type": "text", "text": json.dumps(rbac.define_role(args.get("name", ""), args.get("permissions", [])))}]}
    elif name == "read_rbac_status":
        return {"content": [{"type": "text", "text": json.dumps(rbac.status(), indent=2)}]}

    # Encryption
    elif name == "write_aes_encrypt":
        key = _get_hmac_key()
        result = _aes_encrypt(args.get("plaintext", ""), key)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    elif name == "write_aes_decrypt":
        key = _get_hmac_key()
        result = _aes_decrypt(args, key)
        if result is None:
            return {"content": [{"type": "text", "text": json.dumps({"error": "Decryption failed — integrity check failed or invalid data"})}]}
        return {"content": [{"type": "text", "text": json.dumps({"plaintext": result})}]}

    msg = "Unknown auth tool: " + str(name)
    return {"content": [{"type": "text", "text": json.dumps({"error": msg})}]}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Auth Module Self-Test ===\n")

    # 1. Encryption round-trip
    original = "Sensitive memory content with PII data"
    key = os.urandom(32)
    encrypted = _aes_encrypt(original, key)
    decrypted = _aes_decrypt(encrypted, key)
    print(f"1. Encryption: {original[:20]}... → {len(encrypted['ciphertext'])} hex chars → {decrypted[:20]}...")
    assert decrypted == original, f"Round-trip failed: {decrypted} != {original}"

    # 2. Tamper detection
    tampered = dict(encrypted)
    tampered["tag"] = "deadbeef" * 2
    result = _aes_decrypt(tampered, key)
    print(f"2. Tamper detection: {'PASS' if result is None else 'FAIL'}")
    assert result is None, "Tampered data should not decrypt"

    # 3. RBAC
    rbac = RBACManager()
    s0 = rbac.status()
    print(f"3. RBAC: {len(s0['roles'])} roles, current={s0['current_role']}")
    assert s0["current_role"] == "admin"
    assert s0["current_permissions"] == ["read", "write", "mutate"]

    rbac.set_role("viewer")
    assert not rbac.check_permission("some_tool", "write")
    assert rbac.check_permission("some_tool", "read")
    print(f"   Viewer: read={rbac.check_permission('t', 'read')}, write={rbac.check_permission('t', 'write')}")

    rbac.define_role("deployer", ["write", "read"])
    rbac.set_role("deployer")
    s2 = rbac.status()
    assert "deployer" in s2["roles"]
    print(f"   Deployer role: {s2['roles']['deployer']}")
    assert rbac.check_permission("t", "write")

    # 4. HMAC signing
    sig1 = sign_tool_call("read_memory_status", "{}")
    sig2 = sign_tool_call("read_memory_status", "{}")
    sig3 = sign_tool_call("write_memory_add", "{}")
    assert sig1 == sig2  # Same inputs = same signature
    assert sig1 != sig3  # Different inputs = different signature
    assert verify_tool_call("read_memory_status", "{}", sig1)
    assert not verify_tool_call("read_memory_status", '{"x":1}', sig1)
    print(f"4. HMAC: sig stable={sig1[:16]}..., verifies={verify_tool_call('read_memory_status', '{}', sig1)}")

    # 5. OAuth2 status (unconfigured)
    oauth = OAuth2Client()
    s = oauth.status()
    print(f"5. OAuth2: configured={s['configured']}, has_token={s['has_token']}")
    assert not s["configured"]
    assert not s["has_token"]

    oauth.configure({"client_id": "test", "token_url": "https://example.com/token"})
    s2 = oauth.status()
    print(f"   After config: configured={s2['configured']}")
    assert s2["configured"]

    # Cleanup: remove HMAC key file if created in test
    if HMAC_KEY_FILE.exists():
        HMAC_KEY_FILE.unlink()

    print("\nAll self-tests passed.")
