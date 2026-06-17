"""
Comprehensive tests for Semantic Cache
"""
import sys
import os
import shutil
import gc
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline.cache import SemanticCache
from pipeline.normalizer import QueryNormalizer

BASE_TEST_PATH = os.path.join(os.path.dirname(__file__), "cache_store_test")
_normalizer = QueryNormalizer()


def _norm(q: str) -> str:
    return _normalizer.normalize(q)["normalized_text"]


def _make_cache(suffix=""):
    path = BASE_TEST_PATH + suffix
    shutil.rmtree(path, ignore_errors=True)
    return SemanticCache(persist_path=path), path


def _teardown(cache, path):
    del cache
    gc.collect()
    time.sleep(0.3)
    shutil.rmtree(path, ignore_errors=True)


def test_exact_lookup():
    """Exact same query must return hit with confidence >= 0.90."""
    print("\n" + "=" * 80)
    print("TEST 1: Exact Lookup")
    print("=" * 80)

    cache, path = _make_cache("_t1")
    query = "show average cpu busy time per cpu"
    sql   = "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000"

    cache.store(_norm(query), sql)
    result = cache.lookup(_norm(query))
    print(f"  Hit: {result.hit}  |  Confidence: {result.confidence}")

    ok = result.hit and result.confidence >= 0.90 and result.sql == sql
    print("  PASSED" if ok else "  FAILED")
    _teardown(cache, path)
    return ok


def test_similar_query():
    """Semantically similar query must return hit."""
    print("\n" + "=" * 80)
    print("TEST 2: Semantically Similar Query")
    print("=" * 80)

    cache, path = _make_cache("_t2")
    cache.set_threshold(0.90)
    cache.store(
        _norm("show average cpu busy time per cpu"),
        "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000"
    )

    similar_queries = [
        "show mean cpu busy time grouped by cpu",
        "average cpu busy time by cpu number",
    ]

    passed = 0
    for q in similar_queries:
        r = cache.lookup(_norm(q))
        print(f"  '{q}' -> hit={r.hit}, confidence={r.confidence}")
        if r.hit:
            passed += 1

    _teardown(cache, path)
    ok = passed == len(similar_queries)
    print(f"  {'PASSED' if ok else 'FAILED'} ({passed}/{len(similar_queries)})")
    return ok


def test_unrelated_miss():
    """Completely different query must return miss."""
    print("\n" + "=" * 80)
    print("TEST 3: Unrelated Query - Cache Miss")
    print("=" * 80)

    cache, path = _make_cache("_t3")
    cache.store(
        _norm("show average cpu busy time per cpu"),
        "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000"
    )

    unrelated = [
        "list all disk device read write counts",
        "show transaction backout statistics",
        "count file opens per system name",
    ]

    passed = 0
    for q in unrelated:
        r = cache.lookup(_norm(q))
        print(f"  '{q}' -> hit={r.hit}, confidence={r.confidence}")
        if not r.hit:
            passed += 1

    _teardown(cache, path)
    ok = passed == len(unrelated)
    print(f"  {'PASSED' if ok else 'FAILED'} ({passed}/{len(unrelated)} correctly missed)")
    return ok


def test_persistence():
    """Data must survive across SemanticCache instances."""
    print("\n" + "=" * 80)
    print("TEST 4: Persistence Across Instances")
    print("=" * 80)

    path = BASE_TEST_PATH + "_t4"
    shutil.rmtree(path, ignore_errors=True)

    query = "show average cpu busy time per cpu"
    sql   = "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000"

    cache1 = SemanticCache(persist_path=path)
    cache1.store(_norm(query), sql)
    del cache1; gc.collect(); time.sleep(0.3)

    cache2 = SemanticCache(persist_path=path)
    result = cache2.lookup(_norm(query))
    print(f"  Hit: {result.hit}  |  Confidence: {result.confidence}")

    _teardown(cache2, path)
    ok = result.hit and result.sql == sql
    print(f"  {'PASSED' if ok else 'FAILED'}")
    return ok


def test_upsert():
    """Storing the same query twice should update, not duplicate."""
    print("\n" + "=" * 80)
    print("TEST 5: Upsert (No Duplicates)")
    print("=" * 80)

    cache, path = _make_cache("_t5")
    query  = "show cpu busy time"
    sql_v1 = "SELECT cpu_busy_time FROM macht413.cpu LIMIT 10000"
    sql_v2 = "SELECT cpu_num, cpu_busy_time FROM macht413.cpu LIMIT 10000"

    cache.store(_norm(query), sql_v1)
    cache.store(_norm(query), sql_v2)

    count  = cache.count()
    result = cache.lookup(_norm(query))
    print(f"  Count: {count}  |  SQL: {result.sql[:60]}...")

    _teardown(cache, path)
    ok = count == 1 and result.sql == sql_v2
    print(f"  {'PASSED' if ok else 'FAILED'}")
    return ok


def test_empty_cache():
    """Lookup on empty cache must return miss without error."""
    print("\n" + "=" * 80)
    print("TEST 6: Empty Cache Lookup")
    print("=" * 80)

    cache, path = _make_cache("_t6")
    result = cache.lookup(_norm("show cpu busy time"))
    print(f"  Hit: {result.hit}  |  Confidence: {result.confidence}")

    _teardown(cache, path)
    ok = not result.hit and result.confidence == 0.0
    print(f"  {'PASSED' if ok else 'FAILED'}")
    return ok


def test_entity_filter_matching():
    """Verify SOTA 1 entity and filter matching constraints."""
    print("\n" + "=" * 80)
    print("TEST 7: SOTA 1 Entity & Filter Matching")
    print("=" * 80)

    cache, path = _make_cache("_t7")
    cache.set_threshold(0.90)

    # Store standard query
    q1 = "List the top 8 process names by CPU time"
    sql1 = "SELECT process_name, cpu_busy_time FROM macht413.proc ORDER BY cpu_busy_time DESC LIMIT 8"
    cache.store(_norm(q1), sql1)

    # 1. Look up identical query -> should HIT
    r1 = cache.lookup(_norm(q1))
    print(f"  Identical query hit: {r1.hit} (expected True)")

    # 2. Look up similar query with different number (top 10) -> should MISS
    q2 = "List the top 10 process names by CPU time"
    r2 = cache.lookup(_norm(q2))
    print(f"  Different number (8 vs 10) hit: {r2.hit} (expected False)")

    # 3. Look up query with different entity/table (disk instead of process) -> should MISS
    q3 = "List the top 8 disk names by CPU time"
    r3 = cache.lookup(_norm(q3))
    print(f"  Different entity (process vs disk) hit: {r3.hit} (expected False)")

    # 4. Look up query with singular/plural variations and stopword changes -> should HIT
    q4 = "show top 8 processes by cpu time"
    r4 = cache.lookup(_norm(q4))
    print(f"  Plural and stopword variation hit: {r4.hit} (expected True)")

    # Store query with quoted value
    q5 = "List process details for 'chrome'"
    sql5 = "SELECT * FROM macht413.proc WHERE process_name = 'chrome'"
    cache.store(_norm(q5), sql5)

    # 5. Look up query with different quoted value -> should MISS
    q6 = "List process details for 'explorer'"
    r6 = cache.lookup(_norm(q6))
    print(f"  Different quoted value ('chrome' vs 'explorer') hit: {r6.hit} (expected False)")

    _teardown(cache, path)

    ok = (r1.hit is True and
          r2.hit is False and
          r3.hit is False and
          r4.hit is True and
          r6.hit is False)
    print(f"  {'PASSED' if ok else 'FAILED'}")
    return ok


def run_all_tests():
    print("\n" + "=" * 80)
    print("SEMANTIC CACHE - COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    # Wait for shared embedding model thread to load
    print("Waiting for embedding model to load...")
    cache, path = _make_cache("_init")
    cache._model_ready.wait(timeout=60)
    _teardown(cache, path)
    print("Embedding model ready. Running tests...\n")

    results = [
        ("Exact Lookup",            test_exact_lookup()),
        ("Similar Query Hit",       test_similar_query()),
        ("Unrelated Query Miss",    test_unrelated_miss()),
        ("Persistence",             test_persistence()),
        ("Upsert / No Duplicates",  test_upsert()),
        ("Empty Cache Lookup",      test_empty_cache()),
        ("SOTA 1 Entity Matching",  test_entity_filter_matching()),
    ]

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for name, passed in results:
        print(f"{name:30s}: {'PASSED' if passed else 'FAILED'}")

    all_passed = all(r[1] for r in results)
    print("\n" + "=" * 80)
    print("ALL CACHE TESTS PASSED" if all_passed else "SOME TESTS FAILED")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
