"""
Run all tests for Phases 2–7
"""
import sys
import os
import warnings
warnings.filterwarnings("ignore")   # suppress WeasyPrint/HuggingFace noise

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tests.test_schema_loader import run_all_tests as test_schema_loader
from tests.test_normalizer import run_all_tests as test_normalizer
from tests.test_validator import run_all_tests as test_validator
from tests.test_executor import run_all_tests as test_executor
from tests.test_cache import run_all_tests as test_cache
from tests.test_report_generator import run_all_tests as test_report_generator

def test_prompt_builder():
    """Run prompt builder tests."""
    try:
        from tests.test_prompt_builder import test_full_pipeline, test_with_few_shots, test_retry_prompt
        
        test_full_pipeline()
        test_with_few_shots()
        test_retry_prompt()
        
        return True
    except Exception as e:
        print(f"[FAIL] Prompt Builder tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "=" * 80)
    print(" " * 8 + "PHASES 2, 3, 4, 5, 6 & 7 - COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    # Wait for shared embedding model thread to load
    print("Waiting for embedding model to load...")
    import pipeline.embeddings as embeddings
    embeddings.start_loading()
    embeddings.wait(timeout=60)
    print("Embedding model ready. Running tests...\n")

    results = []
    
    print("\n" + "▶" * 40)
    print("Running Schema Loader Tests...")
    print("▶" * 40)
    results.append(("Schema Loader", test_schema_loader()))
    
    print("\n" + "▶" * 40)
    print("Running Query Normalizer Tests...")
    print("▶" * 40)
    results.append(("Query Normalizer", test_normalizer()))
    
    print("\n" + "▶" * 40)
    print("Running Prompt Builder Tests...")
    print("▶" * 40)
    results.append(("Prompt Builder", test_prompt_builder()))
    
    print("\n" + "▶" * 40)
    print("Running SQL Validator Tests...")
    print("▶" * 40)
    results.append(("SQL Validator", test_validator()))
    
    print("\n" + "▶" * 40)
    print("Running Query Executor Tests...")
    print("▶" * 40)
    results.append(("Query Executor", test_executor()))
    
    print("\n" + "▶" * 40)
    print("Running Semantic Cache Tests...")
    print("▶" * 40)
    results.append(("Semantic Cache", test_cache()))

    print("\n" + "▶" * 40)
    print("Running Report Generator Tests...")
    print("▶" * 40)
    results.append(("Report Generator", test_report_generator()))

    print("\n" + "=" * 80)
    print(" " * 30 + "FINAL SUMMARY")
    print("=" * 80)

    for component, passed in results:
        status = "[OK] PASSED" if passed else "[FAIL] FAILED"
        print(f"{component:30s}: {status}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 80)
    if all_passed:
        print(" " * 8 + "[OK] ALL PHASES 2–7 TESTS PASSED")
        print(" " * 20 + "Ready to proceed to Phase 8!")
    else:
        print(" " * 25 + "[FAIL] SOME TESTS FAILED")
        print(" " * 20 + "Please fix issues before proceeding")
    print("=" * 80 + "\n")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
