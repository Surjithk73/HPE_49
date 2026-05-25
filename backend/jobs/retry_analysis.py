"""
Retry analysis job.

Reads `audit/query_log.db`, finds queries that ultimately failed validation
(the closest available proxy for "needed 2+ retries" — the current schema only
records the final attempt), buckets each failure by error pattern, and emits
recommended prompt / pipeline changes per bucket.

Designed to run on-demand from the dashboard via POST /api/admin/retry-analysis.
"""
from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass, asdict
from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Rule-based classifier
# ---------------------------------------------------------------------------

@dataclass
class Bucket:
    key: str
    label: str
    pattern: re.Pattern
    fix_surface: str
    recommendation: str


# Order matters: first match wins. Quota errors are very chatty so check first.
BUCKETS: List[Bucket] = [
    Bucket(
        key="ollama_unreachable",
        label="Ollama server unreachable or model missing",
        pattern=re.compile(r"Could not reach Ollama|Ollama HTTP 404|Ollama returned no text|Ollama model not configured", re.IGNORECASE),
        fix_surface="env / Ollama server",
        recommendation=(
            "Not a prompt issue. Make sure `ollama serve` is running and the model "
            "set in OLLAMA_MODEL (backend/.env) is pulled — check with `ollama list`. "
            "If OLLAMA_URL points to a non-default host, verify it's reachable."
        ),
    ),
    Bucket(
        key="forbidden_keyword_false_positive",
        label="Validator false-positive on forbidden keyword (substring match)",
        pattern=re.compile(r"Forbidden keyword detected: (TRUNCATE|CREATE|EXEC)", re.IGNORECASE),
        fix_surface="validator.py",
        recommendation=(
            "The FORBIDDEN_KEYWORDS check in validator.py uses substring `in`, so "
            "`date_trunc(...)` triggers TRUNCATE and `create_time` triggers CREATE. "
            "Switch to a word-boundary regex (e.g. r'\\bTRUNCATE\\b'). Prompt cannot "
            "fix this — we actively instruct the model to use date_trunc for "
            "cross-table joins."
        ),
    ),
    Bucket(
        key="injection_false_positive",
        label="Validator false-positive on SQL-injection pattern",
        pattern=re.compile(r"injection pattern detected", re.IGNORECASE),
        fix_surface="validator.py + prompt_builder.py",
        recommendation=(
            "INJECTION_PATTERNS in validator.py includes a bare `--` regex that fires "
            "on any inline double-dash. Tighten to require `--` at start-of-line/token. "
            "Also add a STRICT RULE to prompt_builder: 'Do not emit SQL comments "
            "(`--` or `/* */`) anywhere in the output.'"
        ),
    ),
    Bucket(
        key="unknown_column",
        label="Column does not exist (schema / normalizer drift)",
        pattern=re.compile(r"Column '([^']+)' does not exist", re.IGNORECASE),
        fix_surface="normalizer.py + examples.yaml",
        recommendation=(
            "Usually caused by the normalizer rewriting a user word into a column "
            "name that doesn't exist (e.g. 'reads' -> 'reads_'), reinforced by "
            "few-shot examples using the same wrong name. Audit "
            "backend/pipeline/normalizer.py ABBREVIATIONS against the live schema "
            "and replace stale names in examples.yaml / cache.py."
        ),
    ),
    Bucket(
        key="unknown_table",
        label="Table not in schema",
        pattern=re.compile(r"Table.*(not found|does not exist|not in schema)", re.IGNORECASE),
        fix_surface="schema_linker.py + examples.yaml",
        recommendation=(
            "The model picked a table outside the macht413 schema. Verify the "
            "schema_linker is surfacing all relevant tables for this domain, and "
            "that few-shot examples qualify with `macht413.`."
        ),
    ),
    Bucket(
        key="syntax",
        label="SQL syntax error",
        pattern=re.compile(r"syntax error|Failed to parse", re.IGNORECASE),
        fix_surface="prompt_builder.py",
        recommendation=(
            "Add a STRICT RULE reminding the model that output must be a single "
            "valid PostgreSQL SELECT — no trailing prose, no markdown fences, no "
            "multiple statements separated by ;."
        ),
    ),
    Bucket(
        key="non_select",
        label="Non-SELECT statement emitted",
        pattern=re.compile(r"Only SELECT statements are permitted", re.IGNORECASE),
        fix_surface="prompt_builder.py",
        recommendation=(
            "The STRICT RULES already forbid non-SELECT, but the model still emitted "
            "one. Consider few-shot examples that explicitly refuse a write-style "
            "request, or move the rule to the top of the prompt."
        ),
    ),
]


def _classify(error: str) -> Bucket | None:
    if not error:
        return None
    for bucket in BUCKETS:
        if bucket.pattern.search(error):
            return bucket
    return None


# ---------------------------------------------------------------------------
# Audit log access
# ---------------------------------------------------------------------------

def _resolve_db_path() -> str:
    """Find audit/query_log.db relative to the backend dir."""
    here = os.path.dirname(__file__)
    backend_dir = os.path.dirname(here)
    return os.path.join(backend_dir, "audit", "query_log.db")


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _fetch_failed_rows(db_path: str) -> List[Dict[str, Any]]:
    """
    Return final-failure rows from query_log. Falls back gracefully if the
    optional retry_count column hasn't been added yet.
    """
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    has_retry = _has_column(conn, "query_log", "retry_count")

    cols = (
        "id, timestamp, original_input, normalized_input, domain_category, "
        "generated_sql, validation_error"
    )
    if has_retry:
        cols += ", retry_count"

    cur = conn.execute(
        f"SELECT {cols} FROM query_log WHERE validation_passed = 0 ORDER BY id DESC"
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_analysis(db_path: str | None = None) -> Dict[str, Any]:
    """
    Return a structured retry analysis report.

    Shape:
      {
        "total_failures": int,
        "buckets": [
          {
            "key": str,
            "label": str,
            "fix_surface": str,
            "recommendation": str,
            "count": int,
            "samples": [ {id, timestamp, original_input, validation_error}, ... ]
          },
          ...
        ],
        "unclassified": [ ... ],
        "summary": str,
      }
    """
    path = db_path or _resolve_db_path()
    rows = _fetch_failed_rows(path)

    grouped: Dict[str, Dict[str, Any]] = {}
    unclassified: List[Dict[str, Any]] = []

    for row in rows:
        bucket = _classify(row.get("validation_error") or "")
        sample = {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "original_input": row["original_input"],
            "domain": row.get("domain_category"),
            "validation_error": (row.get("validation_error") or "")[:400],
            "retry_count": row.get("retry_count"),
        }
        if bucket is None:
            unclassified.append(sample)
            continue
        entry = grouped.setdefault(
            bucket.key,
            {
                "key": bucket.key,
                "label": bucket.label,
                "fix_surface": bucket.fix_surface,
                "recommendation": bucket.recommendation,
                "count": 0,
                "samples": [],
            },
        )
        entry["count"] += 1
        if len(entry["samples"]) < 5:  # cap samples per bucket
            entry["samples"].append(sample)

    buckets_out = sorted(grouped.values(), key=lambda b: -b["count"])

    if not rows:
        summary = "No failed queries in the audit log — nothing to analyze."
    else:
        bullets = [f"{b['count']}x {b['label']} -> {b['fix_surface']}" for b in buckets_out]
        if unclassified:
            bullets.append(f"{len(unclassified)}x unclassified")
        summary = f"{len(rows)} final-failure rows analyzed: " + "; ".join(bullets)

    return {
        "total_failures": len(rows),
        "buckets": buckets_out,
        "unclassified": unclassified,
        "summary": summary,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_analysis(), indent=2))
