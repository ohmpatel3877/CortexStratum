#!/usr/bin/env python3
"""
Limbic Emotional Tagging Module — Amygdala analog

Tags memories with emotional valence (positive/negative) and intensity,
influencing retrieval strength. Emotionally charged items are more salient
and easier to recall.

Analog: The amygdala tags experiences with emotional significance,
modulating memory consolidation and retrieval in the hippocampus and cortex.
"""

import json
import math
import time


class LimbicModule:
    """Emotional tagging layer for memory items.

    Each tag stores:
      - valence: -1.0 (negative) to +1.0 (positive)
      - intensity: 0.0 (neutral) to 1.0 (max)
      - created_at / last_access — for decay
      - source: who or what created the tag
    """

    def __init__(self, default_decay: int = 3600):
        self._tags: dict[str, list[dict]] = {}  # memory_key → list of tags
        self._reinforcement_log: list[dict] = []  # historical reinforcement events
        self._default_decay = default_decay  # seconds before a tag's influence halved

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def tag(self, memory_key: str, valence: float, intensity: float = 0.5,
            context: str = "", source: str = "user") -> dict:
        """Tag a memory with emotional metadata.

        Args:
            memory_key: The item/path/key to tag.
            valence: -1.0 (negative) to +1.0 (positive). 0 = neutral.
            intensity: 0.0–1.0 how strongly felt.
            context: Optional note on why tagged.
            source: Who created this tag.

        Returns:
            {"status": "ok", "key": key, "tag_count": N}
        """
        valence = max(-1.0, min(1.0, valence))
        intensity = max(0.0, min(1.0, intensity))
        now = time.time()

        tag = {
            "valence": valence,
            "intensity": intensity,
            "context": context,
            "source": source,
            "created_at": now,
            "last_access": now,
        }

        if memory_key not in self._tags:
            self._tags[memory_key] = []
        self._tags[memory_key].append(tag)
        return {"status": "ok", "key": memory_key, "tag_count": len(self._tags[memory_key])}

    def reinforce(self, key: str, outcome: str = "success",
                  delta: float = 0.15, reason: str = "",
                  source: str = "system") -> dict:
        """Reinforce or weaken a memory's emotional tag based on outcome.

        Behavioral loop: success → positive valence shift + intensity boost
                         failure → negative valence shift + intensity decay

        This is the feedback signal that turns static tagging into
        a reinforcement-learning-style loop.

        Args:
            key: The tagged memory key.
            outcome: "success" or "failure".
            delta: How much to shift (0.0–1.0).
            reason: Why this reinforcement happened.
            source: Who triggered it.
        """
        if key not in self._tags or not self._tags[key]:
            return {"status": "error", "error": f"No tags found for: {key}"}

        delta = max(0.0, min(1.0, delta))
        now = time.time()
        latest = self._tags[key][-1]  # most recent tag

        if outcome == "success":
            # Shift valence positive, boost intensity
            latest["valence"] = min(1.0, latest["valence"] + delta)
            latest["intensity"] = min(1.0, latest["intensity"] + delta * 0.5)
        elif outcome == "failure":
            # Shift valence negative, slightly decay intensity (weakened salience)
            latest["valence"] = max(-1.0, latest["valence"] - delta)
            latest["intensity"] = max(0.0, latest["intensity"] - delta * 0.3)
        else:
            return {"status": "error", "error": f"Unknown outcome: {outcome}"}

        latest["last_access"] = now
        latest["reinforced_at"] = now

        self._reinforcement_log.append({
            "key": key,
            "outcome": outcome,
            "delta": delta,
            "reason": reason,
            "source": source,
            "timestamp": now,
        })

        return {
            "status": "ok",
            "key": key,
            "outcome": outcome,
            "valence": round(latest["valence"], 3),
            "intensity": round(latest["intensity"], 3),
            "total_reinforcements": len(self._reinforcement_log),
        }

    def reinforcement_history(self, key: str | None = None,
                               limit: int = 20) -> list[dict]:
        """Return reinforcement event log, optionally filtered by key."""
        events = self._reinforcement_log
        if key:
            events = [e for e in events if e["key"] == key]
        return sorted(events, key=lambda e: e["timestamp"], reverse=True)[:limit]

    def retrieve(self, min_valence: float = -1.0, max_valence: float = 1.0,
                 min_intensity: float = 0.0, source: str | None = None,
                 limit: int = 20) -> list[dict]:
        """Retrieve tagged memories matching emotional filters.
        Salience = |valence| × intensity × recency_factor
        """
        now = time.time()
        results = []

        for key, tags in self._tags.items():
            # Compute aggregate emotional profile for this key
            if not tags:
                continue

            # Filter tags by criteria
            matched_tags = [t for t in tags
                           if min_valence <= t["valence"] <= max_valence
                           and t["intensity"] >= min_intensity
                           and (source is None or t["source"] == source)]
            if not matched_tags:
                continue

            # Aggregate
            avg_valence = sum(t["valence"] for t in matched_tags) / len(matched_tags)
            avg_intensity = sum(t["intensity"] for t in matched_tags) / len(matched_tags)
            latest = max(t["created_at"] for t in matched_tags)
            age_hours = (now - latest) / 3600
            recency = math.exp(-age_hours / (self._default_decay / 3600))
            salience = abs(avg_valence) * avg_intensity * recency

            results.append({
                "key": key,
                "tags": matched_tags,
                "avg_valence": round(avg_valence, 3),
                "avg_intensity": round(avg_intensity, 3),
                "tag_count": len(matched_tags),
                "age_hours": round(age_hours, 2),
                "salience": round(salience, 3),
            })

        # Sort by salience descending
        results.sort(key=lambda x: x["salience"], reverse=True)
        return results[:limit]

    def forget(self, memory_key: str | None = None,
               older_than_hours: float | None = None,
               source: str | None = None) -> dict:
        """Remove emotional tags.

        Args:
            memory_key: Remove tags for a specific key, or None for all.
            older_than_hours: Only remove tags older than this.
            source: Only remove tags from this source.

        Returns:
            {"status": "ok", "tags_removed": N}
        """
        removed = 0
        keys_to_process = [memory_key] if memory_key else list(self._tags.keys())

        for key in keys_to_process:
            if key not in self._tags:
                continue
            if older_than_hours is not None:
                cutoff = time.time() - older_than_hours * 3600
                before = len(self._tags[key])
                self._tags[key] = [t for t in self._tags[key]
                                  if t["created_at"] >= cutoff]
                removed += before - len(self._tags[key])
            elif source is not None:
                before = len(self._tags[key])
                self._tags[key] = [t for t in self._tags[key]
                                  if t["source"] != source]
                removed += before - len(self._tags[key])
            else:
                if memory_key:
                    removed += len(self._tags[key])
                    del self._tags[key]
                else:
                    # Count all remaining tags, then clear everything
                    total = sum(len(v) for v in self._tags.values())
                    removed += total
                    self._tags.clear()
                    break

        # Clean up empty keys
        empty_keys = [k for k, v in self._tags.items() if not v]
        for k in empty_keys:
            del self._tags[k]

        return {"status": "ok", "tags_removed": removed}

    def status(self) -> dict:
        """Return overall limbic system stats."""
        all_tags = sum(len(v) for v in self._tags.values())
        unique_keys = len(self._tags)

        if all_tags == 0:
            return {"tagged_keys": 0, "total_tags": 0, "valence_distribution": {}}

        # Distribution
        pos = neg = neu = 0
        for tags in self._tags.values():
            for t in tags:
                if t["valence"] > 0.3:
                    pos += 1
                elif t["valence"] < -0.3:
                    neg += 1
                else:
                    neu += 1

        # Most salient key
        salient = self.retrieve(limit=1)
        most_salient = salient[0]["key"] if salient else None

        return {
            "tagged_keys": unique_keys,
            "total_tags": all_tags,
            "valence_distribution": {
                "positive": pos,
                "negative": neg,
                "neutral": neu,
            },
            "most_salient_key": most_salient,
            "decay_window_hours": self._default_decay / 3600,
            "reinforcements_logged": len(self._reinforcement_log),
        }


# ---------------------------------------------------------------------------
# MCP Tool handlers
# ---------------------------------------------------------------------------

_LIMBIC: LimbicModule | None = None


def _get_limbic() -> LimbicModule:
    global _LIMBIC
    if _LIMBIC is None:
        _LIMBIC = LimbicModule()
    return _LIMBIC


def handle_tool_call(name: str, args: dict) -> dict:
    """Dispatch limbic MCP tool calls."""
    mod = _get_limbic()
    try:
        if name == "read_limbic_status":
            return {"content": [{"type": "text", "text": json.dumps(mod.status(), indent=2)}]}

        elif name == "write_limbic_tag":
            key = args.get("key", "")
            if not key:
                return {"content": [{"type": "text", "text": json.dumps({"error": "key is required"})}]}
            result = mod.tag(
                memory_key=key,
                valence=args.get("valence", 0.0),
                intensity=args.get("intensity", 0.5),
                context=args.get("context", ""),
                source=args.get("source", "user"),
            )
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "read_limbic_retrieve":
            result = mod.retrieve(
                min_valence=args.get("min_valence", -1.0),
                max_valence=args.get("max_valence", 1.0),
                min_intensity=args.get("min_intensity", 0.0),
                source=args.get("source"),
                limit=args.get("limit", 20),
            )
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "write_limbic_reinforce":
            key = args.get("key", "")
            if not key:
                return {"content": [{"type": "text", "text": json.dumps({"error": "key is required"})}]}
            result = mod.reinforce(
                key=key,
                outcome=args.get("outcome", "success"),
                delta=args.get("delta", 0.15),
                reason=args.get("reason", ""),
                source=args.get("source", "system"),
            )
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "read_limbic_reinforcements":
            result = mod.reinforcement_history(
                key=args.get("key"),
                limit=args.get("limit", 20),
            )
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        elif name == "mutate_limbic_forget":
            result = mod.forget(
                memory_key=args.get("key"),
                older_than_hours=args.get("older_than_hours"),
                source=args.get("source"),
            )
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        else:
            return {"content": [{"type": "text", "text": json.dumps({"error": f"Unknown limbic tool: {name}"})}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}]}


# ---------------------------------------------------------------------------
# Tool definitions for MCP registration
# ---------------------------------------------------------------------------

LIMBIC_TOOLS = [
    {
        "name": "read_limbic_status",
        "description": " READ — Show emotional tagging stats: tagged keys, total tags, valence distribution (positive/negative/neutral), most salient key.",
        "permission": "read",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "write_limbic_tag",
        "description": " WRITE — Tag a memory with emotional valence and intensity. Valence -1.0 to +1.0 (negative→positive), intensity 0.0 to 1.0. Accepts dry_run=true.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Memory key / path / identifier to tag"},
                "valence": {"type": "number", "description": "-1.0 (negative) to +1.0 (positive). 0 = neutral.", "default": 0.5},
                "intensity": {"type": "number", "description": "0.0–1.0 how strongly felt.", "default": 0.5},
                "context": {"type": "string", "description": "Optional context on why tagged"},
                "source": {"type": "string", "description": "Who created this tag", "default": "user"},
                "dry_run": {"type": "boolean"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "read_limbic_retrieve",
        "description": " READ — Retrieve tagged memories by emotional filter. Returns entries sorted by salience (emotional charge × recency). Filter by valence range, minimum intensity, or source.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "min_valence": {"type": "number", "description": "Minimum valence filter", "default": -1.0},
                "max_valence": {"type": "number", "description": "Maximum valence filter", "default": 1.0},
                "min_intensity": {"type": "number", "description": "Minimum intensity filter", "default": 0.0},
                "source": {"type": "string", "description": "Only tags from this source"},
                "limit": {"type": "integer", "description": "Max results", "default": 20},
            },
            "required": [],
        },
    },
    {
        "name": "write_limbic_reinforce",
        "description": " WRITE — Reinforce or weaken a memory's emotional tag based on outcome (success/failure). Creates a feedback loop: success → positive valence shift + intensity boost, failure → negative shift + decay.",
        "permission": "write",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Tagged memory key to reinforce"},
                "outcome": {"type": "string", "description": "\"success\" or \"failure\"", "default": "success"},
                "delta": {"type": "number", "description": "Shift magnitude (0.0–1.0)", "default": 0.15},
                "reason": {"type": "string", "description": "Why this reinforcement happened"},
                "source": {"type": "string", "description": "Who triggered it", "default": "system"},
                "dry_run": {"type": "boolean"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "read_limbic_reinforcements",
        "description": " READ — View reinforcement event history. Optionally filter by key. Shows outcome, delta, reason, and timestamp for each reinforcement event.",
        "permission": "read",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Filter by memory key (omit for all)"},
                "limit": {"type": "integer", "description": "Max events to return", "default": 20},
            },
            "required": [],
        },
    },
    {
        "name": "mutate_limbic_forget",
        "description": " MUTATE — Remove emotional tags. Can target a specific key, all tags older than N hours, or tags from a specific source. Accepts dry_run=true.",
        "permission": "mutate",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Remove tags only for this key (omitting removes all)"},
                "older_than_hours": {"type": "number", "description": "Only remove tags older than this many hours"},
                "source": {"type": "string", "description": "Only remove tags from this source"},
                "dry_run": {"type": "boolean"},
            },
            "required": [],
        },
    },
]


if __name__ == "__main__":
    # Self-test
    print("=== Limbic Module Self-Test ===\n")

    limbic = LimbicModule(default_decay=3600)

    # Tag some items
    r1 = limbic.tag("debug-session-20260721", valence=0.8, intensity=0.9,
                     context="Successfully fixed the deadlock!", source="agent")
    print(f"Tag positive: {r1}")
    assert r1["status"] == "ok"
    assert r1["tag_count"] == 1

    r2 = limbic.tag("crash-log-Q3", valence=-0.9, intensity=0.8,
                     context="Null pointer in production, very bad", source="agent")
    print(f"Tag negative: {r2}")
    assert r2["status"] == "ok"

    r3 = limbic.tag("readme-update", valence=0.1, intensity=0.2,
                     context="Routine doc update", source="user")
    print(f"Tag neutral: {r3}")

    # Status
    s = limbic.status()
    print(f"Status: {s['tagged_keys']} keys, {s['total_tags']} tags, dist={s['valence_distribution']}")
    assert s["tagged_keys"] == 3
    assert s["total_tags"] == 3
    assert s["valence_distribution"]["positive"] >= 1
    assert s["valence_distribution"]["negative"] >= 1

    # Retrieve positive only
    pos = limbic.retrieve(min_valence=0.3)
    print(f"Positive only: {len(pos)} results, top={pos[0]['key']}")
    assert len(pos) >= 1
    assert pos[0]["avg_valence"] > 0

    # Retrieve negative only
    neg = limbic.retrieve(max_valence=-0.3)
    print(f"Negative only: {len(neg)} results, top={neg[0]['key']}")
    assert len(neg) >= 1
    assert neg[0]["avg_valence"] < 0

    # --- Reinforcement Loop Tests ---

    # Reinforce success on the positive memory
    r4 = limbic.reinforce("debug-session-20260721", outcome="success", delta=0.2,
                           reason="Fix worked in production", source="verifier")
    print(f"Reinforce success: {r4}")
    assert r4["status"] == "ok"
    assert r4["valence"] > 0.8  # was 0.8, now > 1.0 (clamped)
    assert r4["intensity"] > 0.9  # was 0.9, now boosted
    assert r4["total_reinforcements"] == 1

    # Reinforce failure on the negative memory
    r5 = limbic.reinforce("crash-log-Q3", outcome="failure", delta=0.1,
                           reason="Root cause was different", source="agent")
    print(f"Reinforce failure: {r5}")
    assert r5["status"] == "ok"
    assert r5["valence"] < -0.9  # was -0.9, now -1.0 (clamped)

    # Reinforcement history
    hist = limbic.reinforcement_history(key="debug-session-20260721")
    print(f"Reinforcement history: {len(hist)} events")
    assert len(hist) == 1
    assert hist[0]["outcome"] == "success"

    # Reinforce on untagged key should error
    r6 = limbic.reinforce("nonexistent", outcome="success")
    print(f"Reinforce missing key: {r6}")
    assert r6["status"] == "error"

    # Status should show reinforcements
    s_reinf = limbic.status()
    print(f"Status reinforcements: {s_reinf['reinforcements_logged']}")
    assert s_reinf["reinforcements_logged"] == 2

    # --- End Reinforcement Tests ---

    # Forget specific key
    r7 = limbic.forget(memory_key="readme-update")
    print(f"Forget readme-update: {r7}")
    assert r7["tags_removed"] == 1

    s2 = limbic.status()
    print(f"After forget: {s2['tagged_keys']} keys")
    assert s2["tagged_keys"] == 2

    # Clear all
    r8 = limbic.forget()
    print(f"Forget all: {r8}")
    assert r8["tags_removed"] == 2

    s3 = limbic.status()
    print(f"After clear all: {s3['tagged_keys']} keys")
    assert s3["tagged_keys"] == 0

    print("\nAll self-tests passed.")
