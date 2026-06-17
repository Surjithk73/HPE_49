"""
Comprehensive tests for Query Executor
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline.executor import QueryExecutor, ExecutionError, detect_chart_type


def test_basic_execution():
    """Test basic query execution."""
    print("\n" + "=" * 80)
    print("TEST 1: Basic Query Execution")
    print("=" * 80)
    
    executor = QueryExecutor()
    
    test_cases = [
        ("SELECT COUNT(*) FROM macht413.cpu", "count query"),
        ("SELECT cpu_num FROM macht413.cpu LIMIT 5", "simple select"),
        ("SELECT AVG(cpu_busy_time) FROM macht413.cpu", "aggregation"),
    ]
    
    passed = 0
    for sql, description in test_cases:
        try:
            result = executor.execute(sql)
            if result.row_count >= 0 and result.execution_time_ms > 0:
                print(f"[OK] {description}: {result.row_count} rows in {result.execution_time_ms}ms")
                passed += 1
            else:
                print(f"[FAIL] {description}: Invalid result")
        except Exception as e:
            print(f"[FAIL] {description}: {e}")
    
    print(f"\nBasic Execution: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_limit_enforcement():
    """Test that LIMIT is enforced."""
    print("\n" + "=" * 80)
    print("TEST 2: LIMIT Enforcement")
    print("=" * 80)
    
    executor = QueryExecutor()
    
    # Query without LIMIT should have it added
    sql_without_limit = "SELECT * FROM macht413.cpu"
    result = executor.execute(sql_without_limit)
    
    if result.row_count <= 10000:
        print(f"[OK] LIMIT enforced: {result.row_count} rows (max 10000)")
        return True
    else:
        print(f"[FAIL] LIMIT not enforced: {result.row_count} rows")
        return False


def test_timeout_handling():
    """Test timeout configuration."""
    print("\n" + "=" * 80)
    print("TEST 3: Timeout Configuration")
    print("=" * 80)
    
    executor = QueryExecutor()
    
    if executor.timeout == 120:
        print(f"[OK] Timeout configured: {executor.timeout}s")
        return True
    else:
        print(f"[FAIL] Timeout incorrect: {executor.timeout}s")
        return False


def test_read_only_enforcement():
    """Test that only read-only user is allowed."""
    print("\n" + "=" * 80)
    print("TEST 4: Read-Only User Enforcement")
    print("=" * 80)
    
    try:
        # Try to create executor with postgres user
        executor = QueryExecutor(user="postgres")
        print("[FAIL] Should have rejected postgres user")
        return False
    except ExecutionError as e:
        if "read-only" in str(e).lower():
            print(f"[OK] Correctly rejected non-read-only user")
            return True
        else:
            print(f"[FAIL] Wrong error: {e}")
            return False


def test_result_format():
    """Test result format."""
    print("\n" + "=" * 80)
    print("TEST 5: Result Format")
    print("=" * 80)
    
    executor = QueryExecutor()
    result = executor.execute("SELECT cpu_num, cpu_busy_time FROM macht413.cpu LIMIT 1")
    
    checks = []
    
    # Check columns
    if isinstance(result.columns, list) and len(result.columns) == 2:
        print(f"[OK] Columns: {result.columns}")
        checks.append(True)
    else:
        print(f"[FAIL] Columns invalid: {result.columns}")
        checks.append(False)
    
    # Check rows
    if isinstance(result.rows, list) and len(result.rows) == 1:
        print(f"[OK] Rows: {len(result.rows)} row")
        checks.append(True)
    else:
        print(f"[FAIL] Rows invalid: {result.rows}")
        checks.append(False)
    
    # Check row format
    if isinstance(result.rows[0], dict):
        print(f"[OK] Row format: dict with keys {list(result.rows[0].keys())}")
        checks.append(True)
    else:
        print(f"[FAIL] Row format invalid")
        checks.append(False)
    
    # Check metadata
    if result.row_count == 1 and result.execution_time_ms > 0:
        print(f"[OK] Metadata: row_count={result.row_count}, time={result.execution_time_ms}ms")
        checks.append(True)
    else:
        print(f"[FAIL] Metadata invalid")
        checks.append(False)
    
    passed = sum(checks)
    print(f"\nResult Format: {passed}/{len(checks)} checks passed")
    return all(checks)


def test_chart_type_detection():
    """Test chart type detection."""
    print("\n" + "=" * 80)
    print("TEST 6: Chart Type Detection")
    print("=" * 80)
    
    test_cases = [
        (["cpu_num", "avg_busy_time"], 
         [{"cpu_num": 0, "avg_busy_time": 100}, {"cpu_num": 1, "avg_busy_time": 200}], "bar"),
        (["from_timestamp", "cpu_busy_time"], 
         [{"from_timestamp": "2023-03-16T19:36:04", "cpu_busy_time": 100}, {"from_timestamp": "2023-03-16T19:36:09", "cpu_busy_time": 200}], "line"),
        (["to_timestamp", "value"], 
         [{"to_timestamp": "2023-03-16T19:36:04", "value": 100}, {"to_timestamp": "2023-03-16T19:36:09", "value": 200}], "line"),
        (["system_name", "total"], 
         [{"system_name": "A", "total": 10}, {"system_name": "B", "total": 20}], "bar"),
        (["device_name", "reads"], 
         [{"device_name": "A", "reads": 10}, {"device_name": "B", "reads": 20}], "bar"),
        (["process_name", "cpu_time"], 
         [{"process_name": "A", "cpu_time": 10}, {"process_name": "B", "cpu_time": 20}], "bar"),
        (["count"], 
         [{"count": 1}], "table"),
        (["sum", "avg"], 
         [{"sum": 100, "avg": 50}], "table"),
    ]
    
    passed = 0
    for columns, test_rows, expected in test_cases:
        result = detect_chart_type(columns, test_rows)
        if result == expected:
            print(f"[OK] {columns} -> {result}")
            passed += 1
        else:
            print(f"[FAIL] {columns} -> {result} (expected {expected})")
    
    print(f"\nChart Type Detection: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_error_handling():
    """Test error handling."""
    print("\n" + "=" * 80)
    print("TEST 7: Error Handling")
    print("=" * 80)
    
    executor = QueryExecutor()
    
    # Test invalid SQL
    try:
        executor.execute("SELECT * FROM macht413.nonexistent_table")
        print("[FAIL] Should have raised error for invalid table")
        return False
    except ExecutionError as e:
        print(f"[OK] Correctly raised error for invalid table")
        return True


def test_configurable_allowed_users():
    """Test dynamic allowed users validation."""
    print("\n" + "=" * 80)
    print("TEST 8: Configurable Allowed Users")
    print("=" * 80)
    
    passed = 0
    # 1. Matching user should succeed and create pool
    try:
        executor = QueryExecutor(user="querycraft_user", allowed_users=["querycraft_user"])
        print("[OK] Allowed user querycraft_user accepted")
        passed += 1
    except ExecutionError as e:
        print(f"[FAIL] Failed to allow querycraft_user: {e}")
        
    # 2. User not in allowed list should be rejected immediately
    try:
        executor = QueryExecutor(user="querycraft_user", allowed_users=["custom_user"])
        print("[FAIL] Should have rejected querycraft_user when not in allowed list")
    except ExecutionError as e:
        if "read-only" in str(e).lower():
            print("[OK] Correctly rejected querycraft_user (not in allowed list)")
            passed += 1
        else:
            print(f"[FAIL] Unexpected error: {e}")
            
    return passed == 2



def test_query_cost_limits():
    """Test dynamic cost estimation limits."""
    print("\n" + "=" * 80)
    print("TEST 9: Query Cost Limits")
    print("=" * 80)
    
    passed = 0
    # 1. Rejecting high cost query (cost threshold 0.001)
    try:
        executor = QueryExecutor(max_query_cost=0.001)
        executor.execute("SELECT * FROM macht413.cpu LIMIT 10")
        print("[FAIL] High-cost query should have been rejected")
    except ExecutionError as e:
        if "cost" in str(e).lower() and "exceed" in str(e).lower():
            print(f"[OK] High-cost query rejected correctly: {e}")
            passed += 1
        else:
            print(f"[FAIL] Unexpected error for high-cost query: {e}")
            
    # 2. Accepting low-cost query
    try:
        executor = QueryExecutor(max_query_cost=10000.0)
        executor.execute("SELECT cpu_num FROM macht413.cpu LIMIT 1")
        print("[OK] Low-cost query accepted correctly")
        passed += 1
    except ExecutionError as e:
        print(f"[FAIL] Failed to accept low-cost query: {e}")
        
    return passed == 2


def run_all_tests():
    """Run all executor tests."""
    print("\n" + "=" * 80)
    print("QUERY EXECUTOR - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    
    results = []
    
    results.append(("Basic Execution", test_basic_execution()))
    results.append(("LIMIT Enforcement", test_limit_enforcement()))
    results.append(("Timeout Configuration", test_timeout_handling()))
    results.append(("Read-Only Enforcement", test_read_only_enforcement()))
    results.append(("Result Format", test_result_format()))
    results.append(("Chart Type Detection", test_chart_type_detection()))
    results.append(("Error Handling", test_error_handling()))
    results.append(("Configurable Allowed Users", test_configurable_allowed_users()))
    results.append(("Query Cost Limits", test_query_cost_limits()))
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for name, passed in results:
        status = "[OK] PASSED" if passed else "[FAIL] FAILED"
        print(f"{name:30s}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 80)
    if all_passed:
        print("[OK] ALL EXECUTOR TESTS PASSED")
    else:
        print("[FAIL] SOME TESTS FAILED")
    print("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FAIL] Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

