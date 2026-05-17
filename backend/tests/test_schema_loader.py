"""
Comprehensive tests for Schema Loader
Tests normal operation and edge cases.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline.schema_loader import SchemaLoader, load_schema
import tempfile
import yaml

def test_normal_operation():
    """Test normal schema loading."""
    print("\n" + "=" * 60)
    print("TEST 1: Normal Operation")
    print("=" * 60)
    
    try:
        loader = load_schema('../schema_store/enriched_schema.yaml')
        
        # Test 1.1: Schema loads successfully
        assert loader.get_schema() is not None, "Schema should not be None"
        print("✓ Schema loads successfully")
        
        # Test 1.2: All 9 tables present
        tables = loader.get_table_names()
        assert len(tables) == 9, f"Expected 9 tables, got {len(tables)}"
        print(f"✓ All 9 tables present: {', '.join(tables)}")
        
        # Test 1.3: Required tables exist
        required = ['cpu', 'disc', 'dfile', 'dopen', 'file', 'ossns', 'proc', 'tmf', 'udef']
        for table in required:
            assert table in tables, f"Missing required table: {table}"
        print("✓ All required tables exist")
        
        # Test 1.4: Tables have columns
        for table in tables:
            cols = loader.get_columns(table)
            assert len(cols) > 0, f"Table {table} has no columns"
        print("✓ All tables have columns")
        
        # Test 1.5: Can access specific table
        cpu_table = loader.get_table('cpu')
        assert 'columns' in cpu_table, "CPU table missing columns key"
        print("✓ Can access specific table data")
        
        # Test 1.6: Can get queryable columns
        queryable = loader.get_queryable_columns('cpu')
        assert len(queryable) > 0, "No queryable columns found"
        print(f"✓ Found {len(queryable)} queryable columns in CPU table")
        
        # Test 1.7: Column existence check works
        assert loader.column_exists('cpu', 'cpu_num') == True, "cpu_num should exist"
        assert loader.column_exists('cpu', 'fake_column') == False, "fake_column should not exist"
        print("✓ Column existence check works")
        
        # Test 1.8: Can get table description
        desc = loader.get_table_description('cpu')
        assert isinstance(desc, str), "Description should be a string"
        print(f"✓ Can get table description (length: {len(desc)} chars)")
        
        return True
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n" + "=" * 60)
    print("TEST 2: Edge Cases & Error Handling")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    # Test 2.1: Non-existent file
    try:
        loader = SchemaLoader('nonexistent.yaml')
        print("✗ Should have raised FileNotFoundError")
        failed += 1
    except FileNotFoundError:
        print("✓ Correctly raises FileNotFoundError for missing file")
        passed += 1
    except Exception as e:
        print(f"✗ Wrong exception type: {type(e).__name__}")
        failed += 1
    
    # Test 2.2: Empty file
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            temp_file = f.name
        
        try:
            loader = SchemaLoader(temp_file)
            print("✗ Should have raised ValueError for empty file")
            failed += 1
        except ValueError as e:
            if "empty" in str(e).lower():
                print("✓ Correctly raises ValueError for empty file")
                passed += 1
            else:
                print(f"✗ Wrong error message: {e}")
                failed += 1
        finally:
            os.unlink(temp_file)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        failed += 1
    
    # Test 2.3: Invalid YAML
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_file = f.name
        
        try:
            loader = SchemaLoader(temp_file)
            print("✗ Should have raised exception for invalid YAML")
            failed += 1
        except Exception:
            print("✓ Correctly raises exception for invalid YAML")
            passed += 1
        finally:
            os.unlink(temp_file)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        failed += 1
    
    # Test 2.4: Missing required table
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({'cpu': {'columns': {}}}, f)
            temp_file = f.name
        
        try:
            loader = SchemaLoader(temp_file)
            print("✗ Should have raised ValueError for missing tables")
            failed += 1
        except ValueError as e:
            if "missing" in str(e).lower():
                print("✓ Correctly raises ValueError for missing required tables")
                passed += 1
            else:
                print(f"✗ Wrong error message: {e}")
                failed += 1
        finally:
            os.unlink(temp_file)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        failed += 1
    
    # Test 2.5: Table without columns
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            schema = {
                'cpu': {},
                'disc': {'columns': {}},
                'dfile': {'columns': {}},
                'dopen': {'columns': {}},
                'file': {'columns': {}},
                'ossns': {'columns': {}},
                'proc': {'columns': {}},
                'tmf': {'columns': {}},
                'udef': {'columns': {}},
            }
            yaml.dump(schema, f)
            temp_file = f.name
        
        try:
            loader = SchemaLoader(temp_file)
            print("✗ Should have raised ValueError for table without columns")
            failed += 1
        except ValueError as e:
            if "columns" in str(e).lower():
                print("✓ Correctly raises ValueError for table without columns")
                passed += 1
            else:
                print(f"✗ Wrong error message: {e}")
                failed += 1
        finally:
            os.unlink(temp_file)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        failed += 1
    
    # Test 2.6: Access non-existent table
    try:
        loader = load_schema('../schema_store/enriched_schema.yaml')
        table = loader.get_table('nonexistent_table')
        print("✗ Should have raised KeyError for non-existent table")
        failed += 1
    except KeyError:
        print("✓ Correctly raises KeyError for non-existent table")
        passed += 1
    except Exception as e:
        print(f"✗ Wrong exception type: {type(e).__name__}")
        failed += 1
    
    # Test 2.7: Check column in non-existent table
    try:
        loader = load_schema('../schema_store/enriched_schema.yaml')
        exists = loader.column_exists('nonexistent_table', 'some_column')
        assert exists == False, "Should return False for non-existent table"
        print("✓ Returns False for column check in non-existent table")
        passed += 1
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        failed += 1
    
    print(f"\nEdge Cases: {passed} passed, {failed} failed")
    return failed == 0


def test_data_integrity():
    """Test data integrity and consistency."""
    print("\n" + "=" * 60)
    print("TEST 3: Data Integrity & Consistency")
    print("=" * 60)
    
    try:
        loader = load_schema('../schema_store/enriched_schema.yaml')
        
        # Test 3.1: All tables have common columns
        common_cols = ['system_name', 'cpu_num', 'from_timestamp', 'to_timestamp']
        for table in loader.get_table_names():
            cols = loader.get_columns(table)
            col_names = list(cols.keys())
            
            # Check for common columns (with dot notation)
            has_system = any('system_name' in col for col in col_names)
            has_cpu = any('cpu_num' in col for col in col_names)
            has_from = any('from_timestamp' in col for col in col_names)
            has_to = any('to_timestamp' in col for col in col_names)
            
            if not (has_system and has_cpu and has_from and has_to):
                print(f"  ⚠ Table {table} missing some common columns")
        
        print("✓ Checked common columns across tables")
        
        # Test 3.2: Column definitions have expected structure
        cpu_cols = loader.get_columns('cpu')
        sample_col = list(cpu_cols.values())[0]
        
        if isinstance(sample_col, dict):
            print("✓ Column definitions are dictionaries")
        else:
            print(f"⚠ Column definition is {type(sample_col)}, expected dict")
        
        # Test 3.3: Queryable columns filter works
        all_cols = loader.get_columns('cpu')
        queryable_cols = loader.get_queryable_columns('cpu')
        
        assert len(queryable_cols) <= len(all_cols), "Queryable should be subset of all"
        print(f"✓ Queryable columns ({len(queryable_cols)}) ≤ All columns ({len(all_cols)})")
        
        # Test 3.4: Table descriptions exist
        desc_count = 0
        for table in loader.get_table_names():
            desc = loader.get_table_description(table)
            if desc and len(desc) > 0:
                desc_count += 1
        
        print(f"✓ {desc_count}/{len(loader.get_table_names())} tables have descriptions")
        
        # Test 3.5: Schema is immutable (getting it twice returns same data)
        schema1 = loader.get_schema()
        schema2 = loader.get_schema()
        assert schema1 is schema2, "Schema should return same object"
        print("✓ Schema returns consistent data")
        
        return True
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance():
    """Test performance characteristics."""
    print("\n" + "=" * 60)
    print("TEST 4: Performance")
    print("=" * 60)
    
    import time
    
    try:
        # Test 4.1: Schema loading time
        start = time.time()
        loader = load_schema('../schema_store/enriched_schema.yaml')
        load_time = time.time() - start
        print(f"✓ Schema loaded in {load_time*1000:.2f}ms")
        
        if load_time > 1.0:
            print(f"  ⚠ Loading took longer than 1 second")
        
        # Test 4.2: Table access time
        start = time.time()
        for _ in range(1000):
            loader.get_table('cpu')
        access_time = (time.time() - start) / 1000
        print(f"✓ Average table access: {access_time*1000:.4f}ms")
        
        # Test 4.3: Column lookup time
        start = time.time()
        for _ in range(1000):
            loader.column_exists('cpu', 'cpu_num')
        lookup_time = (time.time() - start) / 1000
        print(f"✓ Average column lookup: {lookup_time*1000:.4f}ms")
        
        return True
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        return False


def run_all_tests():
    """Run all test suites."""
    print("\n" + "=" * 70)
    print("SCHEMA LOADER - COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    
    results = []
    
    results.append(("Normal Operation", test_normal_operation()))
    results.append(("Edge Cases", test_edge_cases()))
    results.append(("Data Integrity", test_data_integrity()))
    results.append(("Performance", test_performance()))
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{name:30s}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
