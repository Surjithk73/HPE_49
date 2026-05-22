"""
Semantic Cache for QueryCraft
ChromaDB-backed cache using BAAI/bge-large-en-v1.5 embeddings.

Improvements:
- Background thread model load — API available immediately, cache returns misses until ready
- Cache entry metadata: validated_at, execution_success, row_count for auditability
- Runtime threshold adjustment via set_threshold() / get_threshold()
"""
import hashlib
import sys
import os
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from config import CACHE_SIMILARITY_THRESHOLD
except (ValueError, ImportError):
    CACHE_SIMILARITY_THRESHOLD = 0.95

import chromadb
from sentence_transformers import SentenceTransformer

try:
    from pipeline import embeddings
except ImportError:
    import embeddings  # type: ignore


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

    The embedding model is loaded in a background thread so the API is
    available immediately on startup.  While the model is loading every
    lookup returns a cache miss (safe fallback — the LLM pipeline runs
    normally).  Once the thread finishes, caching works as usual.
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

        # Shared embedding model — kicks off background load on first caller.
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
            if not stored_embeddings or not stored_embeddings[0]:
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

    def lookup(self, normalized_text: str) -> CacheResult:
        """
        Look up a query in the cache.

        Returns a miss immediately if the embedding model is not yet ready.

        Args:
            normalized_text: Normalized query string

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

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=embedding,
            n_results=1,
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

            return CacheResult(hit=True, sql=sql, confidence=round(confidence, 4))

        return CacheResult(hit=False, confidence=round(confidence, 4))

    def store(
        self,
        normalized_text: str,
        sql: str,
        execution_success: bool = True,
        row_count: Optional[int] = None,
    ) -> None:
        """
        Store a query→SQL pair in the cache with execution metadata.

        Args:
            normalized_text:   Normalized query string
            sql:               Validated SQL to cache
            execution_success: Whether the query executed without error
            row_count:         Number of rows returned (None if unknown)
        """
        # Model not ready — skip silently (entry will be stored on next successful run)
        if not self.is_model_ready:
            print("[Cache] Model not ready — skipping store.")
            return

        # Use hash of normalized text as unique ID
        doc_id = hashlib.sha256(normalized_text.encode()).hexdigest()

        # Embed the query
        embedding = self.model.encode([normalized_text]).tolist()

        # Build metadata — ChromaDB only supports str/int/float/bool values
        metadata: dict = {
            "sql":               sql,
            "query":             normalized_text,
            "validated_at":      datetime.now(timezone.utc).isoformat(),
            "execution_success": "true" if execution_success else "false",
        }
        if row_count is not None:
            metadata["row_count"] = row_count

        # Upsert — overwrite if same query stored before
        self.collection.upsert(
            ids=[doc_id],
            embeddings=embedding,
            metadatas=[metadata],
            documents=[normalized_text]
        )

    def flag_failed(self, normalized_text: str) -> bool:
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

        doc_id = hashlib.sha256(normalized_text.encode()).hexdigest()

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
