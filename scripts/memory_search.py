#!/usr/bin/env python3
"""BM25 memory search with SQLite+FTS5 backend, optional vector/hybrid search,
cross-encoder reranking, and LRU query cache. Zero LLM calls, zero GPU required.

Architecture:
  - SQLite + FTS5 for BM25 full-text search (stdlib, no deps)
  - Optional vector search via sentence-transformers + numpy
  - Optional cross-encoder reranker for precision-critical queries
  - FTS5 MATCH with built-in BM25 ranking
  - LRU query cache for repeated queries
  - WAL mode for concurrent reads
"""

import json
import os
import sqlite3
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from difflib import get_close_matches
from pathlib import Path

# Optional deps — graceful fallback
try:
    import numpy as np

    _NUMPY_AVAILABLE = True
except ImportError:
    np = None
    _NUMPY_AVAILABLE = False

try:
    import sentence_transformers as st

    _SENTENCE_AVAILABLE = True
except ImportError:
    st = None
    _SENTENCE_AVAILABLE = False


class LRUCache:
    """128-entry LRU query cache. Evicts least-recently-used when full."""

    def __init__(self, maxsize: int = 128):
        self._maxsize = maxsize
        self._cache: OrderedDict[str, tuple[float, object]] = OrderedDict()

    def get(self, key: str) -> object | None:
        if key not in self._cache:
            return None
        val = self._cache.pop(key)
        self._cache[key] = val
        return val[1]

    def put(self, key: str, value: object):
        if key in self._cache:
            self._cache.pop(key)
        elif len(self._cache) >= self._maxsize:
            self._cache.popitem(last=False)
        self._cache[key] = (time.time(), value)

    def invalidate(self):
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)


STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "was",
    "are",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "shall",
    "can",
    "need",
    "dare",
    "ought",
    "used",
    "this",
    "that",
    "these",
    "those",
    "i",
    "me",
    "my",
    "we",
    "our",
    "you",
    "your",
    "he",
    "him",
    "his",
    "she",
    "her",
    "it",
    "its",
    "they",
    "them",
    "their",
    "what",
    "which",
    "who",
    "whom",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "every",
    "both",
    "few",
    "more",
    "most",
    "some",
    "any",
    "no",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "because",
    "if",
    "then",
    "else",
    "up",
    "down",
    "out",
    "about",
    "into",
    "over",
    "after",
    "before",
    "between",
    "under",
    "again",
    "further",
    "once",
    "here",
    "there",
}


class NEMemorySearch:
    """Memory search engine backed by SQLite+FTS5.

    Public API (unchanged):
        search(), vector_search(), hybrid_search(), reranked_search(),
        synthesize(), add_memory(), consolidate(), status(), cache_status()
    """

    def __init__(self, storage_path: str = ""):
        if not storage_path:
            base = Path(__file__).resolve().parent.parent / ".memory" / "ne"
            storage_path = str(base)
        self.storage_path = storage_path.replace("/", os.sep)
        self.synonyms_path = os.path.join(self.storage_path, "data", "synonyms.json")
        self.db_path = os.path.join(self.storage_path, "memory.db")
        self.k1 = 1.2
        self.b = 0.75
        self.synonyms = {}
        self._synonym_groups = {}
        self._vector_model = None
        self._vectors = None
        self._vector_ids = []
        self._reranker = None
        self._query_cache = LRUCache(maxsize=128)
        self._lock = threading.Lock()
        self._local = threading.local()

        self._load_synonyms()
        self._init_db()
        self._migrate_from_json()

    # ── SQLite Connection (thread-local) ──────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        """Get a thread-local SQLite connection with WAL mode."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        """Create tables if they don't exist."""
        os.makedirs(self.storage_path, exist_ok=True)
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                source TEXT DEFAULT 'manual',
                timestamp TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                vector BLOB
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                text, source, metadata,
                content='memories',
                content_rowid='rowid',
                tokenize='porter unicode61'
            );

            CREATE TABLE IF NOT EXISTS synonyms (
                term TEXT PRIMARY KEY,
                synonyms TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            -- Triggers to keep FTS in sync
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, text, source, metadata)
                VALUES (new.rowid, new.text, new.source, new.metadata);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, text, source, metadata)
                VALUES ('delete', old.rowid, old.text, old.source, old.metadata);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, text, source, metadata)
                VALUES ('delete', old.rowid, old.text, old.source, old.metadata);
                INSERT INTO memories_fts(rowid, text, source, metadata)
                VALUES (new.rowid, new.text, new.source, new.metadata);
            END;
        """)
        conn.commit()

    # ── Migration from old JSON format ───────────────────────────────

    def _migrate_from_json(self):
        """Import memories from legacy memories.json if it exists and DB is empty."""
        json_path = os.path.join(self.storage_path, "memories.json")
        if not os.path.isfile(json_path):
            return
        conn = self._get_conn()
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        if count > 0:
            return  # DB already populated
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return
            imported = 0
            for entry in data:
                text = entry.get("text", "")
                if not text:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO memories (id, text, source, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
                    (
                        entry.get("id", str(uuid.uuid4())),
                        text,
                        entry.get("source", "manual"),
                        entry.get("timestamp", datetime.now(timezone.utc).isoformat()),
                        json.dumps(entry.get("metadata", {})),
                    ),
                )
                imported += 1
            conn.commit()
            # Rename old file to prevent re-import
            os.rename(json_path, json_path + ".imported")
            print(
                f"[memory_search] Migrated {imported} entries from memories.json to SQLite"
            )
        except Exception as e:
            print(f"[memory_search] Migration error: {e}")

    # ── Synonyms (unchanged from original) ────────────────────────────

    def _load_synonyms(self):
        try:
            if os.path.isfile(self.synonyms_path):
                with open(self.synonyms_path, encoding="utf-8") as f:
                    self.synonyms = json.load(f)
            self._build_synonym_groups()
        except Exception:
            self.synonyms = {}
            self._synonym_groups = {}

    def _build_synonym_groups(self):
        groups = {}
        for key, syns in self.synonyms.items():
            group = set([key] + syns)
            for term in group:
                t = term.lower().strip()
                if t not in groups:
                    groups[t] = set()
                groups[t].update(group)
        self._synonym_groups = groups

    def _tokenize(self, text: str) -> list:
        tokens = []
        for raw in text.lower().split():
            cleaned = "".join(c for c in raw if c.isalnum())
            if cleaned and cleaned not in STOPWORDS:
                tokens.append(cleaned)
        return tokens

    def _expand_synonyms(self, tokens: list) -> list:
        expanded = []
        seen = set()
        for t in tokens:
            if t in self._synonym_groups:
                for syn in self._synonym_groups[t]:
                    if syn not in seen:
                        expanded.append(syn)
                        seen.add(syn)
            else:
                if t not in seen:
                    expanded.append(t)
                    seen.add(t)
        return expanded

    def _fuzzy_match(self, term, all_terms):
        if not all_terms:
            return []
        return get_close_matches(term, all_terms, n=3, cutoff=0.85)

    def _get_all_terms(self) -> set:
        """Get all unique indexed terms from FTS5 content table."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT DISTINCT text FROM memories WHERE text != ''"
        ).fetchall()
        terms = set()
        for row in rows:
            terms.update(self._tokenize(row["text"]))
        return terms

    # ── BM25 Search via FTS5 ─────────────────────────────────────────

    def search(
        self, query: str, limit: int = 10, fuzzy_threshold: float = 0.85
    ) -> list:
        if not query:
            return []
        cache_key = f"bm25:{query}:{limit}:{fuzzy_threshold}"
        cached = self._query_cache.get(cache_key)
        if cached is not None:
            return cached

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Expand synonyms first
        expanded = self._expand_synonyms(query_tokens)

        # Fuzzy match against corpus
        all_terms = self._get_all_terms()
        fuzzy_extra = set()
        for t in expanded:
            for m in self._fuzzy_match(t, all_terms):
                fuzzy_extra.add(m)
        all_query_terms = list(set(expanded) | fuzzy_extra)

        if not all_query_terms:
            return []

        conn = self._get_conn()

        # Build FTS5 query: terms joined with OR
        fts_query = " OR ".join(f'"{t}"' for t in all_query_terms)

        try:
            rows = conn.execute(
                """SELECT m.id, m.text, m.source, m.timestamp, m.metadata,
                          rank AS bm25_raw
                   FROM memories_fts
                   WHERE memories_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (fts_query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            # FTS5 syntax error — fallback to LIKE
            like_terms = all_query_terms[:5]
            like_clauses = " OR ".join("m.text LIKE ?" for _ in like_terms)
            params = [f"%{t}%" for t in like_terms]
            params.append(limit)
            rows = conn.execute(
                f"""SELECT m.id, m.text, m.source, m.timestamp, m.metadata,
                           0.0 AS bm25_raw
                    FROM memories m
                    WHERE {like_clauses}
                    LIMIT ?""",
                params,
            ).fetchall()

        results = []
        for row in rows:
            raw = row["bm25_raw"]
            if raw is None:
                score = 1.0
            else:
                # FTS5 rank: lower = better. Convert to similarity 0-1.
                score = 1.0 / (1.0 + abs(float(raw)))
            results.append(
                {
                    "text": row["text"],
                    "score": round(score, 4),
                    "source": row["source"],
                    "timestamp": row["timestamp"],
                    "id": row["id"],
                }
            )

        self._query_cache.put(cache_key, results)
        return results

    # ── Vector Search (vectors stored as BLOBs in SQLite) ────────────

    def vector_available(self) -> bool:
        return _NUMPY_AVAILABLE and _SENTENCE_AVAILABLE

    def _load_vector_model(self):
        if self._vector_model is not None:
            return True
        if not self.vector_available():
            return False
        try:
            model_name = os.environ.get("AI_MEMORY_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            self._vector_model = st.SentenceTransformer(model_name)
            return True
        except Exception:
            return False

    def _load_vectors_from_db(self):
        """Load all vectors from SQLite into memory."""
        if not _NUMPY_AVAILABLE:
            return
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, vector FROM memories WHERE vector IS NOT NULL"
        ).fetchall()
        if not rows:
            self._vectors = None
            self._vector_ids = []
            return
        vecs = []
        ids = []
        for row in rows:
            blob = row["vector"]
            if blob:
                vecs.append(np.frombuffer(blob, dtype=np.float32))
                ids.append(row["id"])
        if vecs:
            self._vectors = np.array(vecs)
            self._vector_ids = ids
        else:
            self._vectors = None
            self._vector_ids = []

    def _compute_vectors(self):
        """Compute vectors for all memories without one and save to DB."""
        if not self._load_vector_model():
            self._vectors = None
            self._vector_ids = []
            return
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, text FROM memories WHERE vector IS NULL"
        ).fetchall()
        if not rows:
            self._load_vectors_from_db()
            return
        texts = [r["text"] for r in rows]
        ids = [r["id"] for r in rows]
        try:
            new_vecs = self._vector_model.encode(texts, show_progress_bar=False)
            for i, mem_id in enumerate(ids):
                blob = new_vecs[i].astype(np.float32).tobytes()
                conn.execute(
                    "UPDATE memories SET vector = ? WHERE id = ?", (blob, mem_id)
                )
            conn.commit()
            self._load_vectors_from_db()
        except Exception:
            self._vectors = None
            self._vector_ids = []

    def vector_search(self, query: str, limit: int = 10) -> list | dict:
        if not self._load_vector_model():
            return {
                "error": "Vector search unavailable. Install: pip install sentence-transformers numpy"
            }
        conn = self._get_conn()
        count = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE vector IS NOT NULL"
        ).fetchone()[0]
        if count == 0:
            self._compute_vectors()
        # Reload if needed
        if self._vectors is None or len(self._vectors) == 0:
            self._load_vectors_from_db()
        if self._vectors is None or len(self._vectors) == 0:
            return {"error": "No vectors available"}
        try:
            query_vec = self._vector_model.encode([query])[0]
            if self._vectors.shape[1] != query_vec.shape[0]:
                self._compute_vectors()
                query_vec = self._vector_model.encode([query])[0]
        except Exception:
            return {"error": "Query encoding failed"}
        scores = []
        for i, vec in enumerate(self._vectors):
            sim = float(
                np.dot(query_vec, vec)
                / (np.linalg.norm(query_vec) * np.linalg.norm(vec) + 1e-10)
            )
            scores.append((sim, i))
        scores.sort(key=lambda x: x[0], reverse=True)

        # Fetch full memory details for top results
        conn = self._get_conn()
        results = []
        for sim, idx in scores[:limit]:
            mem_id = self._vector_ids[idx]
            row = conn.execute(
                "SELECT text, source, timestamp FROM memories WHERE id = ?", (mem_id,)
            ).fetchone()
            if row:
                results.append(
                    {
                        "text": row["text"],
                        "score": round(sim, 4),
                        "source": row["source"],
                        "timestamp": row["timestamp"],
                        "id": mem_id,
                    }
                )
            else:
                results.append(
                    {
                        "text": "(deleted)",
                        "score": round(sim, 4),
                        "source": "unknown",
                        "timestamp": "",
                        "id": mem_id,
                    }
                )
        return results

    # ── Cross-Encoder Reranker (unchanged) ───────────────────────────

    def _load_reranker(self):
        if getattr(self, "_reranker", None) is not None:
            return True
        if not _SENTENCE_AVAILABLE:
            return False
        try:
            model_name = os.environ.get(
                "AI_MEMORY_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
            )
            self._reranker = st.CrossEncoder(model_name)
            return True
        except Exception:
            self._reranker = None
            return False

    def reranked_search(self, query: str, limit: int = 5, candidates: int = 20) -> dict:
        initial = self.hybrid_search(query, limit=candidates)
        results_list = initial.get("results", []) if isinstance(initial, dict) else []
        if not results_list:
            return {"results": [], "method": "reranked"}
        if not self._load_reranker():
            return {
                "results": results_list[:limit],
                "method": "hybrid_only",
                "reranker": "unavailable (pip install sentence-transformers)",
            }
        try:
            pairs = [(query, r["text"]) for r in results_list]
            scores = self._reranker.predict(pairs)
            for i, score in enumerate(scores):
                results_list[i]["rerank_score"] = round(float(score), 4)
            results_list.sort(key=lambda r: r.get("rerank_score", 0), reverse=True)
            return {
                "results": results_list[:limit],
                "method": "reranked",
                "reranker": os.environ.get(
                    "AI_MEMORY_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
                ),
            }
        except Exception as e:
            return {
                "results": results_list[:limit],
                "method": "hybrid_only",
                "reranker": f"error: {e}",
            }

    # ── Hybrid Search (BM25 + Vector RRF) ────────────────────────────

    def hybrid_search(
        self,
        query,
        limit=10,
        bm25_weight=0.5,
        vector_weight=0.5,
        rrf_k=60,
    ):
        bm25_results = self.search(query, limit=limit * 2)
        bm25_map = {r["id"]: r for r in bm25_results}
        vec_results = self.vector_search(query, limit=limit * 2)
        vec_available = isinstance(vec_results, list)
        vec_map = {r["id"]: r for r in vec_results} if vec_available else {}

        if not vec_available:
            return {
                "results": [
                    {
                        **r,
                        "bm25_score": r["score"],
                        "vector_score": 0.0,
                        "bm25_rank": i + 1,
                        "vector_rank": None,
                    }
                    for i, r in enumerate(bm25_results[:limit])
                ],
                "method": "bm25_only",
                "note": "Vector search unavailable",
            }

        all_ids = list(
            dict.fromkeys(
                [r["id"] for r in bm25_results] + [r["id"] for r in vec_results]
            )
        )
        scored = []
        for doc_id in all_ids:
            rrf_score = 0.0
            bm25_rank = None
            vec_rank = None
            if doc_id in bm25_map:
                bm25_rank = (
                    next(i for i, r in enumerate(bm25_results) if r["id"] == doc_id) + 1
                )
                rrf_score += bm25_weight * (1.0 / (rrf_k + bm25_rank))
            if doc_id in vec_map:
                vec_rank = (
                    next(i for i, r in enumerate(vec_results) if r["id"] == doc_id) + 1
                )
                rrf_score += vector_weight * (1.0 / (rrf_k + vec_rank))
            src = bm25_map.get(doc_id) or vec_map.get(doc_id) or {}
            scored.append(
                {
                    "text": src["text"],
                    "score": round(rrf_score, 4),
                    "bm25_score": bm25_map[doc_id]["score"]
                    if doc_id in bm25_map
                    else 0.0,
                    "vector_score": vec_map[doc_id]["score"]
                    if doc_id in vec_map
                    else 0.0,
                    "bm25_rank": bm25_rank,
                    "vector_rank": vec_rank,
                    "source": src.get("source", "unknown"),
                    "timestamp": src.get("timestamp", ""),
                    "id": doc_id,
                }
            )
        scored.sort(key=lambda x: x["score"], reverse=True)
        return {
            "results": scored[:limit],
            "method": "hybrid_rrf",
            "bm25_weight": bm25_weight,
            "vector_weight": vector_weight,
            "rrf_k": rrf_k,
            "bm25_results_count": len(bm25_results),
            "vector_results_count": len(vec_results),
        }

    # ── Aggregate Methods ─────────────────────────────────────────────

    def synthesize(self, query, max_sources=5, min_confidence=0.7):
        results = self.search(query, limit=max_sources)
        sources = [r for r in results if r["score"] >= min_confidence]
        if not sources:
            max_score = max(r["score"] for r in results) if results else 0.0
            if results and max_score > 0:
                sources = results[:1]
            else:
                return {
                    "query": query,
                    "synthesis": "",
                    "sources": [],
                    "confidence": 0.0,
                }
        parts = [f"[{i}] {s['text']}" for i, s in enumerate(sources, 1)]
        avg_c = round(sum(s["score"] for s in sources) / len(sources), 4)
        return {
            "query": query,
            "synthesis": " ".join(parts),
            "sources": sources,
            "confidence": avg_c,
        }

    def add_memory(self, text, source="manual", metadata=None):
        mem_id = str(uuid.uuid4())
        entry = {
            "id": mem_id,
            "text": text,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self._query_cache.invalidate()
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO memories (id, text, source, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
            (
                mem_id,
                text,
                source,
                entry["timestamp"],
                json.dumps(entry["metadata"]),
            ),
        )
        conn.commit()

        # Compute vector for new memory if model is loaded
        if self._load_vector_model() and _NUMPY_AVAILABLE:
            try:
                nv = self._vector_model.encode([text])[0]
                blob = nv.astype(np.float32).tobytes()
                conn.execute(
                    "UPDATE memories SET vector = ? WHERE id = ?", (blob, mem_id)
                )
                conn.commit()
                # Update in-memory vectors
                if self._vectors is None:
                    self._vectors = np.array([nv])
                    self._vector_ids = [mem_id]
                else:
                    self._vectors = np.vstack([self._vectors, nv])
                    self._vector_ids.append(mem_id)
            except Exception:
                self._vectors = None
                self._vector_ids = []

        return mem_id

    def consolidate(self, threshold=0.85, dry_run=False):
        conn = self._get_conn()
        rows = conn.execute("SELECT id, text FROM memories").fetchall()
        removed = 0
        merged = 0
        keep_ids = set()
        handled = set()
        details = []

        # Simple token-set overlap dedup
        entries = [(r["id"], r["text"], self._tokenize(r["text"])) for r in rows]

        for i, (id_a, text_a, toks_a) in enumerate(entries):
            if i in handled:
                continue
            best_pair = None
            best_sim = 0.0
            for j, (id_b, text_b, toks_b) in enumerate(entries):
                if i >= j or j in handled:
                    continue
                inter = set(toks_a) & set(toks_b)
                union = set(toks_a) | set(toks_b)
                sim = len(inter) / len(union) if union else 0.0
                if sim >= threshold and sim > best_sim:
                    best_sim = sim
                    best_pair = j

            if best_pair is not None:
                merged_id = entries[best_pair][0]
                details.append(
                    {
                        "merged": [id_a, merged_id],
                        "text": text_a[:100],
                        "similarity": round(best_sim, 4),
                    }
                )
                handled.update({i, best_pair})
                removed += 1
                merged += 1
                keep_ids.add(id_a)
            else:
                keep_ids.add(id_a)
                handled.add(i)

        if not dry_run and removed > 0:
            ids_to_remove = [r["id"] for r in rows if r["id"] not in keep_ids]
            for rid in ids_to_remove:
                conn.execute("DELETE FROM memories WHERE id = ?", (rid,))
            conn.commit()
            self._query_cache.invalidate()
            self._vectors = None
            self._vector_ids = []

        remaining = (
            len(keep_ids)
            if dry_run
            else conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        )
        return {
            "dry_run": dry_run,
            "removed": removed,
            "merged": merged,
            "remaining": remaining,
            "threshold": threshold,
            "details": details,
        }

    def cache_status(self):
        return {
            "size": self._query_cache.size(),
            "maxsize": self._query_cache._maxsize,
            "strategy": "LRU",
        }

    def status(self):
        conn = self._get_conn()
        mem_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        syn_count = len(self.synonyms)
        total_bytes = (
            os.path.getsize(self.db_path) if os.path.isfile(self.db_path) else 0
        )
        last_ts_row = conn.execute(
            "SELECT timestamp FROM memories ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        last_ts = last_ts_row["timestamp"] if last_ts_row else ""
        vec_count = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE vector IS NOT NULL"
        ).fetchone()[0]
        vs = "unavailable"
        if self.vector_available():
            vs = (
                f"stored ({vec_count} vectors)"
                if self._vectors is None
                else f"loaded ({vec_count} vectors)"
            )
        else:
            vs = "not installed"

        fts_count = conn.execute("SELECT COUNT(*) FROM memories_fts").fetchone()[0]

        return {
            "memory_count": mem_count,
            "synonym_count": syn_count,
            "storage_bytes": total_bytes,
            "storage_backend": "sqlite+fts5",
            "fts_indexed": fts_count,
            "last_memory_timestamp": last_ts,
            "vector_search": vs,
            "vector_count": vec_count,
            "query_cache": self.cache_status(),
            "storage_path": self.storage_path,
            "db_path": self.db_path,
        }


_DEFAULT_SEARCHER = None


def _get_searcher():
    global _DEFAULT_SEARCHER
    if _DEFAULT_SEARCHER is None:
        _DEFAULT_SEARCHER = NEMemorySearch()
    return _DEFAULT_SEARCHER


def search(query, limit=10, fuzzy_threshold=0.85):
    return _get_searcher().search(query, limit, fuzzy_threshold)


def synthesize(query, max_sources=5, min_confidence=0.7):
    return _get_searcher().synthesize(query, max_sources, min_confidence)


def add_memory(text, source="manual", metadata=None):
    return _get_searcher().add_memory(text, source, metadata)


def consolidate(threshold=0.85):
    return _get_searcher().consolidate(threshold)


def status():
    return _get_searcher().status()


def vector_search(query, limit=10):
    return _get_searcher().vector_search(query, limit)


def hybrid_search(query, limit=10, bm25_weight=0.5, vector_weight=0.5, rrf_k=60):
    return _get_searcher().hybrid_search(
        query, limit, bm25_weight, vector_weight, rrf_k
    )


def reranked_search(query, limit=5, candidates=20):
    return _get_searcher().reranked_search(query, limit, candidates)


if __name__ == "__main__":
    se = NEMemorySearch()
    se.add_memory("The agent learned to use BM25 for memory search.", source="test")
    se.add_memory("Synonyms improve recall in search queries.", source="test")
    se.add_memory("Consolidation merges duplicate memory entries.", source="test")
    se.add_memory("BM25 is a ranking function used by search engines.", source="test")
    se.add_memory(
        "Neural networks learn patterns from data through interconnected layers.",
        source="test",
    )
    se.add_memory(
        "Sentence-transformers encode text into dense vectors for semantic similarity.",
        source="test",
    )

    print("=== SEARCH (bm25) ===")
    for r in se.search("bm25 search", limit=3):
        print(f"  [{r['score']:.4f}] {r['text'][:60]}")
    print("=== VECTOR SEARCH ===")
    r = se.vector_search("machine learning", limit=3)
    if isinstance(r, list):
        for x in r:
            print(f"  [{x['score']:.4f}] {x['text'][:60]}")
    print("=== HYBRID SEARCH ===")
    r = se.hybrid_search("how does memory search work", limit=3)
    if isinstance(r, dict):
        for x in r.get("results", []):
            print(f"  [{x['score']:.4f}] {x['text'][:60]}")
    print("=== RERANKED SEARCH ===")
    r = se.reranked_search("ranking algorithms", limit=3)
    print(f"  Method: {r.get('method')}")
    for x in r.get("results", []):
        print(f"  [{x.get('rerank_score', 0):.4f}] {x['text'][:60]}")
    print("=== STATUS ===")
    st = se.status()
    print(f"  Backend: {st['storage_backend']}")
    print(f"  FTS indexed: {st['fts_indexed']}")
    print(f"  Cache: {st['query_cache']}")
    print("DONE")
