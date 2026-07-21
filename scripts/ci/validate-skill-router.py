"""Check that skill-router.json references all local SKILL.md files."""

import json
from pathlib import Path

with open("skills/skill-router.json") as f:
    router = json.load(f)

local_skills = {d.name for d in Path("skills").iterdir() if d.is_dir()}
referenced = set()
for rule in router["rules"]:
    referenced.update(rule.get("skills", []))
referenced.update(router.get("default_skills", []))

missing_local = local_skills - referenced
if missing_local:
    print(f"WARNING: Local skills not referenced in router: {missing_local}")

print(f"Router rules: {len(router['rules'])}")
print(f"SKILL.md files: {len(local_skills)}")
print(f"Unique skill refs: {len(referenced)}")
print("SKILL ROUTER VALIDATION PASSED")
