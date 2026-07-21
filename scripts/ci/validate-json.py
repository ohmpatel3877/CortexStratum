"""Validate all JSON config files parse correctly."""

import json
import sys

files = [
    "skills/skill-router.json",
    "package.json",
    ".opencode/active-skills.json",
    "opencode.json",
]
for f in files:
    try:
        with open(f) as fh:
            json.load(fh)
        print(f"OK: {f}")
    except Exception as e:
        print(f"FAIL: {f} - {e}")
        sys.exit(1)
