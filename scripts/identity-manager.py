#!/usr/bin/env python3
"""
Identity Manager — Consolidate, store, and inject persona identity from mem0.

Reads memory profiles and mem0 entries, distills a structured identity
(persona, traits, principles, patterns), and generates session prompt
fragments for injection at session start.

Usage:
    python scripts/identity-manager.py --consolidate
    python scripts/identity-manager.py --render
    python scripts/identity-manager.py --get-trait thoroughness
    python scripts/identity-manager.py --log-behavior "pattern:text" --context "situation"
"""

import json, os, sys, shutil, subprocess
from datetime import datetime, timezone
from typing import Optional
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

# ── Paths ───────────────────────────────────────────────────

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
MEMORY_DIR = os.path.join(BASE, ".memory")
PROFILES_DIR = os.path.join(MEMORY_DIR, "profiles")
IDENTITY_DIR = os.path.join(MEMORY_DIR, "identity")
IDENTITY_HISTORY = os.path.join(IDENTITY_DIR, "history")
SCRIPTS_DIR = os.path.join(BASE, "scripts")
EVOLUTION_LOG = os.path.join(DATA, "identity-evolution-log.json")
IDENTITY_SCHEMA = os.path.join(DATA, "identity-schema.json")
CURRENT_IDENTITY = os.path.join(IDENTITY_DIR, "current-identity.json")

# ── Style ───────────────────────────────────────────────────

G = "\033[92m"; Y = "\033[93m"; B = "\033[94m"; M = "\033[95m"; R = "\033[91m"; C = "\033[96m"; N = "\033[0m"; BOLD = "\033[1m"
BAR = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Helpers ─────────────────────────────────────────────────

def ensure_dirs() -> None:
    """Create identity storage directories if they don't exist."""
    for d in [IDENTITY_DIR, IDENTITY_HISTORY]:
        os.makedirs(d, exist_ok=True)

def now_iso() -> str:
    """Return current UTC ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()

def _load_json(path: str, default=None):
    """Load JSON from path; return default on failure."""
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default if default is not None else {}

def _save_json(path: str, data, indent: int = 2) -> None:
    """Atomically write JSON to path using temp file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass

def _list_profiles() -> list[dict]:
    """Read all profile files from .memory/profiles/."""
    profiles = []
    if not os.path.isdir(PROFILES_DIR):
        return profiles
    for fname in sorted(os.listdir(PROFILES_DIR)):
        fpath = os.path.join(PROFILES_DIR, fname)
        if fname.endswith(".json"):
            data = _load_json(fpath, {})
            if isinstance(data, dict):
                data["_file"] = fname
                profiles.append(data)
        elif fname.endswith(".md"):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    profiles.append({"_file": fname, "text": f.read(), "source": "profile_md"})
            except Exception:
                pass
    return profiles

def _query_mem0_memories(category: Optional[str] = None, limit: int = 50) -> list[dict]:
    """Query mem0 via subprocess call to memory_search.py or direct file reads."""
    memories = []
    ne_dir = os.path.join(MEMORY_DIR, "ne")
    ne_json = os.path.join(ne_dir, "memories.json")
    if os.path.isfile(ne_json):
        data = _load_json(ne_json, [])
        if isinstance(data, list):
            for m in data:
                if category:
                    meta = m.get("metadata", {})
                    cats = meta.get("categories", meta.get("tags", ""))
                    if isinstance(cats, str) and category not in cats:
                        continue
                    if isinstance(cats, list) and category not in cats:
                        continue
                memories.append(m)
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "memory_search.py")],
            capture_output=True, text=True, timeout=10
        )
        _ = result
    except Exception:
        pass
    return memories[:limit]

def _read_mem0_md_categories() -> dict[str, str]:
    """Parse categories from .mem0.md for description mapping."""
    mem0_path = os.path.join(BASE, ".mem0.md")
    categories = {}
    if os.path.isfile(mem0_path):
        try:
            with open(mem0_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("- ") and ":" in line:
                        parts = line[2:].split(":", 1)
                        key = parts[0].strip()
                        val = parts[1].strip() if len(parts) > 1 else ""
                        categories[key] = val
        except Exception:
            pass
    return categories


class IdentityManager:
    """
    Core identity manager for persona persistence.

    Scans mem0 memories and profile files, distills structured identity,
    and renders session prompt fragments.
    """

    def __init__(self):
        ensure_dirs()

    # ── Consolidation ───────────────────────────────────────

    def consolidate_identity(self, persona_name: str = "default") -> dict:
        """
        Scan all memory sources and build/update identity profile.

        Algorithm:
        1. Count frequency of user_preferences entries → traits
        2. Extract anti_patterns → "things to avoid" behavioral notes
        3. Extract architecture_decisions → principles
        4. Calculate trait strengths from repetition + recency
        5. Merge into existing identity or create new

        Returns the consolidated identity dict.
        """
        profiles = _list_profiles()
        memories = _query_mem0_memories()
        categories = _read_mem0_md_categories()
        existing = self._load_current()

        # ── Extract principles from architecture decisions ──
        principles: list[dict] = []
        principle_counter: Counter = Counter()
        for mem in memories:
            meta = mem.get("metadata", {})
            cats = str(meta.get("categories", meta.get("tags", "")))
            text = mem.get("text", "")
            if "architecture_decisions" in cats or "architecture" in cats:
                p_text = text.split(".")[0].strip() if text else text
                principle_counter[p_text] += 1
        for p_text, count in principle_counter.most_common(10):
            rationale_cat = categories.get("architecture_decisions", "")
            principles.append({
                "principle": p_text[:200],
                "priority": len(principles) + 1,
                "rationale": f"Appeared {count}x in architecture decisions. {rationale_cat}"
            })

        # ── Extract traits from user_preferences ────────────
        trait_map: dict[str, list[str]] = {}
        pref_patterns = {
            "conciseness": ["concise", "brief", "short", "terse", "minimal", "succinct"],
            "thoroughness": ["thorough", "comprehensive", "detailed", "complete", "exhaustive"],
            "proactiveness": ["proactive", "anticipate", "before being asked", "initiative"],
            "formality": ["formal", "professional", "serious", "business", "corporate"],
            "directness": ["direct", "blunt", "straight", "no nonsense", "facts only"],
            "creativity": ["creative", "explore", "innovative", "novel", "imaginative"],
            "skepticism": ["skeptic", "verify", "doubt", "question", "cross-check"],
        }
        for mem in memories:
            meta = mem.get("metadata", {})
            cats = str(meta.get("categories", meta.get("tags", "")))
            text = mem.get("text", "")
            if "user_preferences" in cats:
                text_lower = text.lower()
                for trait, kws in pref_patterns.items():
                    if any(kw in text_lower for kw in kws):
                        if trait not in trait_map:
                            trait_map[trait] = []
                        ref = mem.get("id", mem.get("_file", text[:50]))
                        trait_map[trait].append(str(ref))

        for profile in profiles:
            text = profile.get("text", json.dumps(profile))
            text_lower = text.lower()
            for trait, kws in pref_patterns.items():
                if any(kw in text_lower for kw in kws):
                    if trait not in trait_map:
                        trait_map[trait] = []
                    trait_map[trait].append(profile.get("_file", "profile"))

        traits: list[dict] = []
        for trait, refs in trait_map.items():
            count = len(refs)
            strength = min(1.0, count * 0.15 + 0.1)
            traits.append({
                "trait": trait,
                "strength": round(strength, 2),
                "evidence": refs[:5]
            })
        traits.sort(key=lambda t: t["strength"], reverse=True)

        # ── Extract behavioral patterns ─────────────────────
        behavioral_patterns: list[dict] = []
        anti_pattern_count: Counter = Counter()
        seen_bp = set()
        for mem in memories:
            meta = mem.get("metadata", {})
            cats = str(meta.get("categories", meta.get("tags", "")))
            text = mem.get("text", "")
            if "anti_patterns" in cats:
                anti_pattern_count[text[:120]] += 1
        for bp_text, count in anti_pattern_count.most_common(8):
            key = bp_text[:60]
            if key not in seen_bp:
                seen_bp.add(key)
                behavioral_patterns.append({
                    "pattern": f"AVOID: {bp_text[:200]}",
                    "context": "anti_pattern",
                    "frequency": "often" if count >= 3 else "sometimes",
                    "last_observed": now_iso(),
                })

        # ── Knowledge boundaries ────────────────────────────
        strong_areas: Counter = Counter()
        weak_areas: Counter = Counter()
        for profile in profiles:
            text = profile.get("text", json.dumps(profile)).lower()
            for area in ["python", "typescript", "react", "api", "database", "testing",
                         "devops", "security", "frontend", "backend", "architecture",
                         "fastapi", "docker", "kubernetes", "electron", "tauri"]:
                if area in text:
                    strong_areas[area] += 1
        for mem in memories:
            meta = mem.get("metadata", {})
            cats = str(meta.get("categories", meta.get("tags", "")))
            text = mem.get("text", "").lower()
            if "anti_patterns" in cats or "weakness" in cats:
                for w in ["unfamiliar", "struggle", "weak", "gap", "missing"]:
                    if w in text:
                        weak_areas["unknown_area"] += 1

        recent_learnings = []
        for mem in memories[-20:]:
            meta = mem.get("metadata", {})
            cats = str(meta.get("categories", meta.get("tags", "")))
            if "task_learning" in cats or "session_summaries" in cats:
                text = mem.get("text", "")
                if text and len(text) > 20:
                    recent_learnings.append({
                        "topic": cats,
                        "insight": text[:300],
                        "added": mem.get("timestamp", now_iso()),
                    })
        recent_learnings = recent_learnings[-5:]

        # ── Communication style (evolving defaults) ─────────
        comm = self._infer_communication_style(traits, memories)

        # ── Build identity ──────────────────────────────────
        old_version = existing.get("version", "0.0.0")
        new_version = self._bump_version(old_version)

        identity = {
            "persona_name": persona_name,
            "version": new_version,
            "traits": traits,
            "principles": principles[:8],
            "behavioral_patterns": behavioral_patterns[:6],
            "communication_style": comm,
            "knowledge_boundaries": {
                "strong_areas": [a for a, _ in strong_areas.most_common(8)],
                "weak_areas": [a for a, _ in weak_areas.most_common(4)],
                "recent_learnings": recent_learnings,
            },
            "last_consolidated": now_iso(),
        }

        # ── Track evolution ─────────────────────────────────
        changes = self._diff_identity(existing, identity)
        self._record_evolution(new_version, changes)

        # ── Save ────────────────────────────────────────────
        self._save_identity(identity)
        self._archive_version(identity)

        return identity

    def _infer_communication_style(self, traits: list[dict], memories: list[dict]) -> dict:
        """Infer communication style from trait strengths and memory patterns."""
        trait_map = {t["trait"]: t["strength"] for t in traits}
        verbosity = round(0.3 + trait_map.get("thoroughness", 0.0) * 0.4, 2)
        formality = round(0.4 + trait_map.get("formality", 0.0) * 0.4, 2)
        technical_depth = round(0.6 + trait_map.get("thoroughness", 0.0) * 0.3, 2)
        humor_tolerance = round(0.5 - trait_map.get("formality", 0.0) * 0.3, 2)

        for mem in memories:
            text = mem.get("text", "").lower()
            if "verbos" in text:
                verbosity = min(1.0, verbosity + 0.1)
            if "casual" in text or "informal" in text:
                formality = max(0.0, formality - 0.1)
            if "humor" in text or "funny" in text:
                humor_tolerance = min(1.0, humor_tolerance + 0.1)

        return {
            "verbosity": min(1.0, verbosity),
            "formality": min(1.0, formality),
            "technical_depth": min(1.0, technical_depth),
            "humor_tolerance": min(1.0, humor_tolerance),
        }

    def _bump_version(self, current: str) -> str:
        """Bump patch version of semver string."""
        parts = current.split(".")
        try:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{major}.{minor}.{patch + 1}"
        except (ValueError, IndexError):
            return "1.0.0"

    def _diff_identity(self, old: dict, new: dict) -> list[str]:
        """Compare old and new identity and describe changes."""
        changes = []
        old_traits = {t["trait"]: t["strength"] for t in old.get("traits", [])}
        new_traits = {t["trait"]: t["strength"] for t in new.get("traits", [])}
        for trait, strength in new_traits.items():
            old_s = old_traits.get(trait, 0.0)
            diff = strength - old_s
            if abs(diff) > 0.1:
                direction = "strengthened" if diff > 0 else "weakened"
                changes.append(f"Trait '{trait}' {direction} from {old_s:.2f} to {strength:.2f}")
        old_principle_count = len(old.get("principles", []))
        new_principle_count = len(new.get("principles", []))
        if new_principle_count != old_principle_count:
            changes.append(f"Principles changed: {old_principle_count} → {new_principle_count}")
        old_pattern_count = len(old.get("behavioral_patterns", []))
        new_pattern_count = len(new.get("behavioral_patterns", []))
        if new_pattern_count != old_pattern_count:
            changes.append(f"Behavioral patterns changed: {old_pattern_count} → {new_pattern_count}")
        old_learnings = len(old.get("knowledge_boundaries", {}).get("recent_learnings", []))
        new_learnings = len(new.get("knowledge_boundaries", {}).get("recent_learnings", []))
        if new_learnings != old_learnings:
            changes.append(f"Recent learnings: {old_learnings} → {new_learnings}")
        if not changes:
            changes.append("Minor metadata refresh")
        return changes

    def _record_evolution(self, version: str, changes: list[str]) -> None:
        """Append a version entry to the evolution log."""
        log = _load_json(EVOLUTION_LOG, {"versions": []})
        if "versions" not in log:
            log["versions"] = []
        log["versions"].append({
            "version": version,
            "date": now_iso(),
            "changes_made": changes,
            "triggers": ["consolidation"],
        })
        _save_json(EVOLUTION_LOG, log)

    def _save_identity(self, identity: dict) -> None:
        """Save identity to current-identity.json."""
        _save_json(CURRENT_IDENTITY, identity)
        print(f"  {G}✓ Identity v{identity['version']} saved to {CURRENT_IDENTITY}{N}")

    def _archive_version(self, identity: dict) -> None:
        """Keep a timestamped copy in history/, prune to last 10."""
        ts = now_iso().replace(":", "-").replace(".", "-")
        path = os.path.join(IDENTITY_HISTORY, f"{ts}.json")
        _save_json(path, identity)
        all_versions = sorted(
            f for f in os.listdir(IDENTITY_HISTORY) if f.endswith(".json")
        )
        while len(all_versions) > 10:
            oldest = all_versions.pop(0)
            try:
                os.remove(os.path.join(IDENTITY_HISTORY, oldest))
            except Exception:
                pass

    def _load_current(self) -> dict:
        """Load current identity or return empty defaults."""
        return _load_json(CURRENT_IDENTITY, {})

    # ── Session Prompt Rendering ────────────────────────────

    def render_session_prompt(self) -> str:
        """
        Generate a markdown string for session start injection.

        Returns text like:
        ## Session Identity
        Persona: {name}
        Core Principles: {top 3}
        Behavioral Notes: {top 3}
        Recent Learnings: {top 2}
        """
        identity = self._load_current()
        if not identity.get("traits"):
            return self._render_empty_welcome()

        lines = ["## Session Identity"]
        lines.append(f"Persona: {identity.get('persona_name', 'default')}")

        # Top 3 principles
        principles = identity.get("principles", [])
        if principles:
            lines.append("Core Principles:")
            for p in principles[:3]:
                lines.append(f"- {p['principle'][:120]}")
        else:
            lines.append("Core Principles: (none consolidated yet)")

        # Behavioral notes — mix of top positive patterns + anti-patterns
        patterns = identity.get("behavioral_patterns", [])
        if patterns:
            lines.append("Behavioral Notes:")
            for bp in patterns[:3]:
                prefix = "🚫 " if "AVOID" in bp.get("pattern", "") else "✅ "
                lines.append(f"- {prefix}{bp['pattern'][:120]}")
        else:
            lines.append("Behavioral Notes: (none consolidated yet)")

        # Recent learnings
        learnings = identity.get("knowledge_boundaries", {}).get("recent_learnings", [])
        if learnings:
            lines.append("Recent Learnings:")
            for lr in learnings[-2:]:
                insight = lr.get("insight", "")[:150]
                lines.append(f"- {insight}")
        else:
            lines.append("Recent Learnings: (none recorded yet)")

        # Communication style hint
        cs = identity.get("communication_style", {})
        if cs:
            verb = "verbose" if cs.get("verbosity", 0.5) > 0.6 else "concise"
            formal = "formal" if cs.get("formality", 0.5) > 0.6 else "casual"
            lines.append(f"Style: {verb}, {formal}")

        return "\n".join(lines)

    def _render_empty_welcome(self) -> str:
        """Render a default prompt when no identity exists yet."""
        return (
            "## Session Identity\n"
            "Persona: (not yet consolidated)\n"
            "Core Principles: (none — run `consolidate_identity` first)\n"
            "Behavioral Notes: (none — run `consolidate_identity` first)\n"
            "Recent Learnings: (none — run `consolidate_identity` first)"
        )

    # ── Trait Accessor ──────────────────────────────────────

    def get_trait(self, trait_name: str) -> Optional[float]:
        """
        Return current strength of a named trait (0.0–1.0), or None if not found.

        Parameters
        ----------
        trait_name : str
            The trait name to look up (case-insensitive).

        Returns
        -------
        float or None
        """
        identity = self._load_current()
        for t in identity.get("traits", []):
            if t["trait"].lower() == trait_name.lower():
                return t["strength"]
        return None

    # ── Behavior Logger ─────────────────────────────────────

    def log_behavior(self, behavior_text: str, context: str = "") -> None:
        """
        Record a behavioral observation for next consolidation.

        The observation is appended to a local buffer file under
        `.memory/identity/behavior-log.json`.

        Parameters
        ----------
        behavior_text : str
            Description of the behavior observed.
        context : str
            Situational context in which it occurred.
        """
        log_path = os.path.join(IDENTITY_DIR, "behavior-log.json")
        entries = _load_json(log_path, [])
        if not isinstance(entries, list):
            entries = []
        entries.append({
            "behavior": behavior_text,
            "context": context,
            "observed": now_iso(),
        })
        # Keep last 200 entries
        entries = entries[-200:]
        _save_json(log_path, entries)
        print(f"  {G}✓ Behavior logged: {behavior_text[:80]}{N}")

    # ── Utility ─────────────────────────────────────────────

    def status(self) -> dict:
        """Return current identity status summary."""
        identity = self._load_current()
        history_count = 0
        if os.path.isdir(IDENTITY_HISTORY):
            history_count = len([f for f in os.listdir(IDENTITY_HISTORY) if f.endswith(".json")])
        return {
            "exists": bool(identity.get("traits")),
            "persona": identity.get("persona_name", "N/A"),
            "version": identity.get("version", "N/A"),
            "traits_count": len(identity.get("traits", [])),
            "principles_count": len(identity.get("principles", [])),
            "patterns_count": len(identity.get("behavioral_patterns", [])),
            "learnings_count": len(identity.get("knowledge_boundaries", {}).get("recent_learnings", [])),
            "last_consolidated": identity.get("last_consolidated", "N/A"),
            "history_versions": history_count,
        }


# ── CLI ─────────────────────────────────────────────────────

def print_status(status: dict) -> None:
    """Pretty-print identity status."""
    print(f"\n{C}{BAR}{N}")
    print(f"{C}{BOLD}  IDENTITY MANAGER STATUS{N}")
    print(f"{C}{BAR}{N}")
    if not status["exists"]:
        print(f"  {Y}No identity consolidated yet. Run --consolidate{N}")
        print()
        return
    print(f"  Persona:  {status['persona']}")
    print(f"  Version:  {status['version']}")
    print(f"  Traits:   {status['traits_count']}")
    print(f"  Principles: {status['principles_count']}")
    print(f"  Patterns: {status['patterns_count']}")
    print(f"  Learnings: {status['learnings_count']}")
    print(f"  Last consolidated: {status['last_consolidated'][:19]}")
    print(f"  History:  {status['history_versions']} archived versions")
    print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Identity Manager — persona persistence for cortex-stratum")
    parser.add_argument("--consolidate", action="store_true", help="Consolidate identity from mem0 memories")
    parser.add_argument("--render", action="store_true", help="Render session prompt fragment")
    parser.add_argument("--get-trait", type=str, metavar="TRAIT", help="Get strength of a named trait")
    parser.add_argument("--log-behavior", type=str, metavar="TEXT", help="Log a behavioral observation")
    parser.add_argument("--context", type=str, default="", help="Context for --log-behavior")
    parser.add_argument("--persona", type=str, default="default", help="Persona name for consolidation")
    parser.add_argument("--status", action="store_true", help="Show identity status")
    args = parser.parse_args()

    mgr = IdentityManager()

    if args.consolidate:
        print(f"\n{B}{BAR}{N}")
        print(f"{B}{BOLD}  CONSOLIDATING IDENTITY{N}")
        print(f"{B}{BAR}{N}")
        identity = mgr.consolidate_identity(persona_name=args.persona)
        print(f"\n  {G}✓ Done. Version {identity['version']} — {len(identity['traits'])} traits, "
              f"{len(identity['principles'])} principles{N}")
        print()

    elif args.render:
        prompt = mgr.render_session_prompt()
        print(prompt)

    elif args.get_trait:
        strength = mgr.get_trait(args.get_trait)
        if strength is not None:
            print(f"{strength:.2f}")
        else:
            print(f"none")
            sys.exit(1)

    elif args.log_behavior:
        mgr.log_behavior(args.log_behavior, context=args.context)

    elif args.status:
        print_status(mgr.status())

    else:
        print_status(mgr.status())
        print(f"  Usage: python scripts/identity-manager.py [--consolidate] [--render]")
        print(f"         [--get-trait <name>] [--log-behavior <text> --context <ctx>]")
        print(f"         [--status]")
        print()
