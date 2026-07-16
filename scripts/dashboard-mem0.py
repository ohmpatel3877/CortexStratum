#!/usr/bin/env python3
"""Mem0 query helper for dashboard.ps1 - fetches recent memories via API."""
import json, os, sys, urllib.request

api_key = os.environ.get("MEM0_API_KEY", "")
count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
browse_filter = sys.argv[2] if len(sys.argv) > 2 else ""

url = f"https://api.mem0.ai/v3/memories/?user_id=ohmpa&app_id=ohmpa&limit={count}"
req = urllib.request.Request(url, headers={"Authorization": f"Token {api_key}"})
try:
    resp = urllib.request.urlopen(req, timeout=5)
    data = json.loads(resp.read())
    results = data.get("results", [])
    for m in results[:count]:
        meta = m.get("metadata", {}) or {}
        t = meta.get("type", "unknown")
        txt = m.get("memory", "")[:100].replace("\n", " ")
        created = m.get("createdAt", "")[:10]
        mid = m.get("id", "?")[:8]
        if browse_filter and browse_filter != "all" and t != browse_filter:
            continue
        print(f"{t}|{created}|{mid}|{txt}")
except Exception as e:
    # Silently fail - dashboard works without mem0
    pass
