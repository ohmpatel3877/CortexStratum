#!/usr/bin/env python3
"""
Vector Quantizer — Storage-efficient memory encoding for CortexStratum MLM.

Compresses memory representations using three techniques:
  1. TAG CODEBOOK — maps tag strings → uint16 IDs (growing codebook, LZW-inspired)
  2. CONTENT DEDUP — SHA256 hash → single content store with refcounting
  3. SCORE BINNING — quantizes float importance scores to 4-bit bins (0-15)

All stdlib, zero dependencies.
"""

import hashlib
import json
import math
from typing import Any

# ---------------------------------------------------------------------------
# Tag Codebook (growing dictionary, uint16 IDs)
# ---------------------------------------------------------------------------

class TagCodebook:
    """Bi-directional mapping: tag string ↔ uint16 ID.

    Grows dynamically as new tags appear. IDs are compact (0..N-1)
    for efficient storage in integer arrays instead of string lists.
    """

    def __init__(self):
        self._tag_to_id: dict[str, int] = {}
        self._id_to_tag: dict[int, str] = {}

    def encode(self, tags: list[str]) -> list[int]:
        """Encode a list of tag strings to integer IDs, growing the codebook."""
        ids = []
        for tag in tags:
            if tag not in self._tag_to_id:
                tid = len(self._tag_to_id)
                self._tag_to_id[tag] = tid
                self._id_to_tag[tid] = tag
            ids.append(self._tag_to_id[tag])
        return ids

    def decode(self, ids: list[int]) -> list[str]:
        """Decode integer IDs back to tag strings."""
        return [self._id_to_tag.get(i, f"__unknown_{i}__") for i in ids]

    def stats(self) -> dict:
        return {
            "size": len(self._tag_to_id),
        }

    def get_state(self) -> dict:
        return {"tag_to_id": dict(self._tag_to_id), "id_to_tag": {str(k): v for k, v in self._id_to_tag.items()}}

    def load_state(self, state: dict):
        self._tag_to_id = state.get("tag_to_id", {})
        self._id_to_tag = {int(k): v for k, v in state.get("id_to_tag", {}).items()}


# ---------------------------------------------------------------------------
# Content Deduplicator (SHA256 hash → single store)
# ---------------------------------------------------------------------------

class ContentDeduplicator:
    """Deduplicate content by storing once and reference-counting.

    Uses the first 16 hex chars of SHA256 as the content key.
    """

    def __init__(self):
        self._store: dict[str, dict] = {}  # hash → {content, refcount, created}

    def store(self, content: Any) -> str:
        """Deduplicate content. Returns content hash."""
        c_str = json.dumps(content, sort_keys=True) if not isinstance(content, str) else content
        h = hashlib.sha256(c_str.encode("utf-8")).hexdigest()[:16]
        if h in self._store:
            self._store[h]["refcount"] += 1
        else:
            self._store[h] = {
                "content": content,
                "refcount": 1,
            }
        return h

    def release(self, content_hash: str) -> bool:
        """Decrement refcount. Returns True if entry was removed."""
        if content_hash not in self._store:
            return False
        self._store[content_hash]["refcount"] -= 1
        if self._store[content_hash]["refcount"] <= 0:
            del self._store[content_hash]
            return True
        return False

    def get(self, content_hash: str) -> Any | None:
        """Retrieve content by hash."""
        entry = self._store.get(content_hash)
        return entry["content"] if entry else None

    def stats(self) -> dict:
        return {
            "unique_items": len(self._store),
            "total_refs": sum(e["refcount"] for e in self._store.values()),
            "estimated_bytes": sum(
                len(json.dumps(e["content"])) for e in self._store.values()
            ),
        }


# ---------------------------------------------------------------------------
# Score Binner (quantize floats to 4-bit bins)
# ---------------------------------------------------------------------------

def quantize_score(score: float, bins: int = 16) -> int:
    """Quantize a 0.0–1.0 float to a 0..(bins-1) integer bin.

    Default 16 bins = 4 bits per score, vs 64-bit float.
    16× compression on scores.
    """
    score = max(0.0, min(1.0, score))
    return min(bins - 1, int(score * bins))


def dequantize_score(bin_val: int, bins: int = 16) -> float:
    """Reverse a quantized bin back to approximate float."""
    return (bin_val + 0.5) / bins


# ---------------------------------------------------------------------------
# Combined Vector Quantizer
# ---------------------------------------------------------------------------

class VectorQuantizer:
    """Storage-efficient encoder for memory items.

    Combines tag codebook, content dedup, and score binning.
    """

    def __init__(self):
        self.tags = TagCodebook()
        self.content = ContentDeduplicator()

    def encode_memory(self, item: dict) -> dict:
        """Encode a memory item dict into compact form.

        Input:  {"content": "...", "tags": ["a", "b"], "importance": 0.75, ...}
        Output: {"content_hash": "abc123", "tag_ids": [0, 1], "importance_bin": 12, ...}
        """
        encoded = {}

        # Content dedup
        content = item.get("content", "")
        encoded["content_hash"] = self.content.store(content)

        # Tag codebook
        tags = item.get("tags", [])
        encoded["tag_ids"] = self.tags.encode(tags)

        # Score binning
        importance = item.get("importance", 0.5)
        encoded["importance_bin"] = quantize_score(importance)

        # Pass through other fields unchanged
        for k in ("id", "layer", "created_at", "last_access", "access_count",
                  "ttl_seconds", "promotion_count", "source_session", "source_episodic_ids"):
            if k in item:
                encoded[k] = item[k]

        return encoded

    def decode_memory(self, encoded: dict) -> dict:
        """Reverse encoding back to human-readable form."""
        decoded = {}

        # Content from hash
        content_hash = encoded.get("content_hash", "")
        decoded["content"] = self.content.get(content_hash) or content_hash

        # Tags from IDs
        tag_ids = encoded.get("tag_ids", [])
        decoded["tags"] = self.tags.decode(tag_ids)

        # Dequantize score
        imp_bin = encoded.get("importance_bin", 8)
        decoded["importance"] = dequantize_score(imp_bin)

        # Pass through
        for k in ("id", "layer", "created_at", "last_access", "access_count",
                  "ttl_seconds", "promotion_count", "source_session", "source_episodic_ids"):
            if k in encoded:
                decoded[k] = encoded[k]

        return decoded

    def stats(self) -> dict:
        return {
            "tag_codebook": self.tags.stats(),
            "content_dedup": self.content.stats(),
            "estimated_total_bytes": self.content.stats()["estimated_bytes"],
        }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Vector Quantizer Self-Test ===\n")

    vq = VectorQuantizer()

    # 1. Tag codebook
    ids = vq.tags.encode(["docker", "networking", "debug"])
    print(f"1. Tag encode: {ids}")
    assert ids == [0, 1, 2]
    tags = vq.tags.decode(ids)
    print(f"   Tag decode: {tags}")
    assert tags == ["docker", "networking", "debug"]

    # 2. Content dedup (same content → same hash)
    h1 = vq.content.store("Debugged null pointer")
    h2 = vq.content.store("Debugged null pointer")
    print(f"2. Content dedup: h1={h1}, h2={h2}, same={h1 == h2}")
    assert h1 == h2

    # 3. Score binning
    bins = [quantize_score(s) for s in [0.0, 0.1, 0.25, 0.5, 0.75, 0.99, 1.0]]
    print(f"3. Score bins: {bins}")
    assert bins == [0, 1, 4, 8, 12, 15, 15]
    deq = [dequantize_score(b) for b in bins]
    print(f"   Dequantized: {[round(d, 3) for d in deq]}")

    # 4. Full encode/decode round trip
    original = {
        "id": "mem-001",
        "content": "Docker bridge networking requires port mapping",
        "tags": ["docker", "networking", "infra"],
        "importance": 0.85,
        "layer": "episodic",
        "created_at": 1000.0,
    }
    encoded = vq.encode_memory(original)
    print(f"4. Encoded: content_hash={encoded['content_hash']}, "
          f"tag_ids={encoded['tag_ids']}, "
          f"importance_bin={encoded['importance_bin']}")

    decoded = vq.decode_memory(encoded)
    print(f"   Decoded content: {decoded['content'][:40]}...")
    print(f"   Decoded tags: {decoded['tags']}")
    print(f"   Decoded importance: {decoded['importance']}")
    assert decoded["content"] == original["content"]
    assert decoded["tags"] == original["tags"]
    assert abs(decoded["importance"] - original["importance"]) < 0.04

    # 5. Stats
    s = vq.stats()
    print(f"5. Stats: codebook={s['tag_codebook']['size']}, "
          f"unique_content={s['content_dedup']['unique_items']}, "
          f"bytes={s['content_dedup']['estimated_bytes']}")
    assert s["tag_codebook"]["size"] == 4  # 3 from step 1 + 1 (infra) from step 4
    assert s["content_dedup"]["unique_items"] == 2  # from step 2 + step 4

    print("\nAll self-tests passed.")
