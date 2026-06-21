"""
Semantic Cache for QueryCraft
ChromaDB-backed cache using BAAI/bge-large-en-v1.5 embeddings.

Improvements:
- Synchronous model load — API waits for model load to complete
- Cache entry metadata: validated_at, execution_success, row_count for auditability
- Runtime threshold adjustment via set_threshold() / get_threshold()
"""
import hashlib
import sys
import os
import re
import json
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from config import CACHE_SIMILARITY_THRESHOLD
except (ValueError, ImportError):
    CACHE_SIMILARITY_THRESHOLD = 0.90

import chromadb
from sentence_transformers import SentenceTransformer

try:
    from pipeline import embeddings
except ImportError:
    import embeddings  # type: ignore


def stem_word(word: str) -> str:
    """
    Minimal stemmer to handle common plural nouns in DB contexts:
    e.g., processes -> process, disks -> disk, cpus -> cpu, files -> file.
    """
    word = word.lower().strip()
    if len(word) <= 3:
        return word
    if word.endswith('sses'):
        return word[:-2]  # processes -> process
    if word.endswith('ies'):
        return word[:-3] + 'y'  # queries -> query
    if word.endswith('es') and not word.endswith('ees') and not word.endswith('ses'):
        return word[:-2]
    if word.endswith('s') and not word.endswith('ss'):
        return word[:-1]
    return word


def extract_entities(text: str) -> dict:
    """
    Extract numbers, quoted values, and key entity terms from query text.
    Enforces exact matches to prevent false cache hits.
    """
    text = text.lower().strip()

    # 1. Extract standalone numbers (both integers and decimals)
    number_matches = re.findall(r'\b\d+(?:\.\d+)?\b', text)
    numbers = []
    for num_str in number_matches:
        try:
            if '.' in num_str:
                numbers.append(float(num_str))
            else:
                numbers.append(int(num_str))
        except ValueError:
            pass
    numbers = sorted(numbers)

    # 2. Extract quoted strings
    quoted_strings = re.findall(r'["\'](.*?)["\']', text)
    quoted_strings = sorted([q.strip() for q in quoted_strings if q.strip()])

    STOP_WORDS = {
        'list', 'show', 'display', 'get', 'find', 'select', 'give', 'run', 'execute',
        'the', 'a', 'an', 'of', 'to', 'for', 'by', 'with', 'on', 'at', 'from', 'in', 'about',
        'how', 'what', 'where', 'who', 'which', 'why', 'whose',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'and', 'or', 'but', 'if', 'then', 'else', 'when',
        'per', 'each', 'every', 'grouped', 'group', 'order', 'sort', 'sorted',
        'top', 'bottom', 'limit', 'first', 'last',
        'average', 'mean', 'sum', 'count', 'counts', 'min', 'max', 'minimum', 'maximum', 'total', 'avg',
        'name', 'names', 'time', 'times', 'statistics', 'stats', 'data', 'info', 'information',
        'value', 'values', 'metric', 'metrics', 'record', 'records',
        'number', 'numbers', 'num', 'nums', 'detail', 'details', 'busy', 'usage', 'query', 'queries',
        'database', 'table', 'tables', 'column', 'columns', 'row', 'rows'
    }

    # Extract all words starting with a letter
    all_words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text)

    entity_words = set()
    for w in all_words:
        if w in STOP_WORDS:
            continue
        stemmed = stem_word(w)
        if stemmed not in STOP_WORDS:
            entity_words.add(stemmed)

    return {
        "numbers": numbers,
        "quoted": quoted_strings,
        "entities": sorted(list(entity_words))
    }



class CacheResult:
    """Result of a cache lookup."""

    def __init__(self, hit: bool, sql: Optional[str] = None, confidence: float = 0.0):
        self.hit = hit
        self.sql = sql
        self.confidence = confidence

    def to_dict(self):
        return {'hit': self.hit, 'sql': self.sql, 'confidence': self.confidence}


class SemanticCache:
    """
    Semantic query cache backed by ChromaDB + sentence-transformers.

    The embedding model is loaded synchronously.
    """

    COLLECTION_NAME = "querycraft_cache"
    MODEL_NAME = "BAAI/bge-large-en-v1.5"

    def __init__(self, persist_path: str = "cache_store",
                 threshold: float = CACHE_SIMILARITY_THRESHOLD):
        """
        Initialize the semantic cache.

        Args:
            persist_path: Directory for ChromaDB persistent storage
            threshold:    Cosine similarity threshold for a cache hit (default 0.95)
        """
        self._threshold = threshold

        # Ensure directory exists
        os.makedirs(persist_path, exist_ok=True)

        # Initialize ChromaDB with cosine distance metric
        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}   # cosine distance → similarity = 1 - distance
        )

        # Guard against embedding dimension mismatches (e.g. switching from
        # MiniLM-384d to BGE-large-1024d).  Probe the first stored embedding;
        # if its dimension doesn't match the current model, drop & recreate.
        self._check_embedding_dimension()

        print(f"[Cache] ChromaDB ready — {self.collection.count()} entries.")

        # Shared embedding model — kicks off load on first caller.
        embeddings.start_loading()

    # ── Model access ──────────────────────────────────────────────────────────

    @property
    def model(self) -> Optional[SentenceTransformer]:
        return embeddings.get()

    @property
    def _model_ready(self):
        """Back-compat alias for tests that wait on the event directly."""
        return embeddings._ready

    @property
    def is_model_ready(self) -> bool:
        """True once the shared embedding model has finished loading."""
        return embeddings.is_ready()

    # ── Threshold management ──────────────────────────────────────────────────

    def get_threshold(self) -> float:
        """Return the current similarity threshold."""
        return self._threshold

    def set_threshold(self, value: float) -> None:
        """
        Update the similarity threshold at runtime (no restart needed).

        Args:
            value: New threshold, must be in (0.0, 1.0]
        """
        if not (0.0 < value <= 1.0):
            raise ValueError(f"Threshold must be in (0.0, 1.0], got {value}")
        self._threshold = value
        print(f"[Cache] Similarity threshold updated to {value}")

    # ── Dimension guard ───────────────────────────────────────────────────────

    # Expected embedding dimension for the current model.  BGE-large produces
    # 1024-dim vectors; update this constant if the model changes again.
    _EXPECTED_DIM = 1024

    def _check_embedding_dimension(self) -> None:
        """Drop and recreate the collection if stored embeddings have a
        different dimension than the current model.  This handles seamless
        migration when the embedding model is swapped (e.g. MiniLM-384d →
        BGE-large-1024d) without requiring manual cache deletion."""
        if self.collection.count() == 0:
            return  # nothing stored yet — no conflict possible

        try:
            sample = self.collection.peek(limit=1)
            stored_embeddings = sample.get("embeddings")
            if stored_embeddings is None or len(stored_embeddings) == 0 or len(stored_embeddings[0]) == 0:
                return

            stored_dim = len(stored_embeddings[0])
            if stored_dim != self._EXPECTED_DIM:
                print(
                    f"[Cache] ⚠ Embedding dimension mismatch: stored={stored_dim}, "
                    f"expected={self._EXPECTED_DIM}. Dropping stale collection..."
                )
                self.client.delete_collection(self.COLLECTION_NAME)
                self.collection = self.client.get_or_create_collection(
                    name=self.COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
                print("[Cache] Collection recreated (empty).")
        except Exception as e:
            print(f"[Cache] Warning: dimension check failed: {e}")

    # ── Core operations ───────────────────────────────────────────────────────

    def lookup(self, normalized_text: str, target_db: str = None) -> CacheResult:
        """
        Look up a query in the cache.

        Returns a miss immediately if the embedding model is not yet ready.

        Args:
            normalized_text: Normalized query string
            target_db: Optional target schema to filter the cache hits

        Returns:
            CacheResult with hit status, SQL, and confidence score
        """
        # Model not ready yet — safe fallback
        if not self.is_model_ready:
            return CacheResult(hit=False, confidence=0.0)

        if self.collection.count() == 0:
            return CacheResult(hit=False, confidence=0.0)

        # Embed the query
        embedding = self.model.encode([normalized_text]).tolist()

        where_clause = {}
        if target_db:
            where_clause["target_db"] = target_db

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=embedding,
            n_results=1,
            where=where_clause if where_clause else None,
            include=["metadatas", "distances"]
        )

        if not results["distances"] or not results["distances"][0]:
            return CacheResult(hit=False, confidence=0.0)

        # ChromaDB cosine distance: 0 = identical, 1 = orthogonal
        # Convert to similarity: similarity = 1 - distance
        distance   = results["distances"][0][0]
        confidence = 1.0 - distance

        if confidence >= self._threshold:
            meta = results["metadatas"][0][0]
            sql  = meta.get("sql", "")

            # Skip entries that were previously flagged as execution failures
            if meta.get("execution_success") == "false":
                print(f"[Cache] Skipping flagged entry (execution_success=false) for: {normalized_text[:60]}")
                return CacheResult(hit=False, confidence=round(confidence, 4))

            # SOTA 1: Enforce exact match on numbers, quoted values, and entity terms
            lookup_ent = extract_entities(normalized_text)
            stored_numbers_str = meta.get("cache_numbers")
            stored_quoted_str = meta.get("cache_quoted")
            stored_entities_str = meta.get("cache_entities")

            if stored_numbers_str is not None:
                stored_numbers = json.loads(stored_numbers_str)
                stored_quoted = json.loads(stored_quoted_str)
                stored_entities = json.loads(stored_entities_str)
            else:
                # Fallback for legacy cache entries
                stored_query = meta.get("query", "")
                stored_val = extract_entities(stored_query)
                stored_numbers = stored_val["numbers"]
                stored_quoted = stored_val["quoted"]
                stored_entities = stored_val["entities"]

            if (lookup_ent["numbers"] != stored_numbers or
                lookup_ent["quoted"] != stored_quoted or
                lookup_ent["entities"] != stored_entities):
                print(f"[Cache] Rejecting hit due to mismatch. Lookup: {lookup_ent}, Stored: {{'numbers': {stored_numbers}, 'quoted': {stored_quoted}, 'entities': {stored_entities}}}")
                return CacheResult(hit=False, confidence=round(confidence, 4))

            return CacheResult(hit=True, sql=sql, confidence=round(confidence, 4))

        return CacheResult(hit=False, confidence=round(confidence, 4))

    def store(
        self,
        normalized_text: str,
        sql: str,
        execution_success: bool = True,
        row_count: Optional[int] = None,
        target_db: str = None
    ) -> None:
        """
        Store a query→SQL pair in the cache with execution metadata.

        Args:
            normalized_text:   Normalized query string
            sql:               Validated SQL to cache
            execution_success: Whether the query executed without error
            row_count:         Number of rows returned (None if unknown)
            target_db:         The database schema this query targets
        """
        # Model not ready — skip silently (entry will be stored on next successful run)
        if not self.is_model_ready:
            print("[Cache] Model not ready — skipping store.")
            return

        # Use hash of normalized text + target_db as unique ID so the same
        # query run against different databases (macht413 vs machd500) never
        # shares or overwrites the other's cached SQL.
        cache_key = f"{normalized_text}|{target_db or 'default'}"
        doc_id = hashlib.sha256(cache_key.encode()).hexdigest()

        # Embed the query
        embedding = self.model.encode([normalized_text]).tolist()

        # Build metadata — ChromaDB only supports str/int/float/bool values
        entities = extract_entities(normalized_text)
        metadata: dict = {
            "sql":               sql,
            "query":             normalized_text,
            "validated_at":      datetime.now(timezone.utc).isoformat(),
            "execution_success": "true" if execution_success else "false",
            "cache_numbers":     json.dumps(entities["numbers"]),
            "cache_quoted":      json.dumps(entities["quoted"]),
            "cache_entities":    json.dumps(entities["entities"]),
        }
        if target_db:
            metadata["target_db"] = target_db
        if row_count is not None:
            metadata["row_count"] = row_count

        # Upsert — overwrite if same query stored before
        self.collection.upsert(
            ids=[doc_id],
            embeddings=embedding,
            metadatas=[metadata],
            documents=[normalized_text]
        )

    def flag_failed(self, normalized_text: str, target_db: str = None) -> bool:
        """
        Mark an existing cache entry as execution_success=false.

        Called when a cached SQL causes an execution error so future lookups
        skip it automatically.

        Args:
            normalized_text: Normalized query string

        Returns:
            True if the entry was found and updated, False otherwise
        """
        if not self.is_model_ready:
            return False

        cache_key = f"{normalized_text}|{target_db or 'default'}"
        doc_id = hashlib.sha256(cache_key.encode()).hexdigest()

        try:
            existing = self.collection.get(ids=[doc_id], include=["metadatas", "embeddings", "documents"])
            if not existing["ids"]:
                return False

            meta = existing["metadatas"][0].copy()
            meta["execution_success"] = "false"

            self.collection.upsert(
                ids=[doc_id],
                embeddings=existing["embeddings"][0] if existing.get("embeddings") else
                           self.model.encode([normalized_text]).tolist(),
                metadatas=[meta],
                documents=existing["documents"][0] if existing.get("documents") else [normalized_text]
            )
            print(f"[Cache] Flagged entry as failed: {normalized_text[:60]}")
            return True
        except Exception as e:
            print(f"[Cache] Warning: could not flag entry: {e}")
            return False

    def clear(self) -> None:
        """Clear all entries from the cache."""
        self.client.delete_collection(self.COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

    def delete(self, normalized_text: str) -> bool:
        """
        Delete a specific query from the cache.

        Args:
            normalized_text: Normalized query string to delete

        Returns:
            True if entry was found and deleted, False otherwise
        """
        doc_id = hashlib.sha256(normalized_text.encode()).hexdigest()

        try:
            existing = self.collection.get(ids=[doc_id])
            if not existing["ids"]:
                return False

            self.collection.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def get_all(self) -> list:
        """
        Get all cached entries including metadata.

        Returns:
            List of dicts with query, sql, validated_at, execution_success, row_count
        """
        if self.collection.count() == 0:
            return []

        results = self.collection.get(
            include=["metadatas", "documents"]
        )

        entries = []
        for i, doc_id in enumerate(results["ids"]):
            metadata = results["metadatas"][i] if results["metadatas"] else {}
            entries.append({
                "id":               doc_id,
                "query":            metadata.get("query", ""),
                "sql":              metadata.get("sql", ""),
                "validated_at":     metadata.get("validated_at", None),
                "execution_success": metadata.get("execution_success", "true") == "true",
                "row_count":        metadata.get("row_count", None),
            })

        return entries

    def count(self) -> int:
        """Return number of cached entries."""
        return self.collection.count()


# ── Self-test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import shutil
    import time

    TEST_PATH = "cache_store_test"

    if os.path.exists(TEST_PATH):
        shutil.rmtree(TEST_PATH)

    print("Testing Semantic Cache...")
    print("=" * 80)

    cache = SemanticCache(persist_path=TEST_PATH)

    # Wait for background model load
    print("\n[Setup] Waiting for embedding model to load...")
    cache._model_ready.wait(timeout=60)
    assert cache.is_model_ready, "Model failed to load within 60s"
    print("[Setup] Model ready.\n")

    # ── Test 1: Store and exact lookup ────────────────────────────────────────
    print("[Test 1] Store and exact lookup")
    query = "show average cpu busy time per cpu"
    sql   = "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000"

    cache.store(query, sql, execution_success=True, row_count=16)
    result = cache.lookup(query)

    print(f"  Hit: {result.hit}  |  Confidence: {result.confidence}")
    assert result.hit,                "✗ Expected cache hit"
    assert result.confidence >= 0.95, "✗ Expected confidence ≥ 0.95"
    assert result.sql == sql,         "✗ SQL mismatch"
    print("  ✓ PASSED")

    # ── Test 2: Semantically similar query ────────────────────────────────────
    print("\n[Test 2] Semantically similar query")
    similar = "show mean cpu busy time grouped by cpu"
    result2 = cache.lookup(similar)
    print(f"  Hit: {result2.hit}  |  Confidence: {result2.confidence}")
    assert result2.hit, "✗ Expected cache hit for similar query"
    print("  ✓ PASSED")

    # ── Test 3: Unrelated query (should miss) ─────────────────────────────────
    print("\n[Test 3] Unrelated query — should miss")
    unrelated = "list all disk device read write counts"
    result3 = cache.lookup(unrelated)
    print(f"  Hit: {result3.hit}  |  Confidence: {result3.confidence}")
    assert not result3.hit, "✗ Expected cache miss for unrelated query"
    print("  ✓ PASSED")

    # ── Test 4: Metadata fields ───────────────────────────────────────────────
    print("\n[Test 4] Metadata fields in get_all()")
    entries = cache.get_all()
    assert len(entries) == 1, f"✗ Expected 1 entry, got {len(entries)}"
    e = entries[0]
    assert e["execution_success"] is True,  "✗ execution_success should be True"
    assert e["row_count"] == 16,            "✗ row_count should be 16"
    assert e["validated_at"] is not None,   "✗ validated_at should be set"
    print(f"  validated_at:     {e['validated_at']}")
    print(f"  execution_success: {e['execution_success']}")
    print(f"  row_count:         {e['row_count']}")
    print("  ✓ PASSED")

    # ── Test 5: flag_failed auto-skips entry ──────────────────────────────────
    print("\n[Test 5] flag_failed() causes lookup to skip entry")
    cache.flag_failed(query)
    result5 = cache.lookup(query)
    print(f"  Hit after flag: {result5.hit}  (expected False)")
    assert not result5.hit, "✗ Flagged entry should not be returned"
    print("  ✓ PASSED")

    # ── Test 6: Runtime threshold ─────────────────────────────────────────────
    print("\n[Test 6] Runtime threshold adjustment")
    # Re-store without failure flag
    cache.store(query, sql, execution_success=True, row_count=16)
    original = cache.get_threshold()
    cache.set_threshold(0.50)
    assert cache.get_threshold() == 0.50, "✗ Threshold not updated"
    cache.set_threshold(original)
    print(f"  Threshold round-trip: {original} → 0.50 → {cache.get_threshold()}")
    print("  ✓ PASSED")

    # ── Test 7: Persistence ───────────────────────────────────────────────────
    print("\n[Test 7] Persistence across instances")
    cache2 = SemanticCache(persist_path=TEST_PATH)
    cache2._model_ready.wait(timeout=60)
    result7 = cache2.lookup(query)
    print(f"  Hit: {result7.hit}  |  Confidence: {result7.confidence}")
    assert result7.hit, "✗ Expected cache hit after reload"
    print("  ✓ PASSED")

    # Cleanup
    del cache
    del cache2
    import gc; gc.collect()
    time.sleep(0.5)
    shutil.rmtree(TEST_PATH, ignore_errors=True)

    print("\n" + "=" * 80)
    print("✓ All Semantic Cache tests passed!")
    print("=" * 80)
