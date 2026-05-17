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

BASE_TEST_PATH = os.path.join(os.path.dirname(__file__), "cache_store_test")


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
    """Exact same query must return hit with confidence ≥ 0.95."""
    print("\n" + "=" * 80)
    print("TEST 1: Exact Lookup")
    print("=" * 80)

    cache, path = _make_cache("_t1")
    query = "show average cpu busy time per cpu"
    sql   = "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000"

    cache.store(query, sql)
    result = cache.lookup(query)
    print(f"  Hit: {result.hit}  |  Confidence: {result.confidence}")

    ok = result.hit and result.confidence >= 0.95 and result.sql == sql
    print("  ✓ PASSED" if ok else "  ✗ FAILED")
    _teardown(cache, path)
    return ok


def test_similar_query():
    """Semantically similar query must return hit."""
    print("\n" + "=" * 80)
    print("TEST 2: Semantically Similar Query")
    print("=" * 80)

    cache, path = _make_cache("_t2")
    cache.store(
        "show average cpu busy time per cpu",
        "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000"
    )

    similar_queries = [
        "show mean cpu busy time grouped by cpu",
        "average cpu busy time by cpu number",
    ]

    passed = 0
    for q in similar_queries:
        r = cache.lookup(q)
        print(f"  '{q}' → hit={r.hit}, confidence={r.confidence}")
        if r.hit:
            passed += 1

    _teardown(cache, path)
    ok = passed == len(similar_queries)
    print(f"  {'✓ PASSED' if ok else '✗ FAILED'} ({passed}/{len(similar_queries)})")
    return ok


def test_unrelated_miss():
    """Completely different query must return miss."""
    print("\n" + "=" * 80)
    print("TEST 3: Unrelated Query — Cache Miss")
    print("=" * 80)

    cache, path = _make_cache("_t3")
    cache.store(
        "show average cpu busy time per cpu",
        "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000"
    )

    unrelated = [
        "list all disk device read write counts",
        "show transaction backout statistics",
        "count file opens per system name",
    ]

    passed = 0
    for q in unrelated:
        r = cache.lookup(q)
        print(f"  '{q}' → hit={r.hit}, confidence={r.confidence}")
        if not r.hit:
            passed += 1

    _teardown(cache, path)
    ok = passed == len(unrelated)
    print(f"  {'✓ PASSED' if ok else '✗ FAILED'} ({passed}/{len(unrelated)} correctly missed)")
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
    cache1.store(query, sql)
    del cache1; gc.collect(); time.sleep(0.3)

    cache2 = SemanticCache(persist_path=path)
    result = cache2.lookup(query)
    print(f"  Hit: {result.hit}  |  Confidence: {result.confidence}")

    _teardown(cache2, path)
    ok = result.hit and result.sql == sql
    print(f"  {'✓ PASSED' if ok else '✗ FAILED'}")
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

    cache.store(query, sql_v1)
    cache.store(query, sql_v2)

    count  = cache.count()
    result = cache.lookup(query)
    print(f"  Count: {count}  |  SQL: {result.sql[:60]}...")

    _teardown(cache, path)
    ok = count == 1 and result.sql == sql_v2
    print(f"  {'✓ PASSED' if ok else '✗ FAILED'}")
    return ok


def test_empty_cache():
    """Lookup on empty cache must return miss without error."""
    print("\n" + "=" * 80)
    print("TEST 6: Empty Cache Lookup")
    print("=" * 80)

    cache, path = _make_cache("_t6")
    result = cache.lookup("show cpu busy time")
    print(f"  Hit: {result.hit}  |  Confidence: {result.confidence}")

    _teardown(cache, path)
    ok = not result.hit and result.confidence == 0.0
    print(f"  {'✓ PASSED' if ok else '✗ FAILED'}")
    return ok


def run_all_tests():
    print("\n" + "=" * 80)
    print("SEMANTIC CACHE — COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    results = [
        ("Exact Lookup",            test_exact_lookup()),
        ("Similar Query Hit",       test_similar_query()),
        ("Unrelated Query Miss",    test_unrelated_miss()),
        ("Persistence",             test_persistence()),
        ("Upsert / No Duplicates",  test_upsert()),
        ("Empty Cache Lookup",      test_empty_cache()),
    ]

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for name, passed in results:
        print(f"{name:30s}: {'✓ PASSED' if passed else '✗ FAILED'}")

    all_passed = all(r[1] for r in results)
    print("\n" + "=" * 80)
    print("✓ ALL CACHE TESTS PASSED" if all_passed else "✗ SOME TESTS FAILED")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
