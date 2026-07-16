import json
import math
import os
import tempfile
import uuid
from datetime import datetime, timezone
from difflib import get_close_matches

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
    def __init__(self, storage_path: str = "C:/Users/ohmpa/github/ai-memory-core/.memory/ne"):
        self.storage_path = storage_path.replace("/", os.sep)
        self.memories_path = os.path.join(self.storage_path, "memories.json")
        self.synonyms_path = os.path.join(self.storage_path, "data", "synonyms.json")
        self.k1 = 1.2
        self.b = 0.75
        self.synonyms = {}
        self._synonym_groups = {}
        self.memories = []
        self._corpus_terms = set()
        self._doc_freq = {}
        self._avg_doc_len = 0.0
        self._loaded = False
        self._load_synonyms()
        self._load_memories()

    def _load_synonyms(self):
        try:
            if os.path.isfile(self.synonyms_path):
                with open(self.synonyms_path, "r", encoding="utf-8") as f:
                    self.synonyms = json.load(f)
            self._build_synonym_groups()
        except Exception as e:
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

    def _load_memories(self):
        try:
            if os.path.isfile(self.memories_path):
                with open(self.memories_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.memories = data if isinstance(data, list) else []
            else:
                self.memories = []
                self._save_memories()
        except Exception:
            self.memories = []
        self._rebuild_index()
        self._loaded = True

    def _save_memories(self):
        tmp = None
        try:
            os.makedirs(os.path.dirname(self.memories_path), exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                suffix=".json",
                prefix="memories_",
                dir=os.path.dirname(self.memories_path),
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.memories, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.memories_path)
            tmp = None
        finally:
            if tmp is not None and os.path.isfile(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass

    def _rebuild_index(self):
        doc_freq = {}
        total_len = 0
        corpus_terms = set()
        for mem in self.memories:
            tokens = self._tokenize(mem.get("text", ""))
            seen = set()
            for t in tokens:
                corpus_terms.add(t)
                if t not in seen:
                    doc_freq[t] = doc_freq.get(t, 0) + 1
                    seen.add(t)
            total_len += len(tokens)
        self._doc_freq = doc_freq
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
        if doc_len == 0 or avg_doc_len == 0:
            return 0.0
        tf_map = {}
        for t in doc_tokens:
            tf_map[t] = tf_map.get(t, 0) + 1
        for qt in query_tokens:
            tf = tf_map.get(qt, 0)
            df = doc_freq.get(qt, 0)
            idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / avg_doc_len)
            score += idf * (numerator / denominator) if denominator != 0 else 0.0
        return score

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

    def _fuzzy_match(self, term: str, all_terms: set) -> list:
        if not all_terms:
            return []
        matches = get_close_matches(term, all_terms, n=3, cutoff=0.85)
        return matches

    def search(self, query: str, limit: int = 10, fuzzy_threshold: float = 0.85) -> list:
        if not self.memories:
            return []
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        expanded = self._expand_synonyms(query_tokens)
        fuzzy_extra = set()
        for t in expanded:
            for match in self._fuzzy_match(t, self._corpus_terms):
                fuzzy_extra.add(match)
        all_query_terms = list(set(expanded) | fuzzy_extra)
        total_docs = len(self.memories)
        scored = []
        for mem in self.memories:
            doc_tokens = self._tokenize(mem.get("text", ""))
            score = self._bm25_score(
                all_query_terms,
                doc_tokens,
                len(doc_tokens),
                self._avg_doc_len,
                total_docs,
                self._doc_freq,
            )
            scored.append((score, mem))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, mem in scored[:limit]:
            results.append({
                "text": mem.get("text", ""),
                "score": round(score, 4),
                "source": mem.get("source", "unknown"),
                "timestamp": mem.get("timestamp", ""),
                "id": mem.get("id", ""),
            })
        return results

    def synthesize(self, query: str, max_sources: int = 5, min_confidence: float = 0.7) -> dict:
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
        parts = []
        for i, src in enumerate(sources, 1):
            parts.append(f"[{i}] {src['text']}")
        synthesis = " ".join(parts)
        avg_confidence = round(
            sum(s["score"] for s in sources) / len(sources), 4
        )
        source_list = [
            {
                "id": s["id"],
                "text": s["text"],
                "source": s["source"],
                "timestamp": s["timestamp"],
                "score": s["score"],
            }
            for s in sources
        ]
        return {
            "query": query,
            "synthesis": synthesis,
            "sources": source_list,
            "confidence": avg_confidence,
        }

    def add_memory(self, text: str, source: str = "manual", metadata: dict = None) -> str:
        mem_id = str(uuid.uuid4())
        entry = {
            "id": mem_id,
            "text": text,
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self.memories.append(entry)
        self._rebuild_index()
        self._save_memories()
        return mem_id

    def consolidate(self, threshold: float = 0.85) -> dict:
        removed = 0
        merged = 0
        keep = []
        handled = set()
        for i, a in enumerate(self.memories):
            if i in handled:
                continue
            a_tokens = set(self._tokenize(a.get("text", "")))
            pair_idx = None
            for j, b in enumerate(self.memories):
                if i >= j or j in handled:
                    continue
                b_tokens = set(self._tokenize(b.get("text", "")))
                intersection = a_tokens & b_tokens
                union = a_tokens | b_tokens
                sim = len(intersection) / len(union) if union else 0.0
                if sim >= threshold:
                    pair_idx = j
                    break
            if pair_idx is not None:
                b = self.memories[pair_idx]
                a_sources = set(a.get("source", "").split(", "))
                b_sources = set(b.get("source", "").split(", "))
                merged_text = (
                    b["text"] if len(b["text"]) >= len(a["text"]) else a["text"]
                )
                combined_sources = ", ".join(sorted(set(a_sources | b_sources)))
                a_ts = a.get("timestamp", "")
                b_ts = b.get("timestamp", "")
                merged_entry = {
                    "id": str(uuid.uuid4()),
                    "text": merged_text,
                    "source": combined_sources,
                    "timestamp": min(a_ts, b_ts) if a_ts and b_ts else (a_ts or b_ts),
                    "metadata": {**a.get("metadata", {}), **b.get("metadata", {})},
                }
                keep.append(merged_entry)
                handled.add(i)
                handled.add(pair_idx)
                removed += 1
                merged += 1
            else:
                keep.append(a)
                handled.add(i)
        self.memories = keep
        self._rebuild_index()
        self._save_memories()
        return {
            "removed": removed,
            "merged": merged,
            "remaining": len(self.memories),
            "threshold": threshold,
        }

    def status(self) -> dict:
        mem_count = len(self.memories)
        syn_count = len(self.synonyms)
        total_bytes = 0
        try:
            if os.path.isfile(self.memories_path):
                total_bytes = os.path.getsize(self.memories_path)
        except Exception:
            pass
        last_ts = ""
        if self.memories:
            ts_list = [m.get("timestamp", "") for m in self.memories if m.get("timestamp")]
            if ts_list:
                last_ts = max(ts_list)
        return {
            "memory_count": mem_count,
            "synonym_count": syn_count,
            "storage_bytes": total_bytes,
            "average_doc_length": round(self._avg_doc_len, 2),
            "unique_terms": len(self._corpus_terms),
            "last_memory_timestamp": last_ts,
            "storage_path": self.storage_path,
            "loaded": self._loaded,
        }


_DEFAULT_SEARCHER = None


def _get_searcher():
    global _DEFAULT_SEARCHER
    if _DEFAULT_SEARCHER is None:
        _DEFAULT_SEARCHER = NEMemorySearch()
    return _DEFAULT_SEARCHER


def search(query: str, limit: int = 10, fuzzy_threshold: float = 0.85) -> list:
    return _get_searcher().search(query, limit, fuzzy_threshold)


def synthesize(query: str, max_sources: int = 5, min_confidence: float = 0.7) -> dict:
    return _get_searcher().synthesize(query, max_sources, min_confidence)


def add_memory(text: str, source: str = "manual", metadata: dict = None) -> str:
    return _get_searcher().add_memory(text, source, metadata)


def consolidate(threshold: float = 0.85) -> dict:
    return _get_searcher().consolidate(threshold)


def status() -> dict:
    return _get_searcher().status()


if __name__ == "__main__":
    se = NEMemorySearch()

    se.add_memory("The agent learned to use BM25 for memory search.", source="test")
    se.add_memory("Synonyms improve recall in search queries.", source="test")
    se.add_memory("Consolidation merges duplicate memory entries.", source="test")
    se.add_memory("BM25 is a ranking function used by search engines.", source="test")

    print("=== SEARCH (query='bm25 search') ===")
    for r in se.search("bm25 search", limit=5):
        print(f"  [{r['score']:.4f}] {r['text']}  (src={r['source']})")

    print("\n=== SYNTHESIZE (query='memory retrieval') ===")
    syn = se.synthesize("memory retrieval", max_sources=3, min_confidence=0.0)
    print(f"  confidence={syn['confidence']}")
    print(f"  synthesis={syn['synthesis']}")

    print("\n=== STATUS ===")
    st = se.status()
    for k, v in st.items():
        print(f"  {k}: {v}")

    print("\n=== CONSOLIDATE ===")
    c = se.consolidate(threshold=0.85)
    print(f"  removed={c['removed']}, merged={c['merged']}, remaining={c['remaining']}")
