"""
Comprehensive tests for Query Normalizer
Tests normal operation and edge cases.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline.normalizer import QueryNormalizer

def test_normal_operation():
    """Test normal query normalization."""
    print("\n" + "=" * 60)
    print("TEST 1: Normal Operation")
    print("=" * 60)
    
    normalizer = QueryNormalizer()
    passed = 0
    failed = 0
    
    test_cases = [
        ("Show CPU busy time", "cpu", "Basic CPU query"),
        ("List all processes", "proc", "Basic process query"),
        ("Disk reads and writes", "disc", "Basic disc query"),
        ("Transaction backouts", "tmf", "Basic TMF query"),
        ("Show file read and write counts", "file", "Basic file query"),
        ("OSS namespace stats", "ossns", "Basic OSSNS query"),
        ("User defined metrics", "udef", "Basic UDEF query"),
        ("Show dfile data", "dfile", "Basic DFILE query"),
        ("File opener stats", "dopen", "Basic DOPEN query"),
    ]
    
    for query, expected_domain, description in test_cases:
        result = normalizer.normalize(query)
        if result['domain_category'] == expected_domain:
            print(f"[OK] {description:25s}: '{query}' -> {expected_domain}")
            passed += 1
        else:
            print(f"[FAIL] {description:25s}: Expected {expected_domain}, got {result['domain_category']}")
            failed += 1
    
    print(f"\nNormal Operation: {passed} passed, {failed} failed")
    return failed == 0


def test_abbreviation_expansion():
    """Test abbreviation expansion."""
    print("\n" + "=" * 60)
    print("TEST 2: Abbreviation Expansion")
    print("=" * 60)
    
    normalizer = QueryNormalizer()
    passed = 0
    failed = 0
    
    test_cases = [
        ("show proc data", "process", "proc -> process"),
        ("cpu util", "utilization", "util -> utilization"),
        ("disk reads", "disc", "disk -> disc"),
        ("transaction count", "tmf", "transaction -> tmf"),
    ]
    
    for query, expected_word, description in test_cases:
        result = normalizer.normalize(query)
        normalized = result['normalized_text']
        if expected_word in normalized:
            print(f"[OK] {description:25s}: '{query}' contains '{expected_word}'")
            passed += 1
        else:
            print(f"[FAIL] {description:25s}: '{normalized}' missing '{expected_word}'")
            failed += 1
    
    print(f"\nAbbreviation Expansion: {passed} passed, {failed} failed")
    return failed == 0


def test_edge_cases():
    """Test edge cases."""
    print("\n" + "=" * 60)
    print("TEST 3: Edge Cases")
    print("=" * 60)
    
    normalizer = QueryNormalizer()
    passed = 0
    failed = 0
    
    # Test 3.1: Empty string
    result = normalizer.normalize("")
    if result['normalized_text'] == '' and result['domain_category'] == 'multi':
        print("[OK] Empty string handled correctly")
        passed += 1
    else:
        print(f"[FAIL] Empty string: got {result}")
        failed += 1
    
    # Test 3.2: Whitespace only
    result = normalizer.normalize("   \t\n  ")
    if result['normalized_text'] == '' and result['domain_category'] == 'multi':
        print("[OK] Whitespace-only string handled correctly")
        passed += 1
    else:
        print(f"[FAIL] Whitespace-only: got {result}")
        failed += 1
    
    # Test 3.3: Very long query
    long_query = "show cpu " * 100
    result = normalizer.normalize(long_query)
    if result['domain_category'] == 'cpu':
        print("[OK] Very long query handled correctly")
        passed += 1
    else:
        print(f"[FAIL] Long query: got {result['domain_category']}")
        failed += 1
    
    # Test 3.4: Special characters
    result = normalizer.normalize("show cpu@#$%^&*()data")
    if 'cpu' in result['normalized_text']:
        print("[OK] Special characters handled")
        passed += 1
    else:
        print(f"[FAIL] Special chars: got {result['normalized_text']}")
        failed += 1
    
    # Test 3.5: Mixed case
    result = normalizer.normalize("ShOw CPU BuSy TiMe")
    if result['normalized_text'] == result['normalized_text'].lower():
        print("[OK] Mixed case normalized to lowercase")
        passed += 1
    else:
        print(f"[FAIL] Mixed case: got {result['normalized_text']}")
        failed += 1
    
    # Test 3.6: Numbers in query
    result = normalizer.normalize("show cpu 0 and cpu 1 data")
    if result['domain_category'] == 'cpu':
        print("[OK] Numbers in query handled")
        passed += 1
    else:
        print(f"[FAIL] Numbers: got {result['domain_category']}")
        failed += 1
    
    # Test 3.7: Query with no domain keywords
    result = normalizer.normalize("show me some data")
    if result['domain_category'] == 'multi':
        print("[OK] No domain keywords -> multi")
        passed += 1
    else:
        print(f"[FAIL] No keywords: got {result['domain_category']}")
        failed += 1
    
    # Test 3.8: Unicode characters
    result = normalizer.normalize("show cpu données")
    if 'cpu' in result['normalized_text']:
        print("[OK] Unicode characters handled")
        passed += 1
    else:
        print(f"[FAIL] Unicode: got {result['normalized_text']}")
        failed += 1
    
    print(f"\nEdge Cases: {passed} passed, {failed} failed")
    return failed == 0


def test_multi_domain_detection():
    """Test multi-domain query detection."""
    print("\n" + "=" * 60)
    print("TEST 4: Multi-Domain Detection")
    print("=" * 60)
    
    normalizer = QueryNormalizer()
    passed = 0
    failed = 0
    
    test_cases = [
        ("show cpu and process data", "multi", "CPU + Process"),
        ("compare disc reads and file reads", "multi", "Disc + File"),
        ("transaction and process info", "multi", "TMF + Process"),
        ("cpu utilization and disc space", "multi", "CPU + Disc"),
    ]
    
    for query, expected_domain, description in test_cases:
        result = normalizer.normalize(query)
        if result['domain_category'] == expected_domain:
            print(f"[OK] {description:25s}: '{query}' -> {expected_domain}")
            passed += 1
        else:
            print(f"[FAIL] {description:25s}: Expected {expected_domain}, got {result['domain_category']}")
            failed += 1
    
    print(f"\nMulti-Domain Detection: {passed} passed, {failed} failed")
    return failed == 0


def test_case_insensitivity():
    """Test case insensitivity."""
    print("\n" + "=" * 60)
    print("TEST 5: Case Insensitivity")
    print("=" * 60)
    
    normalizer = QueryNormalizer()
    passed = 0
    failed = 0
    
    queries = [
        "show CPU data",
        "show cpu data",
        "show Cpu data",
        "SHOW CPU DATA",
        "ShOw CpU dAtA",
    ]
    
    results = [normalizer.normalize(q) for q in queries]
    
    # All should produce same normalized text
    normalized_texts = [r['normalized_text'] for r in results]
    if len(set(normalized_texts)) == 1:
        print(f"[OK] All case variations produce same normalized text: '{normalized_texts[0]}'")
        passed += 1
    else:
        print(f"[FAIL] Different normalized texts: {set(normalized_texts)}")
        failed += 1
    
    # All should produce same domain
    domains = [r['domain_category'] for r in results]
    if len(set(domains)) == 1:
        print(f"[OK] All case variations produce same domain: '{domains[0]}'")
        passed += 1
    else:
        print(f"[FAIL] Different domains: {set(domains)}")
        failed += 1
    
    print(f"\nCase Insensitivity: {passed} passed, {failed} failed")
    return failed == 0


def test_whitespace_handling():
    """Test whitespace handling."""
    print("\n" + "=" * 60)
    print("TEST 6: Whitespace Handling")
    print("=" * 60)
    
    normalizer = QueryNormalizer()
    passed = 0
    failed = 0
    
    queries = [
        "show cpu data",
        "  show cpu data  ",
        "show  cpu  data",
        "show\tcpu\tdata",
        "show\ncpu\ndata",
    ]
    
    results = [normalizer.normalize(q) for q in queries]
    
    # All should strip leading/trailing whitespace
    for i, result in enumerate(results):
        text = result['normalized_text']
        if text == text.strip():
            passed += 1
        else:
            print(f"[FAIL] Query {i+1} not stripped: '{text}'")
            failed += 1
    
    if failed == 0:
        print(f"[OK] All {len(queries)} queries properly stripped")
    
    print(f"\nWhitespace Handling: {passed} passed, {failed} failed")
    return failed == 0


def test_performance():
    """Test performance characteristics."""
    print("\n" + "=" * 60)
    print("TEST 7: Performance")
    print("=" * 60)
    
    import time
    
    normalizer = QueryNormalizer()
    
    # Test 7.1: Single normalization time
    query = "show cpu busy time for all processors"
    start = time.time()
    result = normalizer.normalize(query)
    single_time = time.time() - start
    print(f"[OK] Single normalization: {single_time*1000:.4f}ms")
    
    # Test 7.2: Batch normalization time
    queries = [
        "show cpu data",
        "list processes",
        "disk statistics",
        "transaction info",
        "file operations",
    ] * 200  # 1000 queries
    
    start = time.time()
    for q in queries:
        normalizer.normalize(q)
    batch_time = time.time() - start
    avg_time = batch_time / len(queries)
    
    print(f"[OK] Batch normalization: {len(queries)} queries in {batch_time*1000:.2f}ms")
    print(f"[OK] Average per query: {avg_time*1000:.4f}ms")
    
    if avg_time > 0.01:  # 10ms threshold
        print(f"  ⚠ Average time exceeds 10ms threshold")
    
    return True


def test_consistency():
    """Test consistency of results."""
    print("\n" + "=" * 60)
    print("TEST 8: Consistency")
    print("=" * 60)
    
    normalizer = QueryNormalizer()
    passed = 0
    failed = 0
    
    # Test 8.1: Same query produces same result
    query = "show cpu busy time"
    results = [normalizer.normalize(query) for _ in range(10)]
    
    normalized_texts = [r['normalized_text'] for r in results]
    domains = [r['domain_category'] for r in results]
    
    if len(set(normalized_texts)) == 1 and len(set(domains)) == 1:
        print("[OK] Same query produces consistent results (10 iterations)")
        passed += 1
    else:
        print("[FAIL] Inconsistent results for same query")
        failed += 1
    
    # Test 8.2: Normalizer is stateless
    normalizer1 = QueryNormalizer()
    normalizer2 = QueryNormalizer()
    
    result1 = normalizer1.normalize("show cpu data")
    result2 = normalizer2.normalize("show cpu data")
    
    if result1 == result2:
        print("[OK] Different normalizer instances produce same results")
        passed += 1
    else:
        print("[FAIL] Different instances produce different results")
        failed += 1
    
    print(f"\nConsistency: {passed} passed, {failed} failed")
    return failed == 0


def run_all_tests():
    """Run all test suites."""
    print("\n" + "=" * 70)
    print("QUERY NORMALIZER - COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    
    results = []
    
    results.append(("Normal Operation", test_normal_operation()))
    results.append(("Abbreviation Expansion", test_abbreviation_expansion()))
    results.append(("Edge Cases", test_edge_cases()))
    results.append(("Multi-Domain Detection", test_multi_domain_detection()))
    results.append(("Case Insensitivity", test_case_insensitivity()))
    results.append(("Whitespace Handling", test_whitespace_handling()))
    results.append(("Performance", test_performance()))
    results.append(("Consistency", test_consistency()))
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for name, passed in results:
        status = "[OK] PASSED" if passed else "[FAIL] FAILED"
        print(f"{name:30s}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("[OK] ALL TESTS PASSED")
    else:
        print("[FAIL] SOME TESTS FAILED")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
