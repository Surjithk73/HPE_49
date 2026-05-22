"""
QueryCraft — FastAPI Backend
Wires all pipeline components into REST API endpoints.

New endpoints:
  GET  /api/stats                — audit log analytics dashboard
  GET  /api/cache/threshold      — read current similarity threshold
  POST /api/cache/threshold      — update threshold at runtime (no restart)

Other improvements:
  - Execution result (success + row_count) is passed back to cache.store()
    so bad entries are auto-flagged via cache.flag_failed()
  - Executor pool is closed cleanly on shutdown
  - llm_retries count is tracked and written to the audit log
"""
import io
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# ── Pipeline imports ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from config import (
    SCHEMA_YAML_PATH, FEW_SHOTS_PATH, AUDIT_LOG_PATH,
    GEMINI_MODEL, MAX_ROWS, LLM_PROVIDER, OLLAMA_MODEL,
)
from pipeline.schema_loader import load_schema
from pipeline.normalizer import QueryNormalizer
from pipeline.schema_linker import SchemaLinker
from pipeline.prompt_builder import PromptBuilder
from pipeline.llm_engine import LLMError, make_llm_engine
from pipeline.validator import SQLValidator
from pipeline.executor import QueryExecutor, ExecutionError, detect_chart_type
from pipeline.cache import SemanticCache
from pipeline.report_generator import generate_report
from audit.query_log import AuditLog

import psycopg2
import yaml


# ── Global component instances (initialised at startup) ───────────────────────
_schema_loader = None
_schema        = None
_normalizer    = None
_linker        = None
_builder       = None
_llm_engine    = None
_validator     = None
_executor      = None
_cache         = None
_audit         = None
_few_shots     = []


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise all pipeline components at startup."""
    global _schema_loader, _schema, _normalizer, _linker, _builder
    global _llm_engine, _validator, _executor, _cache, _audit, _few_shots

    print("\n[QueryCraft] Starting up...")

    # Schema
    _schema_loader = load_schema(SCHEMA_YAML_PATH)
    _schema        = _schema_loader.get_schema()
    print(f"[QueryCraft] Schema loaded — {len(_schema)} tables")

    # Pipeline components
    _normalizer = QueryNormalizer()
    _linker     = SchemaLinker(_schema)
    _builder    = PromptBuilder(max_rows=MAX_ROWS)
    _validator  = SQLValidator(_schema)
    print("[QueryCraft] Pipeline components ready")

    # LLM engine — provider chosen by LLM_PROVIDER (gemini|ollama)
    _llm_engine = make_llm_engine()
    print(f"[QueryCraft] LLM engine ready — provider: {LLM_PROVIDER}, model: {_llm_engine.model_name}")

    # Executor — creates the connection pool
    _executor = QueryExecutor()

    # Semantic cache — embedding model loads in background thread
    # API is available immediately; cache returns misses until model is ready
    _cache = SemanticCache(persist_path="cache_store")
    print(f"[QueryCraft] Cache initialised — {_cache.count()} entries (model loading in background)")

    # Audit log
    _audit = AuditLog(AUDIT_LOG_PATH)
    print("[QueryCraft] Audit log ready")

    # Few-shot examples (optional — empty list is fine)
    try:
        with open(FEW_SHOTS_PATH, "r") as f:
            data = yaml.safe_load(f)
            _few_shots = data.get("examples", []) if data else []
        print(f"[QueryCraft] Few-shots loaded — {len(_few_shots)} examples")
    except Exception:
        _few_shots = []
        print("[QueryCraft] No few-shot examples found (using empty list)")

    print("[QueryCraft] Startup complete\n")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    print("[QueryCraft] Shutting down...")
    if _executor:
        _executor.close()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="QueryCraft API",
    version="1.0.0",
    description="Natural Language → SQL for HPE NonStop performance data",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str

class SqlRequest(BaseModel):
    sql: str

class ExportRequest(BaseModel):
    sql: str
    format: str                  # "csv" | "excel" | "pdf"
    query_text: Optional[str] = ""

class ThresholdRequest(BaseModel):
    threshold: float = Field(..., gt=0.0, le=1.0,
                             description="Cosine similarity threshold (0 < value ≤ 1)")


# ── Helper ────────────────────────────────────────────────────────────────────
def _ext_for(fmt: str) -> str:
    return {"csv": "csv", "excel": "xlsx", "xlsx": "xlsx", "pdf": "pdf"}.get(fmt.lower(), fmt)


# ── Routes ────────────────────────────────────────────────────────────────────

# GET /api/health
@app.get("/api/health")
def health():
    """Health check — verifies DB connection and cache availability."""
    db_ok    = False
    cache_ok = False

    try:
        from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME,
            user=DB_USER, password=DB_PASSWORD,
            connect_timeout=3
        )
        conn.close()
        db_ok = True
    except Exception:
        pass

    try:
        cache_ok = _cache is not None and _cache.collection is not None
    except Exception:
        pass

    return {
        "status":            "ok",
        "db_connected":      db_ok,
        "cache_ready":       cache_ok,
        "cache_model_ready": _cache.is_model_ready if _cache else False,
        "llm_provider":      LLM_PROVIDER,
        "llm_model":         (_llm_engine.model_name if _llm_engine else None) or GEMINI_MODEL,
        "cache_entries":     _cache.count() if _cache else 0,
        "schema_tables":     len(_schema) if _schema else 0,
    }


# GET /api/schema
@app.get("/api/schema")
def schema_info():
    """Return table names, column counts, and descriptions."""
    result = []
    for table_name, table_def in _schema.items():
        columns = table_def.get("columns", {})
        result.append({
            "table_name":   table_name,
            "column_count": len(columns),
            "description":  table_def.get("purpose", "")[:200],
        })
    return result


# GET /api/history
@app.get("/api/history")
def history():
    """Return last 50 query log entries."""
    return _audit.get_history(50)


# GET /api/stats  ── NEW ──────────────────────────────────────────────────────
@app.get("/api/stats")
def stats():
    """
    Analytics dashboard over the full audit log.

    Returns:
        total_queries           — total queries logged
        cache_hit_rate          — fraction served from cache
        avg_execution_time_ms   — mean execution time across all queries
        top_domains             — top 10 queried domains with counts
        validation_failure_rate — fraction that failed SQL validation
        retry_rate              — fraction of LLM queries that needed a retry
    """
    return _audit.get_stats()


# POST /api/admin/retry-analysis
@app.post("/api/admin/retry-analysis")
def retry_analysis():
    """
    Analyze the audit log for queries that exhausted the retry budget,
    bucket them by failure mode, and emit recommended prompt / pipeline
    changes. See backend/jobs/retry_analysis.py for the classifier rules.
    """
    from jobs.retry_analysis import run_analysis
    return run_analysis()


# POST /api/query
@app.post("/api/query")
def run_query(req: QueryRequest):
    """
    Main pipeline endpoint.
    NL query → SQL → validate → execute → return results.
    """
    original_query = req.query.strip()

    if not original_query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    log_entry = {
        "original_input":    original_query,
        "normalized_input":  "",
        "domain_category":   "",
        "generated_sql":     None,
        "validation_passed": False,
        "validation_error":  None,
        "cache_hit":         False,
        "row_count":         None,
        "execution_time_ms": None,
        "export_format":     None,
        "llm_retries":       0,
    }

    try:
        # Step 1 — Normalize
        norm      = _normalizer.normalize(original_query)
        norm_text = norm["normalized_text"]
        domain    = norm["domain_category"]
        log_entry["normalized_input"] = norm_text
        log_entry["domain_category"]  = domain

        # Step 2 — Cache lookup
        cache_result = _cache.lookup(norm_text)

        # Track the prompt sent to the LLM for debugging
        debug_prompt = None

        if cache_result.hit:
            sql = cache_result.sql
            log_entry["cache_hit"]         = True
            log_entry["generated_sql"]     = sql
            log_entry["validation_passed"] = True
            debug_prompt = "[Cache Hit] No prompt was sent to the LLM — SQL was served from the semantic cache."
        else:
            # Step 3 — Schema linking
            schema_context = _linker.link_schema(norm_text, domain)

            # Step 4 — Prompt building
            prompt = _builder.build_prompt(norm_text, schema_context, _few_shots)

            # Capture the exact prompt for debugging
            debug_prompt = prompt
            print("\n" + "=" * 80)
            print("[DEBUG] Exact prompt sent to Gemini API:")
            print("=" * 80)
            print(prompt)
            print("=" * 80 + "\n")

            # Step 5 — LLM generation with retry
            # We monkey-patch the builder temporarily to count retries
            retry_count = 0
            original_build_retry = _builder.build_retry_prompt

            def _counting_retry(original_prompt, failed_sql, error):
                nonlocal retry_count
                retry_count += 1
                return original_build_retry(original_prompt, failed_sql, error)

            _builder.build_retry_prompt = _counting_retry

            try:
                sql = _llm_engine.generate_sql_with_retry(
                    prompt=prompt,
                    validator=_validator,
                    prompt_builder=_builder,
                    max_retries=2
                )
            except LLMError as e:
                log_entry["validation_error"] = str(e)
                log_entry["llm_retries"]      = retry_count
                _audit.log_query(log_entry)
                raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")
            finally:
                _builder.build_retry_prompt = original_build_retry

            log_entry["llm_retries"] = retry_count

            # Step 6 — Final validation
            val = _validator.validate(sql)
            if not val.valid:
                log_entry["validation_error"] = val.error
                _audit.log_query(log_entry)
                raise HTTPException(status_code=400, detail=f"SQL validation failed: {val.error}")

            sql = val.sanitized_sql
            log_entry["generated_sql"]     = sql
            log_entry["validation_passed"] = True

        # Step 7 — Execute
        execution_success = False
        try:
            result = _executor.execute(sql)
            execution_success = True
        except ExecutionError as e:
            log_entry["validation_error"] = str(e)
            _audit.log_query(log_entry)
            # If this was a cache hit that failed, flag the entry as bad
            if cache_result.hit:
                _cache.flag_failed(norm_text)
            raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

        # Step 8 — Chart type
        chart_type = detect_chart_type(result.columns)

        # Step 9 — Store in cache (only on cache miss, with execution metadata)
        if not cache_result.hit:
            _cache.store(
                norm_text,
                sql,
                execution_success=execution_success,
                row_count=result.row_count,
            )

        # Step 10 — Audit log
        log_entry["row_count"]         = result.row_count
        log_entry["execution_time_ms"] = result.execution_time_ms
        _audit.log_query(log_entry)

        return {
            "sql":               sql,
            "columns":           result.columns,
            "rows":              result.rows,
            "row_count":         result.row_count,
            "execution_time_ms": result.execution_time_ms,
            "cache_hit":         cache_result.hit,
            "chart_type":        chart_type,
            "domain":            domain,
            "debug_prompt":      debug_prompt,
        }

    except HTTPException:
        raise
    except Exception as e:
        log_entry["validation_error"] = str(e)
        _audit.log_query(log_entry)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# POST /api/sql
@app.post("/api/sql")
def run_sql(req: SqlRequest):
    """
    Direct SQL execution endpoint.
    Accepts a raw SELECT query, validates it, executes it, and returns results.
    Bypasses the LLM pipeline entirely — no normalization, no cache, no prompt building.
    """
    raw_sql = req.sql.strip()

    if not raw_sql:
        raise HTTPException(status_code=400, detail="SQL cannot be empty")

    log_entry = {
        "original_input":    raw_sql,
        "normalized_input":  raw_sql,
        "domain_category":   "sql_direct",
        "generated_sql":     raw_sql,
        "validation_passed": False,
        "validation_error":  None,
        "cache_hit":         False,
        "row_count":         None,
        "execution_time_ms": None,
        "export_format":     None,
        "llm_retries":       0,
    }

    val = _validator.validate(raw_sql)
    if not val.valid:
        log_entry["validation_error"] = val.error
        _audit.log_query(log_entry)
        raise HTTPException(status_code=400, detail=f"SQL validation failed: {val.error}")

    sql = val.sanitized_sql
    log_entry["validation_passed"] = True
    log_entry["generated_sql"]     = sql

    try:
        result = _executor.execute(sql)
    except ExecutionError as e:
        log_entry["validation_error"] = str(e)
        _audit.log_query(log_entry)
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

    chart_type = detect_chart_type(result.columns)

    log_entry["row_count"]         = result.row_count
    log_entry["execution_time_ms"] = result.execution_time_ms
    _audit.log_query(log_entry)

    return {
        "sql":               sql,
        "columns":           result.columns,
        "rows":              result.rows,
        "row_count":         result.row_count,
        "execution_time_ms": result.execution_time_ms,
        "cache_hit":         False,
        "chart_type":        chart_type,
        "domain":            "sql_direct",
    }


# POST /api/export
@app.post("/api/export")
def export(req: ExportRequest):
    """Export query results as CSV, Excel, or PDF."""
    fmt = req.format.lower().strip()
    if fmt not in ("csv", "excel", "xlsx", "pdf"):
        raise HTTPException(status_code=400, detail=f"Unsupported format: {req.format}")

    val = _validator.validate(req.sql)
    if not val.valid:
        raise HTTPException(status_code=400, detail=f"SQL validation failed: {val.error}")

    sql = val.sanitized_sql

    try:
        result = _executor.execute(sql)
    except ExecutionError as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

    try:
        file_bytes, mime_type = generate_report(
            format=fmt,
            columns=result.columns,
            rows=result.rows,
            query_text=req.query_text or "",
            sql=sql
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

    ext      = _ext_for(fmt)
    filename = f"querycraft_report.{ext}"

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=mime_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# GET /api/cache
@app.get("/api/cache")
def get_cache():
    """Get all cached query entries (includes metadata fields)."""
    entries = _cache.get_all()
    return {
        "count":   len(entries),
        "entries": entries,
    }


# DELETE /api/cache
@app.delete("/api/cache")
def clear_cache():
    """Clear all entries from the cache."""
    _cache.clear()
    return {"status": "success", "message": "Cache cleared", "count": 0}


# DELETE /api/cache/query
@app.delete("/api/cache/query")
def delete_cache_entry(query: str = Query(..., description="The query text to delete")):
    """Delete a specific query from the cache by query text."""
    norm      = _normalizer.normalize(query)
    norm_text = norm["normalized_text"]
    deleted   = _cache.delete(norm_text)

    if deleted:
        return {
            "status":     "success",
            "message":    "Cache entry deleted",
            "query":      query,
            "normalized": norm_text,
        }
    raise HTTPException(status_code=404, detail="Cache entry not found")


# GET /api/cache/threshold  ── NEW ────────────────────────────────────────────
@app.get("/api/cache/threshold")
def get_threshold():
    """Return the current cache similarity threshold."""
    return {
        "threshold": _cache.get_threshold(),
        "description": (
            "Cosine similarity threshold for cache hits. "
            "Higher = stricter matching. Range: (0.0, 1.0]"
        ),
    }


# POST /api/cache/threshold  ── NEW ───────────────────────────────────────────
@app.post("/api/cache/threshold")
def set_threshold(req: ThresholdRequest):
    """
    Update the cache similarity threshold at runtime.

    No server restart required.  The new value takes effect immediately
    for all subsequent lookups.

    Body:
        { "threshold": 0.85 }   — float in (0.0, 1.0]
    """
    try:
        _cache.set_threshold(req.threshold)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {
        "status":    "updated",
        "threshold": _cache.get_threshold(),
        "message":   f"Cache similarity threshold set to {req.threshold}",
    }
