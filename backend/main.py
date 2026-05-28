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
import traceback
import logging
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("querycraft")

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
from pipeline.few_shot_retriever import FewShotRetriever
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
_few_shot_retriever = None
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
        
    # Few-shot retriever (RAG for prompts)
    _few_shot_retriever = FewShotRetriever(_few_shots, persist_path="cache_store")
    print("[QueryCraft] Few-shot retriever ready")

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
    include_chart: Optional[bool] = True
    include_table: Optional[bool] = True
    chart_types: Optional[List[str]] = None
    chart_type_override: Optional[str] = None
    # Base64-encoded PNG captured from the UI chart (sent by the frontend).
    # When present, this image is embedded directly in the PDF instead of
    # regenerating a server-side matplotlib chart — ensures PDF matches the UI.
    chart_image_base64: Optional[str] = None

class ThresholdRequest(BaseModel):
    threshold: float = Field(..., gt=0.0, le=1.0,
                             description="Cosine similarity threshold (0 < value ≤ 1)")

class ModelRequest(BaseModel):
    model: str = Field(..., description="Gemini model name to switch to")

class ExplainRequest(BaseModel):
    sql: str
    query_text: str
    columns: List[str]
    rows: List[dict]


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
        "cache_confidence":  None,
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
        # Always record the confidence score so near-misses are visible in
        # the audit log — this lets you tune the threshold with real data.
        log_entry["cache_confidence"] = cache_result.confidence

        # Track the prompt sent to the LLM for debugging
        debug_prompt = None
        raw_llm_output = None

        if cache_result.hit:
            sql = cache_result.sql
            log_entry["cache_hit"]         = True
            log_entry["generated_sql"]     = sql
            log_entry["validation_passed"] = True
            debug_prompt = "[Cache Hit] No prompt was sent to the LLM — SQL was served from the semantic cache."
        else:
            # Step 3 — Schema linking
            schema_context = _linker.link_schema(norm_text, domain)

            # Step 4 — Prompt building (RAG for few-shots)
            top_few_shots = _few_shot_retriever.get_top_k(norm_text, k=3) if _few_shot_retriever else []
            prompt = _builder.build_prompt(norm_text, schema_context, top_few_shots)

            # Capture the exact prompt for debugging
            debug_prompt = prompt
            # Only print the full prompt to terminal when DEBUG_PROMPTS=true
            if os.getenv("DEBUG_PROMPTS", "").lower() == "true":
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
                sql, raw_llm_output = _llm_engine.generate_sql_with_retry(
                    prompt=prompt,
                    validator=_validator,
                    prompt_builder=_builder,
                    max_retries=2
                )
            except LLMError as e:
                log_entry["validation_error"] = str(e)
                log_entry["llm_retries"]      = retry_count
                _audit.log_query(log_entry)
                logger.error(f"[/api/query] LLM error: {e}")
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
            logger.error(f"[/api/query] Execution error — SQL: {sql}\nError: {e}")
            raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

        # Step 8 — Chart type
        chart_type = detect_chart_type(result.columns, result.rows)

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
            "raw_llm_output":    raw_llm_output,
        }

    except HTTPException:
        raise
    except Exception as e:
        log_entry["validation_error"] = str(e)
        _audit.log_query(log_entry)
        tb = traceback.format_exc()
        logger.error(f"[/api/query] Unexpected error: {e}\n{tb}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# POST /api/image-to-query
@app.post("/api/image-to-query")
async def image_to_query(file: UploadFile = File(...)):
    """
    Image-based query entry point.

    Pipeline: chart image → Gemini multimodal (image→NL question) → /api/query.
    Returns the standard QueryResponse plus the inferred natural-language prompt.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")

    image_bytes = await file.read()
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty image upload")
    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 8 MB)")

    try:
        from config import GEMINI_API_KEY
        import google.generativeai as genai
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini SDK not available: {e}")

    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    model_name = (_llm_engine.model_name if _llm_engine else None) or GEMINI_MODEL

    instruction = (
        "You are looking at a chart screenshot from HPE NonStop Measure performance reports. "
        "The underlying dataset is in PostgreSQL schema `macht413` with tables: "
        "cpu, proc, disc, file, dfile, dopen, tmf, ossns, udef. "
        "Write ONE concise natural-language analytics question that this chart would answer, "
        "phrased so it can be translated into a SQL query against that schema. "
        "Do NOT write SQL. Do NOT describe the chart. Output only the question, on a single line."
    )

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name)
        resp = model.generate_content([
            instruction,
            {"mime_type": file.content_type, "data": image_bytes},
        ])
        nl_question = (resp.text or "").strip().splitlines()[0].strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gemini image call failed: {e}")

    if not nl_question:
        raise HTTPException(status_code=502, detail="Gemini returned an empty question for the image")

    # Reuse the existing NL→SQL pipeline.
    result = run_query(QueryRequest(query=nl_question))
    if isinstance(result, dict):
        result["inferred_query"] = nl_question
    return result


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
        logger.error(f"[/api/sql] Execution error — SQL: {sql}\nError: {e}")
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

    chart_type = detect_chart_type(result.columns, result.rows)

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
            sql=sql,
            include_chart=req.include_chart if req.include_chart is not None else True,
            include_table=req.include_table if req.include_table is not None else True,
            chart_types=req.chart_types,
            chart_type_override=req.chart_type_override,
            chart_image_base64=req.chart_image_base64,
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


# ── Model switcher ────────────────────────────────────────────────────────────

# Models the UI is allowed to switch to.  Only Gemini models are listed here;
# Ollama switching is handled by restarting with a different .env.
ALLOWED_GEMINI_MODELS = [
    "gemini-3.1-flash-lite",    # default — fast, low cost
    "gemini-2.0-flash",         # stronger reasoning
    "gemini-2.5-flash",         # latest generation
    "gemini-3.5-flash",         # latest 3.x series
    "gemini-3-flash-preview",   # gemini-3-flash (preview name on API)
]


# GET /api/model
@app.get("/api/model")
def get_model():
    """Return the currently active LLM model name and the list of available models."""
    return {
        "current_model":   _llm_engine.model_name if _llm_engine else None,
        "available_models": ALLOWED_GEMINI_MODELS,
        "provider":        LLM_PROVIDER,
    }


# POST /api/model
@app.post("/api/model")
def switch_model(req: ModelRequest):
    """
    Hot-swap the active Gemini model at runtime.

    No server restart required.  The new model takes effect immediately
    for all subsequent queries.  Cache entries are not invalidated — cached
    SQL is model-agnostic.

    Body:
        { "model": "gemini-2.5-flash" }

    Only Gemini models are supported via this endpoint.  To switch to Ollama,
    update LLM_PROVIDER in .env and restart the server.
    """
    global _llm_engine

    if LLM_PROVIDER != "gemini":
        raise HTTPException(
            status_code=400,
            detail=f"Model switching is only supported for LLM_PROVIDER=gemini. "
                   f"Current provider: {LLM_PROVIDER}"
        )

    requested = req.model.strip()
    if requested not in ALLOWED_GEMINI_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{requested}' is not in the allowed list. "
                   f"Allowed: {ALLOWED_GEMINI_MODELS}"
        )

    previous = _llm_engine.model_name if _llm_engine else None

    if previous == requested:
        return {
            "status":         "unchanged",
            "model":          requested,
            "previous_model": previous,
            "message":        f"Already using {requested}",
        }

    try:
        from pipeline.llm_engine import LLMEngine
        _llm_engine = LLMEngine(model=requested)
        logger.info(f"[/api/model] Switched from {previous} → {requested}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialise model '{requested}': {e}")

    return {
        "status":         "switched",
        "model":          requested,
        "previous_model": previous,
        "message":        f"Model switched to {requested}",
    }


# POST /api/explain
@app.post("/api/explain")
def explain_results(req: ExplainRequest):
    """Explain query execution results and identify outliers using LLM."""
    if not _llm_engine:
        raise HTTPException(status_code=500, detail="LLM Engine not initialized")

    # Save token usage by truncating rows to 50
    limit = 50
    truncated_rows = req.rows[:limit]

    import json
    rows_json = json.dumps(truncated_rows, indent=2)

    prompt = f"""You are a senior database performance analyst and system administrator for HPE NonStop databases.
Analyze the following query execution results to explain what they mean for the system's performance and health, and highlight any outliers, unusual values, anomalies, or potential issues.

Context:
- Original User Question: {req.query_text}
- Executed SQL: {req.sql}

Results (truncated to first {limit} rows if larger):
Columns: {", ".join(req.columns)}
Data Rows:
{rows_json}

Provide a concise analysis (approx. 2-3 short paragraphs or bullet points).
Identify any outlier values or performance metrics that are high, low, or typical, and explain their significance to the system.
Do not assume context that is not present in the columns.
"""
    try:
        explanation = _llm_engine.generate_text(prompt)
        return {"explanation": explanation}
    except LLMError as e:
        raise HTTPException(status_code=500, detail=f"LLM explanation generation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected explanation generation error: {str(e)}")
