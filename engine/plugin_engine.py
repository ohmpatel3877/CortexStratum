#!/usr/bin/env python3
"""
Plugin Engine — dynamic loading, hot-reload, and management of CortexStratum plugins.

Plugins live in plugins/*.py. Each exports:
  - PLUGIN_INFO = {"name": str, "version": str, "description": str}
  - PLUGIN_TOOLS = [tool_dict, ...]
  - handle_tool_call(name, args) -> dict

Hot-reload: file mtime polling + importlib.reload().
"""

import importlib
import json
import sys
import threading
from pathlib import Path

# Default plugin directory (relative to this file's location)
_DEFAULT_PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugins"


class PluginManager:
    """Load, track, and hot-reload plugins."""

    def __init__(self, plugin_dir: str | Path | None = None):
        self._plugin_dir = Path(plugin_dir) if plugin_dir else _DEFAULT_PLUGIN_DIR
        self._plugin_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._plugins: dict[str, dict] = {}  # name → plugin metadata + module ref
        self._tool_registry: dict[str, str] = {}  # tool_name → plugin_name
        self._mtimes: dict[str, float] = {}  # file_path → mtime

        self._load_all()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_all(self):
        """Scan plugin directory and load all .py files (except __init__)."""
        sys.path.insert(0, str(self._plugin_dir.parent))  # so import can find plugins/
        for fpath in sorted(self._plugin_dir.glob("*.py")):
            if fpath.name.startswith("__"):
                continue
            self._load_one(fpath)

    def _load_one(self, fpath: Path) -> dict | None:
        """Load a single plugin file."""
        mod_name = f"plugins.{fpath.stem}"
        try:
            if mod_name in sys.modules:
                mod = importlib.reload(sys.modules[mod_name])
            else:
                spec = importlib.util.spec_from_file_location(mod_name, fpath)
                if spec is None or spec.loader is None:
                    return None
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)

            info = getattr(mod, "PLUGIN_INFO", {"name": fpath.stem, "version": "0.1.0"})
            name = info.get("name", fpath.stem)
            tools = getattr(mod, "PLUGIN_TOOLS", [])
            handler = getattr(mod, "handle_tool_call", None)

            if not handler:
                return None

            with self._lock:
                # Remove old tool registrations for this plugin
                for tname in list(self._tool_registry.keys()):
                    if self._tool_registry[tname] == name:
                        del self._tool_registry[tname]

                # Register new tools
                for t in tools:
                    tname = t.get("name", "")
                    if tname:
                        self._tool_registry[tname] = name

                self._plugins[name] = {
                    "name": name,
                    "version": info.get("version", "0.1.0"),
                    "description": info.get("description", ""),
                    "file": str(fpath),
                    "mtime": fpath.stat().st_mtime,
                    "tools": [t.get("name", "") for t in tools],
                    "handler": handler,
                    "mod": mod,
                }
                self._mtimes[str(fpath)] = fpath.stat().st_mtime

            return self._plugins[name]

        except Exception as e:
            return {"name": fpath.stem, "error": str(e)}

    # ------------------------------------------------------------------
    # Hot-reload (poll mtimes)
    # ------------------------------------------------------------------

    def check_reload(self) -> list[dict]:
        """Check for modified plugin files and reload them. Returns list of results."""
        results = []
        for fpath in sorted(self._plugin_dir.glob("*.py")):
            if fpath.name.startswith("__"):
                continue
            try:
                mtime = fpath.stat().st_mtime
                prev = self._mtimes.get(str(fpath), 0)
                if mtime > prev:
                    r = self._load_one(fpath)
                    results.append({"file": fpath.name, "reloaded": True, "status": "ok" if r else "error"})
            except Exception as e:
                results.append({"file": fpath.name, "error": str(e)})
        return results

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, name: str, args: dict) -> dict | None:
        """Route a tool call to the owning plugin. Returns None if no plugin handles it."""
        with self._lock:
            plugin_name = self._tool_registry.get(name)
            if plugin_name is None:
                return None
            plugin = self._plugins.get(plugin_name)
            if plugin is None:
                return None
            handler = plugin.get("handler")
            if handler is None:
                return None
        try:
            return handler(name, args)
        except Exception as e:
            return {"content": [{"type": "text", "text": json.dumps({"error": f"Plugin error ({plugin_name}): {e}"})}]}

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_plugins(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "name": p["name"],
                    "version": p["version"],
                    "description": p["description"],
                    "file": p["file"],
                    "tools": p["tools"],
                }
                for p in self._plugins.values()
            ]

    def plugin_tools(self) -> list[dict]:
        """Return combined TOOLS list from all plugins."""
        combined = []
        with self._lock:
            for p in self._plugins.values():
                mod = p.get("mod")
                if mod and hasattr(mod, "PLUGIN_TOOLS"):
                    combined.extend(mod.PLUGIN_TOOLS)
        return combined

    def reload_plugin(self, name: str) -> dict:
        """Reload a specific plugin by name."""
        with self._lock:
            for fpath in sorted(self._plugin_dir.glob("*.py")):
                if fpath.stem == name or fpath.stem.replace("_", "") == name.replace("_", ""):
                    r = self._load_one(fpath)
                    return {"status": "ok" if r else "error", "name": name, "file": fpath.name}
        return {"status": "error", "error": f"Plugin '{name}' not found"}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_MANAGER: PluginManager | None = None


def get_manager() -> PluginManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = PluginManager()
    return _MANAGER


# ---------------------------------------------------------------------------
# MCP Tool definitions
# ---------------------------------------------------------------------------

PLUGIN_TOOLS = [
    {
        "name": "read_plugin_list",
        "description": " READ — List all loaded plugins, their versions, and exported tools.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "write_plugin_reload",
        "description": " WRITE — Reload a plugin (or all if name omitted). Checks file mtime and re-imports.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Plugin name to reload. Omit to reload all changed."},
            },
            "required": [],
        },
    },
    {
        "name": "write_plugin_scan",
        "description": " WRITE — Scan the plugins/ directory for new .py files and load them.",
        "permission": "write",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


def handle_tool_call(name: str, args: dict) -> dict:
    mgr = get_manager()
    if name == "read_plugin_list":
        return {"content": [{"type": "text", "text": json.dumps(mgr.list_plugins(), indent=2)}]}
    elif name == "write_plugin_reload":
        pname = args.get("name", "")
        if pname:
            r = mgr.reload_plugin(pname)
        else:
            results = mgr.check_reload()
            r = {"status": "ok", "reloaded": len([x for x in results if x.get("reloaded")])}
        return {"content": [{"type": "text", "text": json.dumps(r, indent=2)}]}
    elif name == "write_plugin_scan":
        r = mgr.check_reload()
        return {"content": [{"type": "text", "text": json.dumps({"status": "ok", "results": r}, indent=2)}]}
    msg = "Unknown plugin tool: " + str(name)
    return {"content": [{"type": "text", "text": json.dumps({"error": msg})}]}


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile

    print("=== Plugin Engine Self-Test ===\n")

    # Use a temp plugin dir
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir)

        # Write a test plugin
        test_plugin = '''#!/usr/bin/env python3
"""test_plugin — test"""
PLUGIN_INFO = {"name": "test_plugin", "version": "1.0.0", "description": "Test plugin"}

PLUGIN_TOOLS = [
    {
        "name": "read_test_greet",
        "description": "Returns a greeting",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]

def handle_tool_call(name, args):
    return {"content": [{"type": "text", "text": '{"greeting": "hello from test_plugin"}'}]}
'''
        plugin_file = plugin_dir / "test_plugin.py"
        plugin_file.write_text(test_plugin)

        mgr = PluginManager(plugin_dir)

        # 1. List plugins
        pl = mgr.list_plugins()
        print(f"1. Plugins loaded: {len(pl)}")
        assert len(pl) == 1
        assert pl[0]["name"] == "test_plugin"
        assert "read_test_greet" in pl[0]["tools"]

        # 2. Dispatch
        r = mgr.dispatch("read_test_greet", {})
        print(f"2. Dispatch: {r['content'][0]['text']}")
        assert r is not None
        assert 'test_plugin' in r['content'][0]['text']

        # 3. Unknown tool
        r2 = mgr.dispatch("nonexistent", {})
        print(f"3. Unknown: {r2}")
        assert r2 is None

        # 4. Plugin tools list
        pt = mgr.plugin_tools()
        print(f"4. Plugin tools: {len(pt)}")
        assert len(pt) == 1
        assert pt[0]["name"] == "read_test_greet"

        print("\nAll self-tests passed.")
