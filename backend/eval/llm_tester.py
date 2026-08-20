"""
Eval harness for QueryCraft NL→SQL pipeline.

Scores a test set on two axes:
  - execution_success: the generated SQL ran without DB error

Usage:
    python -m eval.llm_tester
    python -m eval.llm_tester --test-set path/to/set.yaml
    python -m eval.llm_tester --case 1      # run a single case by id

Output: per-case pass/fail table + aggregate scores to stdout.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _load_test_set(path: str) -> list[dict]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("test_set", [])


def run_eval(test_set_path: str, case_filter: str = None) -> dict:
    cases = _load_test_set(test_set_path)
    if case_filter:
        cases = [c for c in cases if str(c["id"]) == str(case_filter)]
        if not cases:
            print(f"No case with id='{case_filter}' found.")
            return {}

    # INITIALIZE PIPELINE ONCE
    from config import SCHEMA_YAML_PATH, FEW_SHOTS_PATH, MAX_ROWS
    from pipeline.schema_loader import load_schema
    from pipeline.normalizer import QueryNormalizer
    from pipeline.schema_linker import SchemaLinker
    from pipeline.prompt_builder import PromptBuilder
    from pipeline.llm_engine import make_llm_engine
    from pipeline.validator import SQLValidator
    from pipeline.executor import QueryExecutor
    from pipeline.few_shot_retriever import FewShotRetriever

    print("Initializing AI pipeline components...")
    schema_loader = load_schema(SCHEMA_YAML_PATH)
    schema = schema_loader.get_schema()
    normalizer = QueryNormalizer()
    linker = SchemaLinker(schema)
    builder = PromptBuilder(max_rows=MAX_ROWS)
    llm = make_llm_engine()
    validator = SQLValidator(schema)
    executor = QueryExecutor()
    
    try:
        with open(FEW_SHOTS_PATH) as f:
            few_shots = yaml.safe_load(f).get("examples", [])
    except Exception:
        few_shots = []
    retriever = FewShotRetriever(few_shots, persist_path="cache_store_eval")

    results = []
    for case in cases:
        question = case.get("prompt", "")
        print(f"\n[{case['id']}] {question}")
        t0 = time.time()
        
        try:
            norm = normalizer.normalize(question)
            schema_ctx = linker.link_schema(norm["normalized_text"], norm["domain_category"])
            top_k = retriever.get_top_k(norm["normalized_text"], k=3)
            prompt = builder.build_prompt(norm["normalized_text"], schema_ctx, top_k)
            sql, _ = llm.generate_sql_with_retry(prompt, validator, builder)
            
            db_result = executor.execute(sql)
            error = None
            row_count = db_result.get("row_count", 0)
        except Exception as exc:
            sql = None
            error = str(exc)
            row_count = 0

        elapsed = round((time.time() - t0) * 1000)
        
        execution_success = error is None
        passed = execution_success
        
        score = {
            "id": case["id"],
            "question": question,
            "passed": passed,
            "execution_success": execution_success,
            "row_count": row_count,
            "sql": sql,
            "error": error,
            "elapsed_ms": elapsed
        }
        results.append(score)

        status = "PASS" if passed else "FAIL"
        print(f"  {status} | exec={execution_success} rows={row_count} ({elapsed}ms)")
        if error:
            print(f"  error: {error[:120]}")
        if sql:
            print(f"  sql: {sql[:100]}...")

    executor.close()

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    exec_ok = sum(1 for r in results if r["execution_success"])

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed")
    print(f"  Execution success: {exec_ok}/{total}")
    print(f"{'='*60}")

    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 2) if total else 0,
        "execution_success_rate": round(exec_ok / total, 2) if total else 0,
        "cases": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run QueryCraft eval harness")
    parser.add_argument(
        "--test-set",
        default=os.path.join(os.path.dirname(__file__), "model_evaluation_test_set.yaml"),
        help="Path to test set YAML",
    )
    parser.add_argument("--case", default=None, help="Run a single case by id")
    args = parser.parse_args()

    report = run_eval(args.test_set, case_filter=args.case)
    if report:
        print(json.dumps(report, indent=2, default=str))
