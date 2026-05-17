"""
QueryCraft — FastAPI Backend
Wires all pipeline components into REST API endpoints.
"""
import io
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── Pipeline imports ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from config import (
    SCHEMA_YAML_PATH, FEW_SHOTS_PATH, AUDIT_LOG_PATH,
    GEMINI_MODEL, MAX_ROWS
)
from pipeline.schema_loader import load_schema
from pipeline.normalizer import QueryNormalizer
from pipeline.schema_linker import SchemaLinker
from pipeline.prompt_builder import PromptBuilder
from pipeline.llm_engine import LLMEngine, LLMError
from pipeline.validator import SQLValidator
from pipeline.executor import QueryExecutor, ExecutionError, detect_chart_type
from pipeline.cache import SemanticCache
from pipeline.report_generator import generate_report
from audit.query_log import AuditLog

import psycopg2
import yaml


# ── Global component instances (initialised at startup) ───────────────────────
_schema_loader  = None
_schema         = None
_normalizer     = None
_linker         = None
_builder        = None
_llm_engine     = None
_validator      = None
_executor       = None
_cache          = None
_audit          = None
_few_shots      = []


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
    _executor   = QueryExecutor()
    print("[QueryCraft] Pipeline components ready")

    # LLM engine
    _llm_engine = LLMEngine()
    print(f"[QueryCraft] LLM engine ready — model: {GEMINI_MODEL}")

    # Semantic cache
    _cache = SemanticCache(persist_path="cache_store")
    print(f"[QueryCraft] Cache ready — {_cache.count()} entries")

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
    print("[QueryCraft] Shutting down...")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="QueryCraft API",
    version="1.0.0",
    description="Natural Language → SQL for HPE NonStop performance data",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


# ── Request / Response models ─────────────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str

class ExportRequest(BaseModel):
    sql: str
    format: str          # "csv" | "excel" | "pdf"
    query_text: Optional[str] = ""


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

    # DB check
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

    # Cache check
    try:
        cache_ok = _cache is not None and _cache.collection is not None
    except Exception:
        pass

    return {
        "status": "ok",
        "db_connected": db_ok,
        "cache_ready": cache_ok,
        "llm_model": GEMINI_MODEL,
        "cache_entries": _cache.count() if _cache else 0,
        "schema_tables": len(_schema) if _schema else 0
    }


# GET /api/schema
@app.get("/api/schema")
def schema_info():
    """Return table names, column counts, and descriptions."""
    result = []
    for table_name, table_def in _schema.items():
        columns = table_def.get("columns", {})
        result.append({
            "table_name": table_name,
            "column_count": len(columns),
            "description": table_def.get("purpose", "")[:200]
        })
    return result


# GET /api/history
@app.get("/api/history")
def history():
    """Return last 50 query log entries."""
    return _audit.get_history(50)


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
        "original_input":   original_query,
        "normalized_input": "",
        "domain_category":  "",
        "generated_sql":    None,
        "validation_passed": False,
        "validation_error": None,
        "cache_hit":        False,
        "row_count":        None,
        "execution_time_ms": None,
        "export_format":    None,
    }

    try:
        # Step 1 — Normalize
        norm        = _normalizer.normalize(original_query)
        norm_text   = norm["normalized_text"]
        domain      = norm["domain_category"]
        log_entry["normalized_input"] = norm_text
        log_entry["domain_category"]  = domain

        # Step 2 — Cache lookup
        cache_result = _cache.lookup(norm_text)

        if cache_result.hit:
            sql = cache_result.sql
            log_entry["cache_hit"]        = True
            log_entry["generated_sql"]    = sql
            log_entry["validation_passed"] = True
        else:
            # Step 3 — Schema linking
            schema_context = _linker.link_schema(norm_text, domain)

            # Step 4 — Prompt building
            prompt = _builder.build_prompt(norm_text, schema_context, _few_shots)

            # Step 5 — LLM generation with retry
            try:
                sql = _llm_engine.generate_sql_with_retry(
                    prompt=prompt,
                    validator=_validator,
                    prompt_builder=_builder,
                    max_retries=2
                )
            except LLMError as e:
                log_entry["validation_error"] = str(e)
                _audit.log_query(log_entry)
                raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

            # Step 6 — Final validation
            val = _validator.validate(sql)
            if not val.valid:
                log_entry["validation_error"] = val.error
                _audit.log_query(log_entry)
                raise HTTPException(status_code=400, detail=f"SQL validation failed: {val.error}")

            sql = val.sanitized_sql
            log_entry["generated_sql"]    = sql
            log_entry["validation_passed"] = True

        # Step 7 — Execute
        try:
            result = _executor.execute(sql)
        except ExecutionError as e:
            log_entry["validation_error"] = str(e)
            _audit.log_query(log_entry)
            raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

        # Step 8 — Chart type
        chart_type = detect_chart_type(result.columns)

        # Step 9 — Store in cache (only on cache miss)
        if not cache_result.hit:
            _cache.store(norm_text, sql)

        # Step 10 — Audit log
        log_entry["row_count"]         = result.row_count
        log_entry["execution_time_ms"] = result.execution_time_ms
        _audit.log_query(log_entry)

        return {
            "sql":              sql,
            "columns":          result.columns,
            "rows":             result.rows,
            "row_count":        result.row_count,
            "execution_time_ms": result.execution_time_ms,
            "cache_hit":        cache_result.hit,
            "chart_type":       chart_type,
            "domain":           domain,
        }

    except HTTPException:
        raise
    except Exception as e:
        log_entry["validation_error"] = str(e)
        _audit.log_query(log_entry)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# POST /api/export
@app.post("/api/export")
def export(req: ExportRequest):
    """
    Export query results as CSV, Excel, or PDF.
    Re-validates and re-executes the SQL before generating the file.
    """
    # Validate format
    fmt = req.format.lower().strip()
    if fmt not in ("csv", "excel", "xlsx", "pdf"):
        raise HTTPException(status_code=400, detail=f"Unsupported format: {req.format}")

    # Re-validate SQL
    val = _validator.validate(req.sql)
    if not val.valid:
        raise HTTPException(status_code=400, detail=f"SQL validation failed: {val.error}")

    sql = val.sanitized_sql

    # Execute
    try:
        result = _executor.execute(sql)
    except ExecutionError as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

    # Generate report
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

    ext = _ext_for(fmt)
    filename = f"querycraft_report.{ext}"

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=mime_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# GET /api/cache
@app.get("/api/cache")
def get_cache():
    """Get all cached query entries."""
    entries = _cache.get_all()
    return {
        "count": len(entries),
        "entries": entries
    }


# DELETE /api/cache
@app.delete("/api/cache")
def clear_cache():
    """Clear all entries from the cache."""
    _cache.clear()
    return {
        "status": "success",
        "message": "Cache cleared",
        "count": 0
    }


# DELETE /api/cache/{query}
@app.delete("/api/cache/query")
def delete_cache_entry(query: str):
    """
    Delete a specific query from the cache.
    
    Query parameter:
        query: The normalized query text to delete
    """
    # Normalize the query first
    norm = _normalizer.normalize(query)
    norm_text = norm["normalized_text"]
    
    # Delete from cache
    deleted = _cache.delete(norm_text)
    
    if deleted:
        return {
            "status": "success",
            "message": f"Cache entry deleted",
            "query": query,
            "normalized": norm_text
        }
    else:
        raise HTTPException(status_code=404, detail="Cache entry not found")

