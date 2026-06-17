"""
Phase 8 — API endpoint tests
Requires the server to be running on http://localhost:8000
"""
import sys
import os
import time
import json

import requests

BASE = "http://localhost:8000"


def _get(path):
    return requests.get(f"{BASE}{path}", timeout=60)

def _post(path, body):
    return requests.post(f"{BASE}{path}", json=body, timeout=60)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_health():
    print("\n" + "=" * 80)
    print("TEST 1: GET /api/health")
    print("=" * 80)

    r = _get("/api/health")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()

    print(f"  Response: {json.dumps(data, indent=2)}")

    checks = [
        data.get("status") == "ok",
        data.get("db_connected") is True,
        data.get("cache_ready") is True,
        "llm_model" in data,
    ]
    ok = all(checks)
    print(f"\n  {'[OK] PASSED' if ok else '[FAIL] FAILED'}")
    return ok


def test_schema():
    print("\n" + "=" * 80)
    print("TEST 2: GET /api/schema")
    print("=" * 80)

    r = _get("/api/schema")
    if r.status_code != 200:
        print(f"Error: {r.status_code} - {r.text}")
    assert r.status_code == 200
    data = r.json()

    print(f"  Tables returned: {len(data)}")
    for t in data:
        print(f"    {t['table_name']:10s} — {t['column_count']} columns")

    ok = len(data) >= 9 and all("table_name" in t and "column_count" in t for t in data)
    print(f"\n  {'[OK] PASSED' if ok else '[FAIL] FAILED'}")
    return ok


def test_query_cpu():
    print("\n" + "=" * 80)
    print("TEST 3: POST /api/query — CPU aggregation")
    print("=" * 80)

    r = _post("/api/query", {"query": "show total cpu busy time per cpu"})
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()

    print(f"  SQL:        {data.get('sql', '')[:80]}...")
    print(f"  Columns:    {data.get('columns')}")
    print(f"  Row count:  {data.get('row_count')}")
    print(f"  Chart type: {data.get('chart_type')}")
    print(f"  Cache hit:  {data.get('cache_hit')}")
    print(f"  Exec time:  {data.get('execution_time_ms')}ms")

    ok = (
        "sql" in data and
        "columns" in data and
        "rows" in data and
        data.get("row_count", 0) > 0 and
        data.get("chart_type") == "bar"
    )
    print(f"\n  {'[OK] PASSED' if ok else '[FAIL] FAILED'}")
    return ok


def test_cache_hit():
    print("\n" + "=" * 80)
    print("TEST 4: POST /api/query — Cache hit on second identical query")
    print("=" * 80)

    query = {"query": "show total cpu busy time per cpu"}

    # First call (already done in test 3, but run again to be sure)
    r1 = _post("/api/query", query)
    assert r1.status_code == 200
    d1 = r1.json()

    # Second call — should be a cache hit
    r2 = _post("/api/query", query)
    assert r2.status_code == 200
    d2 = r2.json()

    print(f"  First call  — cache_hit: {d1.get('cache_hit')}, time: {d1.get('execution_time_ms')}ms")
    print(f"  Second call — cache_hit: {d2.get('cache_hit')}, time: {d2.get('execution_time_ms')}ms")

    ok = d2.get("cache_hit") is True
    print(f"\n  {'[OK] PASSED' if ok else '[FAIL] FAILED'}")
    return ok


def test_harmful_query():
    print("\n" + "=" * 80)
    print("TEST 5: POST /api/query — Harmful SQL directly via export (validator blocks it)")
    print("=" * 80)

    # Test that the validator blocks actual harmful SQL via the export endpoint
    r = _post("/api/export", {
        "sql": "DROP TABLE macht413.cpu",
        "format": "csv",
        "query_text": "test"
    })
    print(f"  DROP TABLE -> Status: {r.status_code}")
    drop_blocked = r.status_code == 400

    r2 = _post("/api/export", {
        "sql": "DELETE FROM macht413.cpu",
        "format": "csv",
        "query_text": "test"
    })
    print(f"  DELETE     -> Status: {r2.status_code}")
    delete_blocked = r2.status_code == 400

    r3 = _post("/api/export", {
        "sql": "SELECT * FROM macht413.cpu; DROP TABLE macht413.cpu;",
        "format": "csv",
        "query_text": "test"
    })
    print(f"  Injection  -> Status: {r3.status_code}")
    injection_blocked = r3.status_code == 400

    ok = drop_blocked and delete_blocked and injection_blocked
    print(f"\n  {'[OK] PASSED' if ok else '[FAIL] FAILED'} — validator blocks all harmful SQL")
    return ok


def test_empty_query():
    print("\n" + "=" * 80)
    print("TEST 6: POST /api/query — Empty query rejected")
    print("=" * 80)

    r = _post("/api/query", {"query": ""})
    print(f"  Status: {r.status_code}")

    ok = r.status_code == 400
    print(f"\n  {'[OK] PASSED' if ok else '[FAIL] FAILED'}")
    return ok


def test_export_csv():
    print("\n" + "=" * 80)
    print("TEST 7: POST /api/export — CSV download")
    print("=" * 80)

    sql = "SELECT cpu_num, cpu_busy_time FROM macht413.cpu LIMIT 10"
    r = _post("/api/export", {"sql": sql, "format": "csv", "query_text": "test"})

    print(f"  Status:       {r.status_code}")
    print(f"  Content-Type: {r.headers.get('content-type')}")
    print(f"  Disposition:  {r.headers.get('content-disposition')}")
    print(f"  Size:         {len(r.content)} bytes")

    ok = (
        r.status_code == 200 and
        "text/csv" in r.headers.get("content-type", "") and
        "querycraft_report.csv" in r.headers.get("content-disposition", "") and
        len(r.content) > 0
    )
    print(f"\n  {'[OK] PASSED' if ok else '[FAIL] FAILED'}")
    return ok


def test_export_excel():
    print("\n" + "=" * 80)
    print("TEST 8: POST /api/export — Excel download")
    print("=" * 80)

    sql = "SELECT cpu_num, cpu_busy_time FROM macht413.cpu LIMIT 10"
    r = _post("/api/export", {"sql": sql, "format": "excel", "query_text": "test"})

    print(f"  Status:       {r.status_code}")
    print(f"  Content-Type: {r.headers.get('content-type')}")
    print(f"  Size:         {len(r.content)} bytes")
    print(f"  Magic bytes:  {r.content[:4]}")

    ok = (
        r.status_code == 200 and
        r.content[:4] == b"PK\x03\x04" and
        "querycraft_report.xlsx" in r.headers.get("content-disposition", "")
    )
    print(f"\n  {'[OK] PASSED' if ok else '[FAIL] FAILED'}")
    return ok


def test_export_pdf():
    print("\n" + "=" * 80)
    print("TEST 9: POST /api/export — PDF download")
    print("=" * 80)

    sql = "SELECT cpu_num, cpu_busy_time FROM macht413.cpu LIMIT 10"
    r = _post("/api/export", {"sql": sql, "format": "pdf", "query_text": "test"})

    print(f"  Status:       {r.status_code}")
    print(f"  Content-Type: {r.headers.get('content-type')}")
    print(f"  Size:         {len(r.content)} bytes")
    print(f"  Magic bytes:  {r.content[:4]}")

    ok = (
        r.status_code == 200 and
        r.content[:4] == b"%PDF" and
        "querycraft_report.pdf" in r.headers.get("content-disposition", "")
    )
    print(f"\n  {'[OK] PASSED' if ok else '[FAIL] FAILED'}")
    return ok


def test_history():
    print("\n" + "=" * 80)
    print("TEST 10: GET /api/history")
    print("=" * 80)

    r = _get("/api/history")
    assert r.status_code == 200
    data = r.json()

    print(f"  Entries: {len(data)}")
    if data:
        e = data[0]
        print(f"  Latest:  [{e.get('timestamp','')[:19]}] {e.get('original_input','')[:50]}")

    ok = isinstance(data, list) and len(data) > 0
    print(f"\n  {'[OK] PASSED' if ok else '[FAIL] FAILED'}")
    return ok


def test_explain():
    print("\n" + "=" * 80)
    print("TEST 11: POST /api/explain")
    print("=" * 80)

    body = {
        "sql": "SELECT cpu_num, cpu_busy_time FROM macht413.cpu LIMIT 10",
        "query_text": "show cpu busy time per cpu",
        "columns": ["cpu_num", "cpu_busy_time"],
        "rows": [
            {"cpu_num": 0, "cpu_busy_time": 1000},
            {"cpu_num": 1, "cpu_busy_time": 1200},
            {"cpu_num": 2, "cpu_busy_time": 900}
        ]
    }
    r = _post("/api/explain", body)
    print(f"  Status: {r.status_code}")

    ok = False
    if r.status_code == 200:
        data = r.json()
        print(f"  Explanation key exists: {'explanation' in data}")
        if 'explanation' in data:
            print(f"  Explanation snippet: {data['explanation'][:80]}...")
            ok = len(data['explanation']) > 0
    else:
        print(f"  Error message: {r.text}")

    print(f"\n  {'[OK] PASSED' if ok else '[FAIL] FAILED'}")
    return ok


def run_all_tests():
    print("\n" + "=" * 80)
    print("PHASE 8 — API ENDPOINT TESTS")
    print("=" * 80)

    # Check server is reachable
    try:
        requests.get(f"{BASE}/api/health", timeout=5)
    except Exception:
        print("\n[FAIL] Server not reachable at http://localhost:8000")
        print("  Start it with: uvicorn main:app --reload --port 8000")
        return False

    results = []
    results.append(("GET /api/health",          test_health()))
    results.append(("GET /api/schema",           test_schema()))
    results.append(("POST /api/query (cpu)",     test_query_cpu()))
    results.append(("POST /api/query (cache)",   test_cache_hit()))
    results.append(("POST /api/query (harmful)", test_harmful_query()))
    results.append(("POST /api/query (empty)",   test_empty_query()))
    results.append(("POST /api/export (csv)",    test_export_csv()))
    results.append(("POST /api/export (excel)",  test_export_excel()))
    results.append(("POST /api/export (pdf)",    test_export_pdf()))
    results.append(("GET /api/history",          test_history()))
    results.append(("POST /api/explain",          test_explain()))

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    for name, ok in results:
        print(f"  {name:35s}: {'[OK] PASSED' if ok else '[FAIL] FAILED'}")

    all_passed = all(r[1] for r in results)
    print("\n" + "=" * 80)
    print("[OK] ALL API TESTS PASSED" if all_passed else "[FAIL] SOME TESTS FAILED")
    print("=" * 80)
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
