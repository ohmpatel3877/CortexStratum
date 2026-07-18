#!/usr/bin/env python3
"""Tool definition validator — checks TOOLS list integrity."""
import ast, sys, os, json, re

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(SCRIPTS, "tools-mcp-server.py")

def extract_tools_list():
    """Parse the TOOLS list via regex — handles A() and DR() calls that ast can't."""
    with open(SERVER, encoding="utf-8") as f:
        content = f.read()
    # Find TOOLS = [ ... ] block
    start = content.find("TOOLS = [")
    if start < 0:
        return []
    # Find matching closing bracket (naive depth count)
    depth = 0
    end = start
    for i in range(start, len(content)):
        if content[i] == "[":
            depth += 1
        elif content[i] == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    tools_text = content[start:end]
    # Extract each tool dict using regex
    tools = []
    pattern = r'\{\s*"name":\s*"([^"]+)"[^}]+"permission":\s*"([^"]+)"[^}]*\}'
    for match in re.finditer(pattern, tools_text):
        tools.append({"name": match.group(1), "permission": match.group(2)})
    return tools

def extract_dispatch_tools():
    """Extract tool names referenced in handle_tool_call dispatch."""
    with open(SERVER, encoding="utf-8") as f:
        content = f.read()
    tool_refs = set()
    for match in re.finditer(r'"(read_|write_|mutate_)\w+"', content):
        tool_refs.add(match.group(0).strip('"'))
    return tool_refs

def validate():
    errors = []

    try:
        tools = extract_tools_list()
        print(f"  Parsed {len(tools)} tool definitions")
    except Exception as e:
        print(f"  FAILED to parse TOOLS list: {e}")
        sys.exit(1)

    tool_names = set()
    for i, tool in enumerate(tools):
        if not isinstance(tool, dict):
            errors.append(f"  Tool at index {i} is not a dict: {type(tool).__name__}")
            continue
        name = tool.get("name", f"<index {i}>")
        tool_names.add(name)

        if "name" not in tool:
            errors.append(f"  Tool at index {i} missing 'name'")
        if "permission" not in tool:
            errors.append(f"  {name}: missing 'permission'")
        if "inputSchema" not in tool:
            errors.append(f"  {name}: missing 'inputSchema'")

    dispatch_tools = extract_dispatch_tools()
    for dt in dispatch_tools:
        if dt not in tool_names and not any(dt.startswith(p) for p in ["read_", "write_", "mutate_"]):
            continue
        if dt not in tool_names:
            errors.append(f"  DISPATCH REF '{dt}' has no TOOLS list entry")

    for tn in tool_names:
        if tn not in dispatch_tools:
            found = False
            with open(SERVER, encoding="utf-8") as f:
                content = f.read()
            parts = tn.split("_")
            if len(parts) >= 2:
                prefix = parts[0] + "_" + parts[1]
                if f'startswith("{prefix}")' in content:
                    found = True
            if not found:
                if f'"{tn}"' not in content:
                    errors.append(f"  TOOL '{tn}' defined but NEVER referenced in dispatch")

    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    {e}")
        sys.exit(1)
    else:
        print(f"\n  ALL {len(tools)} tools validated — dispatch complete, no errors")

if __name__ == "__main__":
    validate()
