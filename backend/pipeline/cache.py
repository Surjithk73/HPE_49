"""
Semantic Cache for QueryCraft
ChromaDB-backed cache using sentence-transformers embeddings.
"""
import hashlib
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from config import CACHE_SIMILARITY_THRESHOLD
except (ValueError, ImportError):
    CACHE_SIMILARITY_THRESHOLD = 0.95

import chromadb
from sentence_transformers import SentenceTransformer


class CacheResult:
    """Result of a cache lookup."""

    def __init__(self, hit: bool, sql: Optional[str] = None, confidence: float = 0.0):
        self.hit = hit
        self.sql = sql
        self.confidence = confidence

    def to_dict(self):
        return {'hit': self.hit, 'sql': self.sql, 'confidence': self.confidence}


class SemanticCache:
    """Semantic query cache backed by ChromaDB + sentence-transformers."""

    COLLECTION_NAME = "querycraft_cache"
    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self, persist_path: str = "cache_store",
                 threshold: float = CACHE_SIMILARITY_THRESHOLD):
        """
        Initialize the semantic cache.

        Args:
            persist_path: Directory for ChromaDB persistent storage
            threshold: Cosine similarity threshold for cache hit (default 0.95)
        """
        self.threshold = threshold

        # Ensure directory exists
        os.makedirs(persist_path, exist_ok=True)

        # Initialize ChromaDB with cosine distance metric
        self.client = chromadb.PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}   # cosine distance → similarity = 1 - distance
        )

        # Load embedding model
        print(f"[Cache] Loading embedding model '{self.MODEL_NAME}'...")
        self.model = SentenceTransformer(self.MODEL_NAME)
        print(f"[Cache] Model loaded. Collection has {self.collection.count()} entries.")

    def lookup(self, normalized_text: str) -> CacheResult:
        """
        Look up a query in the cache.

        Args:
            normalized_text: Normalized query string

        Returns:
            CacheResult with hit status, SQL, and confidence score
        """
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
        distance = results["distances"][0][0]
        confidence = 1.0 - distance

        if confidence >= self.threshold:
            sql = results["metadatas"][0][0].get("sql", "")
            return CacheResult(hit=True, sql=sql, confidence=round(confidence, 4))

        return CacheResult(hit=False, confidence=round(confidence, 4))

    def store(self, normalized_text: str, sql: str) -> None:
        """
        Store a query→SQL pair in the cache.

        Args:
            normalized_text: Normalized query string
            sql: Validated SQL to cache
        """
        # Use hash of normalized text as unique ID
        doc_id = hashlib.sha256(normalized_text.encode()).hexdigest()

        # Embed the query
        embedding = self.model.encode([normalized_text]).tolist()

        # Upsert — overwrite if same query stored before
        self.collection.upsert(
            ids=[doc_id],
            embeddings=embedding,
            metadatas=[{"sql": sql, "query": normalized_text}],
            documents=[normalized_text]
        )

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
        # Use hash of normalized text as unique ID
        doc_id = hashlib.sha256(normalized_text.encode()).hexdigest()

        try:
            # Check if entry exists
            existing = self.collection.get(ids=[doc_id])
            if not existing["ids"]:
                return False

            # Delete the entry
            self.collection.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def get_all(self) -> list:
        """
        Get all cached entries.

        Returns:
            List of dicts with 'query', 'sql', and 'id' keys
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
                "id": doc_id,
                "query": metadata.get("query", ""),
                "sql": metadata.get("sql", "")
            })

        return entries

    def count(self) -> int:
        """Return number of cached entries."""
        return self.collection.count()


# ── Self-test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import shutil

    TEST_PATH = "cache_store_test"

    # Clean up any previous test run
    if os.path.exists(TEST_PATH):
        shutil.rmtree(TEST_PATH)

    print("Testing Semantic Cache...")
    print("=" * 80)

    cache = SemanticCache(persist_path=TEST_PATH)

    # ── Test 1: Store and exact lookup ────────────────────────────────────────
    print("\n[Test 1] Store and exact lookup")
    query = "show average cpu busy time per cpu"
    sql   = "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000"

    cache.store(query, sql)
    result = cache.lookup(query)

    print(f"  Hit: {result.hit}  |  Confidence: {result.confidence}")
    assert result.hit,                    "✗ Expected cache hit"
    assert result.confidence >= 0.95,     "✗ Expected confidence ≥ 0.95"
    assert result.sql == sql,             "✗ SQL mismatch"
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

    # ── Test 4: Persistence ───────────────────────────────────────────────────
    print("\n[Test 4] Persistence across instances")
    cache2 = SemanticCache(persist_path=TEST_PATH)
    result4 = cache2.lookup(query)

    print(f"  Hit: {result4.hit}  |  Confidence: {result4.confidence}")
    assert result4.hit, "✗ Expected cache hit after reload"
    print("  ✓ PASSED")

    # ── Test 5: Multiple entries ──────────────────────────────────────────────
    print("\n[Test 5] Multiple entries")
    entries = [
        ("list disk reads and writes per device",
         "SELECT device_name, SUM(reads_) FROM macht413.disc GROUP BY device_name LIMIT 10000"),
        ("show transaction backout count",
         "SELECT COUNT(*) FROM macht413.tmf WHERE backouts > 0 LIMIT 10000"),
        ("count file opens per system",
         "SELECT system_name, COUNT(*) FROM macht413.file GROUP BY system_name LIMIT 10000"),
    ]
    for q, s in entries:
        cache.store(q, s)

    print(f"  Total cached entries: {cache.count()}")
    assert cache.count() == 4, f"✗ Expected 4 entries, got {cache.count()}"

    # Each stored query should hit
    for q, s in entries:
        r = cache.lookup(q)
        assert r.hit, f"✗ Expected hit for '{q}'"
    print("  ✓ All 3 new entries hit correctly")
    print("  ✓ PASSED")

    # Cleanup — close clients before deleting on Windows
    del cache
    del cache2
    import gc; gc.collect()
    import time; time.sleep(0.5)
    shutil.rmtree(TEST_PATH, ignore_errors=True)

    print("\n" + "=" * 80)
    print("✓ All Semantic Cache tests passed!")
    print("=" * 80)
