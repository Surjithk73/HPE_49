"""
Eval harness for QueryCraft NL→SQL pipeline.

Scores a golden set on two axes:
  - execution_success: the generated SQL ran without DB error
  - column_match:      all expected_columns are present in the result

Usage:
    python -m eval.runner                          # uses default golden_set.yaml
    python -m eval.runner --golden path/to/set.yaml
    python -m eval.runner --case cpu_avg_busy      # run a single case by id

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


def _load_golden_set(path: str) -> list[dict]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("cases", [])


def _run_pipeline(question: str) -> dict:
    """
    Run the single-shot pipeline (normalise → schema link → prompt → LLM → execute).
    Returns a result dict with keys: sql, columns, rows, row_count, error.
    Uses the same pipeline modules as main.py but initialises them fresh.
    """
    try:
        from config import (
            SCHEMA_YAML_PATH, FEW_SHOTS_PATH, MAX_ROWS
        )
        from pipeline.schema_loader import load_schema
        from pipeline.normalizer import QueryNormalizer
        from pipeline.schema_linker import SchemaLinker
        from pipeline.prompt_builder import PromptBuilder
        from pipeline.llm_engine import make_llm_engine
        from pipeline.validator import SQLValidator
        from pipeline.executor import QueryExecutor, detect_chart_type
        from pipeline.few_shot_retriever import FewShotRetriever

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

        norm = normalizer.normalize(question)
        schema_ctx = linker.link_schema(norm["normalized_text"], norm["domain_category"])
        top_k = retriever.get_top_k(norm["normalized_text"], k=3)
        prompt = builder.build_prompt(norm["normalized_text"], schema_ctx, top_k)
        sql, _ = llm.generate_sql_with_retry(prompt, validator, builder)
        result = executor.execute(sql)
        executor.close()
        return {
            "sql": sql,
            "columns": result.get("columns", []),
            "row_count": result.get("row_count", 0),
            "error": None,
        }
    except Exception as exc:
        return {"sql": None, "columns": [], "row_count": 0, "error": str(exc)}


def _score_case(case: dict, result: dict) -> dict:
    expected_cols = {c.lower() for c in case.get("expected_columns", [])}
    actual_cols = {c.lower() for c in result.get("columns", [])}

    execution_success = result.get("error") is None
    column_match = expected_cols.issubset(actual_cols) if expected_cols else True
    row_count_ok = result.get("row_count", 0) >= case.get("expected_row_count_min", 0)

    passed = execution_success and column_match and row_count_ok
    return {
        "id": case["id"],
        "question": case["question"],
        "passed": passed,
        "execution_success": execution_success,
        "column_match": column_match,
        "row_count_ok": row_count_ok,
        "row_count": result.get("row_count"),
        "sql": result.get("sql"),
        "error": result.get("error"),
        "missing_columns": sorted(expected_cols - actual_cols),
    }


def run_eval(golden_set_path: str, case_filter: str = None) -> dict:
    cases = _load_golden_set(golden_set_path)
    if case_filter:
        cases = [c for c in cases if c["id"] == case_filter]
        if not cases:
            print(f"No case with id='{case_filter}' found.")
            return {}

    results = []
    for case in cases:
        print(f"\n[{case['id']}] {case['question']}")
        t0 = time.time()
        pipeline_result = _run_pipeline(case["question"])
        elapsed = round((time.time() - t0) * 1000)
        score = _score_case(case, pipeline_result)
        score["elapsed_ms"] = elapsed
        results.append(score)

        status = "PASS" if score["passed"] else "FAIL"
        print(f"  {status} | exec={score['execution_success']} cols={score['column_match']} rows={score['row_count_ok']} ({elapsed}ms)")
        if score["error"]:
            print(f"  error: {score['error'][:120]}")
        if score["missing_columns"]:
            print(f"  missing columns: {score['missing_columns']}")
        if score["sql"]:
            print(f"  sql: {score['sql'][:100]}...")

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    exec_ok = sum(1 for r in results if r["execution_success"])
    col_ok = sum(1 for r in results if r["column_match"])

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed")
    print(f"  Execution success: {exec_ok}/{total}")
    print(f"  Column match:      {col_ok}/{total}")
    print(f"{'='*60}")

    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 2) if total else 0,
        "execution_success_rate": round(exec_ok / total, 2) if total else 0,
        "column_match_rate": round(col_ok / total, 2) if total else 0,
        "cases": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run QueryCraft eval harness")
    parser.add_argument(
        "--golden",
        default=os.path.join(os.path.dirname(__file__), "golden_set.yaml"),
        help="Path to golden set YAML",
    )
    parser.add_argument("--case", default=None, help="Run a single case by id")
    args = parser.parse_args()

    report = run_eval(args.golden, case_filter=args.case)
    if report:
        print(json.dumps(report, indent=2, default=str))
