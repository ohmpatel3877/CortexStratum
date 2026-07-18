#!/usr/bin/env python3
"""BM25 memory search with optional vector/hybrid search, cross-encoder reranking,
inverted index, and LRU query cache. Zero LLM calls, zero GPU required.

Architecture:
  - BM25 Okapi with synonym expansion + fuzzy matching (core, no deps)
  - Optional vector search via sentence-transformers + numpy
  - Optional cross-encoder reranker for precision-critical queries
  - Inverted index for O(query_terms * matching_docs) search
  - LRU query cache for repeated queries
"""

import json, math, os, tempfile, threading, time, uuid
from collections import OrderedDict
from datetime import datetime, timezone
from difflib import get_close_matches
from pathlib import Path

# Optional deps — graceful fallback
try:
    import numpy as np; _NUMPY_AVAILABLE = True
except ImportError:
    np = None; _NUMPY_AVAILABLE = False

try:
    import sentence_transformers as st; _SENTENCE_AVAILABLE = True
except ImportError:
    st = None; _SENTENCE_AVAILABLE = False


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
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "need",
    "dare", "ought", "used", "this", "that", "these", "those", "i", "me",
    "my", "we", "our", "you", "your", "he", "him", "his", "she", "her",
    "it", "its", "they", "them", "their", "what", "which", "who", "whom",
    "when", "where", "why", "how", "all", "each", "every", "both", "few",
    "more", "most", "some", "any", "no", "not", "only", "own", "same",
    "so", "than", "too", "very", "just", "because", "if", "then", "else",
    "up", "down", "out", "about", "into", "over", "after", "before",
    "between", "under", "again", "further", "once", "here", "there",
}


class NEMemorySearch:
    def __init__(self, storage_path: str = ""):
        if not storage_path:
            base = Path(__file__).resolve().parent.parent / ".memory" / "ne"
            storage_path = str(base)
        self.storage_path = storage_path.replace("/", os.sep)
        self.memories_path = os.path.join(self.storage_path, "memories.json")
        self.synonyms_path = os.path.join(self.storage_path, "data", "synonyms.json")
        self.vector_dir = os.path.join(self.storage_path, "vectors")
        self.vectors_path = os.path.join(self.vector_dir, "vectors.npy")
        self.vector_ids_path = os.path.join(self.vector_dir, "vector_ids.json")
        self.k1 = 1.2; self.b = 0.75
        self.synonyms = {}; self._synonym_groups = {}
        self.memories = []
        self._corpus_terms = set(); self._doc_freq = {}
        self._inverted_index: dict[str, set[int]] = {}
        self._avg_doc_len = 0.0; self._loaded = False
        self._vector_model = None; self._vectors = None; self._vector_ids = []
        self._reranker = None
        self._query_cache = LRUCache(maxsize=128)
        self._lock = threading.Lock()
        self._load_synonyms(); self._load_memories(); self._load_vectors()

    def _load_synonyms(self):
        try:
            if os.path.isfile(self.synonyms_path):
                with open(self.synonyms_path) as f:
                    self.synonyms = json.load(f)
            self._build_synonym_groups()
        except Exception:
            self.synonyms = {}; self._synonym_groups = {}

    def _build_synonym_groups(self):
        groups = {}
        for key, syns in self.synonyms.items():
            group = set([key] + syns)
            for term in group:
                t = term.lower().strip()
                if t not in groups: groups[t] = set()
                groups[t].update(group)
        self._synonym_groups = groups

    def _load_memories(self):
        try:
            if os.path.isfile(self.memories_path):
                with open(self.memories_path) as f:
                    data = json.load(f)
                    self.memories = data if isinstance(data, list) else []
            else:
                self.memories = []; self._save_memories()
        except Exception as e:
            # Backup corrupted file before resetting
            import logging, shutil
            logging.warning("Failed to load memories.json: " + str(e))
            if __import__("os").path.isfile(self.memories_path) and __import__("os").path.getsize(self.memories_path) > 0:
                bak = self.memories_path + ".corrupted." + str(__import__("time").time()).replace(".", "_")
                shutil.copy2(self.memories_path, bak)
            self.memories = []
        self._rebuild_index(); self._loaded = True

    def _save_memories(self):
        tmp = None
        try:
            os.makedirs(os.path.dirname(self.memories_path), exist_ok=True)
            fd, tmp = tempfile.mkstemp(suffix=".json", prefix="memories_", dir=os.path.dirname(self.memories_path))
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.memories, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.memories_path); tmp = None
        finally:
            if tmp and os.path.isfile(tmp):
                try: os.remove(tmp)
                except: pass

    def _rebuild_index(self):
        """Build inverted index + doc frequency map. Thread-safe via lock."""
        with self._lock:
            self._rebuild_index_unsafe()

    def _rebuild_index_unsafe(self):
        doc_freq = {}; total_len = 0; corpus_terms = set()
        inverted_index: dict[str, set[int]] = {}
        for idx, mem in enumerate(self.memories):
            tokens = self._tokenize(mem.get("text", ""))
            seen = set()
            for t in tokens:
                corpus_terms.add(t)
                if t not in seen:
                    doc_freq[t] = doc_freq.get(t, 0) + 1
                    seen.add(t)
                if t not in inverted_index: inverted_index[t] = set()
                inverted_index[t].add(idx)
            total_len += len(tokens)
        self._doc_freq = doc_freq; self._inverted_index = inverted_index
        self._corpus_terms = corpus_terms
        n = len(self.memories)
        self._avg_doc_len = total_len / n if n > 0 else 0.0

    def _tokenize(self, text: str) -> list:
        tokens = []
        for raw in text.lower().split():
            cleaned = "".join(c for c in raw if c.isalnum())
            if cleaned and cleaned not in STOPWORDS:
                tokens.append(cleaned)
        return tokens

    def _bm25_score(self, query_tokens, doc_tokens, doc_len, avg_doc_len, total_docs, doc_freq):
        score = 0.0
        if doc_len == 0 or avg_doc_len == 0: return 0.0
        tf_map = {}
        for t in doc_tokens: tf_map[t] = tf_map.get(t, 0) + 1
        for qt in query_tokens:
            tf = tf_map.get(qt, 0); df = doc_freq.get(qt, 0)
            idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / avg_doc_len)
            score += idf * (numerator / denominator) if denominator != 0 else 0.0
        return score

    def _expand_synonyms(self, tokens: list) -> list:
        expanded = []; seen = set()
        for t in tokens:
            if t in self._synonym_groups:
                for syn in self._synonym_groups[t]:
                    if syn not in seen: expanded.append(syn); seen.add(syn)
            else:
                if t not in seen: expanded.append(t); seen.add(t)
        return expanded

    def _fuzzy_match(self, term, all_terms):
        if not all_terms: return []
        return get_close_matches(term, all_terms, n=3, cutoff=0.85)

    #  Vector Search 
    def vector_available(self) -> bool:
        return _NUMPY_AVAILABLE and _SENTENCE_AVAILABLE

    def _load_vector_model(self):
        if self._vector_model is not None: return True
        if not self.vector_available(): return False
        try:
            model = os.environ.get("AI_MEMORY_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            self._vector_model = st.SentenceTransformer(model)
            return True
        except: return False

    def _load_vectors(self):
        if not _NUMPY_AVAILABLE: return
        try:
            if os.path.isfile(self.vectors_path) and os.path.isfile(self.vector_ids_path):
                self._vectors = np.load(self.vectors_path)
                with open(self.vector_ids_path) as f: self._vector_ids = json.load(f)
        except: self._vectors = None; self._vector_ids = []

    def _save_vectors(self):
        if self._vectors is None or not _NUMPY_AVAILABLE: return
        try:
            os.makedirs(self.vector_dir, exist_ok=True)
            fd, tmp = tempfile.mkstemp(suffix=".npy", prefix="vectors_", dir=self.vector_dir)
            with os.fdopen(fd, "wb") as f: np.save(f, self._vectors)
            os.replace(tmp, self.vectors_path)
            fd2, tmp2 = tempfile.mkstemp(suffix=".json", prefix="vecids_", dir=self.vector_dir)
            with os.fdopen(fd2, "w") as f: json.dump(self._vector_ids, f)
            os.replace(tmp2, self.vector_ids_path)
        except: pass

    def _compute_vectors(self):
        if not self._load_vector_model(): self._vectors = None; self._vector_ids = []; return
        texts = [m.get("text", "") for m in self.memories]
        if not texts: self._vectors = None; self._vector_ids = []; return
        try:
            self._vectors = self._vector_model.encode(texts, show_progress_bar=False)
            self._vector_ids = [m.get("id", "") for m in self.memories]
            self._save_vectors()
        except: self._vectors = None; self._vector_ids = []

    def vector_search(self, query: str, limit: int = 10) -> list | dict:
        if not self._load_vector_model():
            return {"error": "Vector search unavailable. Install: pip install sentence-transformers numpy"}
        if not self.memories: return []
        if self._vectors is None or len(self._vectors) != len(self.memories): self._compute_vectors()
        if self._vectors is None or len(self._vectors) == 0: return []
        try:
            query_vec = self._vector_model.encode([query])[0]
            if self._vectors.shape[1] != query_vec.shape[0]:
                self._compute_vectors()
                query_vec = self._vector_model.encode([query])[0]
        except: return {"error": "Query encoding failed"}
        scores = []
        for i, vec in enumerate(self._vectors):
            sim = float(np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec) + 1e-10))
            scores.append((sim, i))
        scores.sort(key=lambda x: x[0], reverse=True)
        return [{"text": self.memories[idx].get("text",""), "score": round(sim,4),
                 "source": self.memories[idx].get("source","unknown"),
                 "timestamp": self.memories[idx].get("timestamp",""), "id": self.memories[idx].get("id","")}
                for sim, idx in scores[:limit]]

    #  Cross-Encoder Reranker 
    def _load_reranker(self):
        if getattr(self, '_reranker', None) is not None: return True
        if not _SENTENCE_AVAILABLE: return False
        try:
            model = os.environ.get("AI_MEMORY_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
            self._reranker = st.CrossEncoder(model)
            return True
        except: self._reranker = None; return False

    def reranked_search(self, query: str, limit: int = 5, candidates: int = 20) -> dict:
        initial = self.hybrid_search(query, limit=candidates)
        results_list = initial.get("results", []) if isinstance(initial, dict) else []
        if not results_list:
            return {"results": [], "method": "reranked"}
        if not self._load_reranker():
            return {"results": results_list[:limit], "method": "hybrid_only",
                    "reranker": "unavailable (pip install sentence-transformers)"}
        try:
            pairs = [(query, r["text"]) for r in results_list]
            scores = self._reranker.predict(pairs)
            for i, score in enumerate(scores): results_list[i]["rerank_score"] = round(float(score), 4)
            results_list.sort(key=lambda r: r.get("rerank_score", 0), reverse=True)
            return {"results": results_list[:limit], "method": "reranked",
                    "reranker": os.environ.get("AI_MEMORY_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")}
        except Exception as e:
            return {"results": results_list[:limit], "method": "hybrid_only", "reranker": f"error: {e}"}

    #  Hybrid Search (BM25 + Vector RRF) 
    def hybrid_search(self, query, limit=10, bm25_weight=0.5, vector_weight=0.5, rrf_k=60):
        bm25_results = self.search(query, limit=limit * 2)
        bm25_map = {r["id"]: r for r in bm25_results}
        vec_results = self.vector_search(query, limit=limit * 2)
        vec_available = isinstance(vec_results, list)
        vec_map = {r["id"]: r for r in vec_results} if vec_available else {}
        if not vec_available:
            return {"results": [{**r, "bm25_score": r["score"], "vector_score": 0.0,
                                 "bm25_rank": i+1, "vector_rank": None}
                                for i, r in enumerate(bm25_results[:limit])],
                    "method": "bm25_only", "note": "Vector search unavailable"}
        all_ids = list(dict.fromkeys([r["id"] for r in bm25_results] + [r["id"] for r in vec_results]))
        scored = []
        for doc_id in all_ids:
            rrf_score = 0.0; bm25_rank = None; vec_rank = None
            if doc_id in bm25_map:
                bm25_rank = next(i for i,r in enumerate(bm25_results) if r["id"]==doc_id) + 1
                rrf_score += bm25_weight * (1.0 / (rrf_k + bm25_rank))
            if doc_id in vec_map:
                vec_rank = next(i for i,r in enumerate(vec_results) if r["id"]==doc_id) + 1
                rrf_score += vector_weight * (1.0 / (rrf_k + vec_rank))
            src = bm25_map.get(doc_id) or vec_map.get(doc_id) or {}
            scored.append({"text": src["text"], "score": round(rrf_score,4),
                           "bm25_score": bm25_map[doc_id]["score"] if doc_id in bm25_map else 0.0,
                           "vector_score": vec_map[doc_id]["score"] if doc_id in vec_map else 0.0,
                           "bm25_rank": bm25_rank, "vector_rank": vec_rank,
                           "source": src.get("source","unknown"), "timestamp": src.get("timestamp",""), "id": doc_id})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return {"results": scored[:limit], "method": "hybrid_rrf",
                "bm25_weight": bm25_weight, "vector_weight": vector_weight, "rrf_k": rrf_k,
                "bm25_results_count": len(bm25_results), "vector_results_count": len(vec_results)}

    #  BM25 Search (with inverted index) 
    def search(self, query: str, limit: int = 10, fuzzy_threshold: float = 0.85) -> list:
        if not self.memories: return []
        cache_key = f"{query}:{limit}:{fuzzy_threshold}"
        cached = self._query_cache.get(cache_key)
        if cached is not None: return cached
        query_tokens = self._tokenize(query)
        if not query_tokens: return []
        expanded = self._expand_synonyms(query_tokens)
        fuzzy_extra = set()
        for t in expanded:
            for m in self._fuzzy_match(t, self._corpus_terms): fuzzy_extra.add(m)
        all_query_terms = list(set(expanded) | fuzzy_extra)
        total_docs = len(self.memories)
        # Thread-safe snapshot of inverted index
        with self._lock:
            idx_snap = dict(self._inverted_index)
            df_snap = dict(self._doc_freq)
            mem_snap = list(self.memories)
        candidate_indices: set[int] = set()
        for qt in all_query_terms:
            if qt in idx_snap: candidate_indices.update(idx_snap[qt])
        scored = []
        for idx in candidate_indices:
            mem = mem_snap[idx]
            dt = self._tokenize(mem.get("text",""))
            scored.append((self._bm25_score(all_query_terms, dt, len(dt), self._avg_doc_len, total_docs, df_snap), mem))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [{"text": mem.get("text",""), "score": round(score,4), "source": mem.get("source","unknown"),
                    "timestamp": mem.get("timestamp",""), "id": mem.get("id","")}
                   for score, mem in scored[:limit]]
        self._query_cache.put(cache_key, results)
        return results

    #  Aggregate Methods 
    def synthesize(self, query, max_sources=5, min_confidence=0.7):
        results = self.search(query, limit=max_sources)
        sources = [r for r in results if r["score"] >= min_confidence]
        if not sources:
            max_score = max(r["score"] for r in results) if results else 0.0
            if results and max_score > 0: sources = results[:1]
            else: return {"query": query, "synthesis": "", "sources": [], "confidence": 0.0}
        parts = [f"[{i}] {s['text']}" for i, s in enumerate(sources, 1)]
        avg_c = round(sum(s["score"] for s in sources) / len(sources), 4)
        return {"query": query, "synthesis": " ".join(parts), "sources": sources, "confidence": avg_c}

    def add_memory(self, text, source="manual", metadata=None):
        mem_id = str(uuid.uuid4())
        entry = {"id": mem_id, "text": text, "source": source,
                 "timestamp": datetime.now(timezone.utc).isoformat(), "metadata": metadata or {}}
        self._query_cache.invalidate()
        self.memories.append(entry)
        self._rebuild_index(); self._save_memories()
        if self._vector_model is not None and _NUMPY_AVAILABLE:
            try:
                nv = self._vector_model.encode([text])[0]
                if self._vectors is None:
                    self._vectors = np.array([nv]); self._vector_ids = [mem_id]
                else:
                    self._vectors = np.vstack([self._vectors, nv]); self._vector_ids.append(mem_id)
                self._save_vectors()
            except: self._vectors = None; self._vector_ids = []
        return mem_id

    def consolidate(self, threshold=0.85, dry_run=False):
        removed = 0; merged = 0; keep = []; handled = set(); details = []
        for i, a in enumerate(self.memories):
            if i in handled: continue
            a_tokens = set(self._tokenize(a.get("text","")))
            pair_idx = None
            for j, b in enumerate(self.memories):
                if i >= j or j in handled: continue
                b_tokens = set(self._tokenize(b.get("text","")))
                inter = a_tokens & b_tokens; union = a_tokens | b_tokens
                sim = len(inter)/len(union) if union else 0.0
                if sim >= threshold: pair_idx = j; break
            if pair_idx is not None:
                b = self.memories[pair_idx]
                merged_entry = {"id": str(uuid.uuid4()), "text": a["text"],
                    "source": ", ".join(sorted(set(a.get("source","").split(", ")) | set(b.get("source","").split(", ")))),
                    "timestamp": min(a.get("timestamp",""), b.get("timestamp","")),
                    "metadata": {**a.get("metadata",{}), **b.get("metadata",{}),
                                 "merged_from": [a["id"], b["id"]], "merged_at": datetime.now(timezone.utc).isoformat()}}
                details.append({"merged": [a["id"], b["id"]], "text": a["text"][:100],
                                "similarity": round(sim,4)})
                keep.append(merged_entry); handled.update({i, pair_idx})
                removed += 1; merged += 1
            else: keep.append(a); handled.add(i)
        if not dry_run:
            self.memories = keep; self._rebuild_index(); self._save_memories()
            self._query_cache.invalidate(); self._vectors = None; self._vector_ids = []
        return {"dry_run": dry_run, "removed": removed, "merged": merged,
                "remaining": len(keep) if dry_run else len(self.memories), "threshold": threshold, "details": details}

    def cache_status(self):
        return {"size": self._query_cache.size(), "maxsize": self._query_cache._maxsize, "strategy": "LRU"}

    def status(self):
        mem_count = len(self.memories); syn_count = len(self.synonyms)
        total_bytes = 0
        if os.path.isfile(self.memories_path): total_bytes = os.path.getsize(self.memories_path)
        last_ts = max([m["timestamp"] for m in self.memories if m.get("timestamp")] or [""])
        vs = "unavailable"
        if self.vector_available():
            if self._vectors is not None: vs = f"loaded ({len(self._vectors)} vectors)"
            else: vs = "not loaded"
        else: vs = "not installed"
        return {"memory_count": mem_count, "synonym_count": syn_count, "storage_bytes": total_bytes,
                "average_doc_length": round(self._avg_doc_len,2), "unique_terms": len(self._corpus_terms),
                "last_memory_timestamp": last_ts, "vector_search": vs,
                "vector_count": len(self._vectors) if self._vectors is not None else 0,
                "query_cache": self.cache_status(),
                "index": {"inverted_index_terms": len(self._inverted_index), "indexed_documents": len(self.memories)},
                "storage_path": self.storage_path, "loaded": self._loaded}


_DEFAULT_SEARCHER = None
def _get_searcher():
    global _DEFAULT_SEARCHER
    if _DEFAULT_SEARCHER is None: _DEFAULT_SEARCHER = NEMemorySearch()
    return _DEFAULT_SEARCHER

def search(query, limit=10, fuzzy_threshold=0.85): return _get_searcher().search(query, limit, fuzzy_threshold)
def synthesize(query, max_sources=5, min_confidence=0.7): return _get_searcher().synthesize(query, max_sources, min_confidence)
def add_memory(text, source="manual", metadata=None): return _get_searcher().add_memory(text, source, metadata)
def consolidate(threshold=0.85): return _get_searcher().consolidate(threshold)
def status(): return _get_searcher().status()
def vector_search(query, limit=10): return _get_searcher().vector_search(query, limit)
def hybrid_search(query, limit=10, bm25_weight=0.5, vector_weight=0.5, rrf_k=60):
    return _get_searcher().hybrid_search(query, limit, bm25_weight, vector_weight, rrf_k)
def reranked_search(query, limit=5, candidates=20): return _get_searcher().reranked_search(query, limit, candidates)


if __name__ == "__main__":
    se = NEMemorySearch()
    se.add_memory("The agent learned to use BM25 for memory search.", source="test")
    se.add_memory("Synonyms improve recall in search queries.", source="test")
    se.add_memory("Consolidation merges duplicate memory entries.", source="test")
    se.add_memory("BM25 is a ranking function used by search engines.", source="test")
    se.add_memory("Neural networks learn patterns from data through interconnected layers.", source="test")
    se.add_memory("Sentence-transformers encode text into dense vectors for semantic similarity.", source="test")

    print("=== SEARCH (bm25) ===")
    for r in se.search("bm25 search", limit=3): print(f"  [{r['score']:.4f}] {r['text'][:60]}")
    print("=== VECTOR SEARCH ===")
    r = se.vector_search("machine learning", limit=3)
    if isinstance(r, list): [print(f"  [{x['score']:.4f}] {x['text'][:60]}") for x in r]
    print("=== HYBRID SEARCH ===")
    r = se.hybrid_search("how does memory search work", limit=3)
    if isinstance(r, dict): [print(f"  [{x['score']:.4f}] {x['text'][:60]}") for x in r.get('results',[])]
    print("=== RERANKED SEARCH ===")
    r = se.reranked_search("ranking algorithms", limit=3)
    print(f"  Method: {r.get('method')}")
    [print(f"  [{x.get('rerank_score',0):.4f}] {x['text'][:60]}") for x in r.get('results',[])]
    print("=== STATUS ===")
    st = se.status()
    print(f"  Cache: {st['query_cache']}")
    print(f"  Index terms: {st['index']['inverted_index_terms']}")
