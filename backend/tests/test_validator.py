"""
Comprehensive tests for SQL Validator
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline.schema_loader import load_schema
from pipeline.validator import SQLValidator


def test_valid_queries():
    """Test valid SQL queries."""
    print("\n" + "=" * 80)
    print("TEST 1: Valid SQL Queries")
    print("=" * 80)
    
    loader = load_schema('../schema_store/enriched_schema.yaml')
    schema = loader.get_schema()
    validator = SQLValidator(schema)
    
    test_cases = [
        "SELECT * FROM macht413.cpu LIMIT 100",
        "SELECT cpu_num, cpu_busy_time FROM macht413.cpu WHERE cpu_num = 0",
        "SELECT AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num",
        "SELECT c.cpu_num, p.process_name FROM macht413.cpu c JOIN macht413.proc p ON c.cpu_num = p.cpu_num",
        "SELECT COUNT(*) FROM macht413.disc",
        "SELECT DISTINCT system_name FROM macht413.file",
    ]
    
    passed = 0
    for i, sql in enumerate(test_cases, 1):
        result = validator.validate(sql)
        if result.valid:
            print(f"[OK] Test {i}: Valid")
            passed += 1
        else:
            print(f"[FAIL] Test {i}: {result.error}")
    
    print(f"\nValid Queries: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_schema_prefix():
    """Test automatic schema prefix addition."""
    print("\n" + "=" * 80)
    print("TEST 2: Schema Prefix Auto-Addition")
    print("=" * 80)
    
    loader = load_schema('../schema_store/enriched_schema.yaml')
    schema = loader.get_schema()
    validator = SQLValidator(schema)
    
    test_cases = [
        ("SELECT * FROM cpu", "macht413.cpu"),
        ("SELECT * FROM proc", "macht413.proc"),
        ("SELECT * FROM disc", "macht413.disc"),
    ]
    
    passed = 0
    for i, (sql, expected_table) in enumerate(test_cases, 1):
        result = validator.validate(sql)
        if result.valid and expected_table in result.sanitized_sql:
            print(f"[OK] Test {i}: Schema prefix added correctly")
            passed += 1
        else:
            print(f"[FAIL] Test {i}: Failed to add schema prefix")
    
    print(f"\nSchema Prefix: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_forbidden_operations():
    """Test rejection of forbidden SQL operations."""
    print("\n" + "=" * 80)
    print("TEST 3: Forbidden Operations")
    print("=" * 80)
    
    loader = load_schema('../schema_store/enriched_schema.yaml')
    schema = loader.get_schema()
    validator = SQLValidator(schema)
    
    test_cases = [
        ("DELETE FROM macht413.cpu", "DELETE"),
        ("UPDATE macht413.cpu SET cpu_num = 1", "UPDATE"),
        ("INSERT INTO macht413.cpu VALUES (1, 2, 3)", "INSERT"),
        ("DROP TABLE macht413.cpu", "DROP"),
        ("ALTER TABLE macht413.cpu ADD COLUMN test INT", "ALTER"),
        ("CREATE TABLE test (id INT)", "CREATE"),
        ("TRUNCATE TABLE macht413.cpu", "TRUNCATE"),
    ]
    
    passed = 0
    for i, (sql, keyword) in enumerate(test_cases, 1):
        result = validator.validate(sql)
        if not result.valid and keyword.lower() in result.error.lower():
            print(f"[OK] Test {i}: {keyword} correctly rejected")
            passed += 1
        else:
            print(f"[FAIL] Test {i}: {keyword} not properly rejected")
    
    print(f"\nForbidden Operations: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_injection_patterns():
    """Test SQL injection pattern detection."""
    print("\n" + "=" * 80)
    print("TEST 4: SQL Injection Patterns")
    print("=" * 80)
    
    loader = load_schema('../schema_store/enriched_schema.yaml')
    schema = loader.get_schema()
    validator = SQLValidator(schema)
    
    test_cases = [
        "SELECT * FROM macht413.cpu; DROP TABLE macht413.cpu;",
        "SELECT * FROM macht413.cpu WHERE 1=1; DELETE FROM macht413.cpu;",
    ]
    
    passed = 0
    for i, sql in enumerate(test_cases, 1):
        result = validator.validate(sql)
        if not result.valid:
            print(f"[OK] Test {i}: Injection pattern detected")
            passed += 1
        else:
            print(f"[FAIL] Test {i}: Injection pattern NOT detected")
    
    print(f"\nInjection Patterns: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_table_validation():
    """Test table existence validation."""
    print("\n" + "=" * 80)
    print("TEST 5: Table Existence Validation")
    print("=" * 80)
    
    loader = load_schema('../schema_store/enriched_schema.yaml')
    schema = loader.get_schema()
    validator = SQLValidator(schema)
    
    # Valid tables
    valid_tables = ["cpu", "disc", "proc", "file", "tmf"]
    passed = 0
    
    for table in valid_tables:
        sql = f"SELECT * FROM macht413.{table} LIMIT 10"
        result = validator.validate(sql)
        if result.valid:
            print(f"[OK] Valid table '{table}' accepted")
            passed += 1
        else:
            print(f"[FAIL] Valid table '{table}' rejected: {result.error}")
    
    # Invalid tables
    invalid_tables = ["fake_table", "nonexistent", "test"]
    
    for table in invalid_tables:
        sql = f"SELECT * FROM macht413.{table} LIMIT 10"
        result = validator.validate(sql)
        if not result.valid and "does not exist" in result.error:
            print(f"[OK] Invalid table '{table}' rejected")
            passed += 1
        else:
            print(f"[FAIL] Invalid table '{table}' not properly rejected")
    
    total = len(valid_tables) + len(invalid_tables)
    print(f"\nTable Validation: {passed}/{total} passed")
    return passed == total


def test_column_validation():
    """Test column existence validation."""
    print("\n" + "=" * 80)
    print("TEST 6: Column Existence Validation")
    print("=" * 80)
    
    loader = load_schema('../schema_store/enriched_schema.yaml')
    schema = loader.get_schema()
    validator = SQLValidator(schema)
    
    # Valid columns
    valid_cases = [
        "SELECT cpu_num FROM macht413.cpu",
        "SELECT cpu_busy_time FROM macht413.cpu",
        "SELECT system_name FROM macht413.cpu",
    ]
    
    passed = 0
    for i, sql in enumerate(valid_cases, 1):
        result = validator.validate(sql)
        if result.valid:
            print(f"[OK] Test {i}: Valid column accepted")
            passed += 1
        else:
            print(f"[FAIL] Test {i}: Valid column rejected: {result.error}")
    
    # Invalid columns
    invalid_cases = [
        "SELECT fake_column FROM macht413.cpu",
        "SELECT nonexistent_field FROM macht413.disc",
    ]
    
    for i, sql in enumerate(invalid_cases, len(valid_cases) + 1):
        result = validator.validate(sql)
        if not result.valid and "does not exist" in result.error:
            print(f"[OK] Test {i}: Invalid column rejected")
            passed += 1
        else:
            print(f"[FAIL] Test {i}: Invalid column not properly rejected")
    
    total = len(valid_cases) + len(invalid_cases)
    print(f"\nColumn Validation: {passed}/{total} passed")
    return passed == total


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n" + "=" * 80)
    print("TEST 7: Edge Cases")
    print("=" * 80)
    
    loader = load_schema('../schema_store/enriched_schema.yaml')
    schema = loader.get_schema()
    validator = SQLValidator(schema)
    
    test_cases = [
        ("", "empty string"),
        ("   ", "whitespace only"),
        ("NOT A VALID SQL", "invalid syntax"),
    ]
    
    passed = 0
    for i, (sql, description) in enumerate(test_cases, 1):
        result = validator.validate(sql)
        if not result.valid:
            print(f"[OK] Test {i}: {description} rejected")
            passed += 1
        else:
            print(f"[FAIL] Test {i}: {description} not rejected")
    
    print(f"\nEdge Cases: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_joins_and_aliases():
    """Test AST-based tracking of table aliases, Joins, subqueries and CTEs."""
    print("\n" + "=" * 80)
    print("TEST 8: Joins, Subqueries and CTEs Validation")
    print("=" * 80)
    
    loader = load_schema('../schema_store/enriched_schema.yaml')
    schema = loader.get_schema()
    validator = SQLValidator(schema)
    
    # These should be valid
    valid_cases = [
        "SELECT c.cpu_num, p.process_name FROM macht413.cpu c JOIN macht413.proc p ON c.cpu_num = p.cpu_num",
        "SELECT cpu_num, process_name FROM macht413.cpu JOIN macht413.proc ON macht413.cpu.cpu_num = macht413.proc.cpu_num", # Unqualified but unambiguous
        "WITH cpu_cte AS (SELECT cpu_num, cpu_busy_time FROM macht413.cpu) SELECT cpu_num FROM cpu_cte",
        "SELECT sub.cpu_num FROM (SELECT cpu_num FROM macht413.cpu) sub",
    ]
    
    passed = 0
    for i, sql in enumerate(valid_cases, 1):
        result = validator.validate(sql)
        if result.valid:
            print(f"[OK] Valid case {i} passed")
            passed += 1
        else:
            print(f"[FAIL] Valid case {i} failed: {result.error}")
            
    # These should be invalid (ambiguous or nonexistent columns in joins/subqueries)
    invalid_cases = [
        ("SELECT fake_col FROM macht413.cpu c JOIN macht413.proc p ON c.cpu_num = p.cpu_num", "does not exist"),
        ("SELECT c.process_name FROM macht413.cpu c JOIN macht413.proc p ON c.cpu_num = p.cpu_num", "does not exist"), # process_name is in proc, not cpu
        ("SELECT sub.process_name FROM (SELECT cpu_num FROM macht413.cpu) sub", "does not exist"), # subquery only exports cpu_num
    ]
    
    for i, (sql, expected_error) in enumerate(invalid_cases, len(valid_cases) + 1):
        result = validator.validate(sql)
        if not result.valid and expected_error in result.error:
            print(f"[OK] Invalid case {i} correctly rejected: {result.error}")
            passed += 1
        else:
            print(f"[FAIL] Invalid case {i} not correctly rejected: {result.error if not result.valid else 'passed'}")
            
    total = len(valid_cases) + len(invalid_cases)
    print(f"\nJoins and Aliases: {passed}/{total} passed")
    return passed == total


def test_repeating_columns():
    """Test validation of repeating column groups (e.g. ipu{N}, svnet{N}, c{N})."""
    print("\n" + "=" * 80)
    print("TEST 9: Repeating Column Groups")
    print("=" * 80)
    
    loader = load_schema('../schema_store/enriched_schema.yaml')
    schema = loader.get_schema()
    validator = SQLValidator(schema)
    
    # Valid columns from precomputed expansion
    valid_cases = [
        "SELECT ipu0_ipu_busy_time FROM macht413.cpu",
        "SELECT ipu15_ipu_busy_time FROM macht413.cpu",
        "SELECT c0_hits FROM macht413.disc",
        "SELECT c7_hits FROM macht413.disc",
    ]
    
    passed = 0
    for i, sql in enumerate(valid_cases, 1):
        result = validator.validate(sql)
        if result.valid:
            print(f"[OK] Valid case {i} passed")
            passed += 1
        else:
            print(f"[FAIL] Valid case {i} failed: {result.error}")
            
    # Invalid columns (out of bounds or nonexistent)
    invalid_cases = [
        "SELECT ipu16_ipu_busy_time FROM macht413.cpu", # IPU goes up to 15
        "SELECT c8_hits FROM macht413.disc", # Cache blocks go up to 7
    ]
    
    for i, sql in enumerate(invalid_cases, len(valid_cases) + 1):
        result = validator.validate(sql)
        if not result.valid and "does not exist" in result.error:
            print(f"[OK] Invalid case {i} correctly rejected")
            passed += 1
        else:
            print(f"[FAIL] Invalid case {i} not correctly rejected: {result.error if not result.valid else 'passed'}")
            
    total = len(valid_cases) + len(invalid_cases)
    print(f"\nRepeating Columns: {passed}/{total} passed")
    return passed == total


def test_complexity_limits():
    """Test enforcement of query complexity limits."""
    print("\n" + "=" * 80)
    print("TEST 10: Query Complexity Limits")
    print("=" * 80)
    
    loader = load_schema('../schema_store/enriched_schema.yaml')
    schema = loader.get_schema()
    validator = SQLValidator(schema)
    
    # 1. More than 9 tables
    sql_too_many_tables = (
        "SELECT * FROM macht413.cpu t1 "
        "JOIN macht413.cpu t2 ON t1.cpu_num = t2.cpu_num "
        "JOIN macht413.cpu t3 ON t1.cpu_num = t3.cpu_num "
        "JOIN macht413.cpu t4 ON t1.cpu_num = t4.cpu_num "
        "JOIN macht413.cpu t5 ON t1.cpu_num = t5.cpu_num "
        "JOIN macht413.cpu t6 ON t1.cpu_num = t6.cpu_num "
        "JOIN macht413.cpu t7 ON t1.cpu_num = t7.cpu_num "
        "JOIN macht413.cpu t8 ON t1.cpu_num = t8.cpu_num "
        "JOIN macht413.cpu t9 ON t1.cpu_num = t9.cpu_num "
        "JOIN macht413.cpu t10 ON t1.cpu_num = t10.cpu_num"
    )
    
    # 2. More than 30 columns in SELECT
    columns_list = ", ".join([f"cpu_busy_time AS col{i}" for i in range(35)])
    sql_too_many_columns = f"SELECT {columns_list} FROM macht413.cpu"
    
    # 3. Nesting depth > 3
    sql_too_deep_nesting = (
        "SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT cpu_num FROM macht413.cpu) s4) s3) s2) s1"
    )
    
    test_cases = [
        (sql_too_many_tables, "too many tables"),
        (sql_too_many_columns, "too many columns in SELECT"),
        (sql_too_deep_nesting, "nesting depth > 3"),
    ]
    
    passed = 0
    for i, (sql, description) in enumerate(test_cases, 1):
        result = validator.validate(sql)
        if not result.valid and "limit exceeded" in result.error:
            print(f"[OK] Rejected {description} correctly: {result.error}")
            passed += 1
        else:
            print(f"[FAIL] Failed to reject {description}: {result.error if not result.valid else 'passed'}")
            
    # Subquery nesting level 3 should pass
    sql_nested_3 = (
        "SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT cpu_num FROM macht413.cpu) s3) s2) s1"
    )
    result_nested_3 = validator.validate(sql_nested_3)
    if result_nested_3.valid:
        print("[OK] Nested subquery at level 3 allowed")
        passed += 1
    else:
        print(f"[FAIL] Level 3 subquery rejected: {result_nested_3.error}")
        
    total = len(test_cases) + 1
    print(f"\nComplexity Limits: {passed}/{total} passed")
    return passed == total


def run_all_tests():
    """Run all validator tests."""
    print("\n" + "=" * 80)
    print("SQL VALIDATOR - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    
    results = []
    
    results.append(("Valid Queries", test_valid_queries()))
    results.append(("Schema Prefix", test_schema_prefix()))
    results.append(("Forbidden Operations", test_forbidden_operations()))
    results.append(("Injection Patterns", test_injection_patterns()))
    results.append(("Table Validation", test_table_validation()))
    results.append(("Column Validation", test_column_validation()))
    results.append(("Edge Cases", test_edge_cases()))
    results.append(("Joins and Aliases", test_joins_and_aliases()))
    results.append(("Repeating Columns", test_repeating_columns()))
    results.append(("Complexity Limits", test_complexity_limits()))
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for name, passed in results:
        status = "[OK] PASSED" if passed else "[FAIL] FAILED"
        print(f"{name:30s}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 80)
    if all_passed:
        print("[OK] ALL VALIDATOR TESTS PASSED")
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

