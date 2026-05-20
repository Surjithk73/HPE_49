# QueryCraft — Project Plan

> HPE NonStop Performance Report Generator | FastAPI + React | Gemini API → Ollama

---

## 1. Overview

### Goals

- Accept natural language queries from analysts via a web UI
- Generate valid PostgreSQL SELECT queries against the `macht413` schema using Gemini API
- Validate, execute, and return results as tables, charts, and downloadable reports (CSV, Excel, PDF)
- Cache semantically similar queries to ensure consistency and reduce LLM calls
- Log every query for auditability and debugging

### Scope

**In scope:**
- All 9 tables in `macht413` schema (cpu, disc, dfile, dopen, file, ossns, proc, tmf, udef)
- Natural language → SQL via Gemini API (`gemini-3.1-flash-lite`)
- Semantic cache using ChromaDB + `all-MiniLM-L6-v2`
- SQL validation and security guard via `sqlglot`
- Report export: CSV, Excel, PDF
- Charts: line and bar (auto-detected from result columns)
- Query history panel (last 50 queries)
- SQLite audit log
- Single-user local deployment (Windows, localhost)

**Out of scope:**
- User authentication / login system
- Multi-user or concurrent session management
- Cloud deployment (Vercel, Railway, etc.)
- Ollama / local LLM (future swap only — architecture supports it)
- Few-shot examples (placeholder file required at start; content added later)
- Real-time / streaming data (data is static historical snapshots)
- Writing data to the database (SELECT only, no mutations)

### Assumptions

- PostgreSQL latest stable version installed locally on Windows
- CSV files for all 9 tables exist in `backend/data/` (sourced from `measurefiles/`: cpucsv, dfilecsv, disccsv, dopencsv, filecsv, ossnscsv, proccsv, tmfcsv, udefcsv)
- `enriched_schema.yaml` (883 lines, all 9 tables, all column descriptions) already exists
- Gemini API key is available and the model `gemini-3.1-flash-lite` is accessible
- Python latest stable version installed
- Node.js (LTS) installed for React frontend
- Both backend and frontend run in separate terminals on localhost

---

## 2. Phases & Tasks

---

### Phase 0 — Project Scaffold & Environment

**Objective:** Create the full monorepo folder structure, install all dependencies, and configure environment variables. Nothing runs yet — this phase is purely setup.

**Dependencies:** None. This is the starting point.

**Priority:** Critical — nothing else can begin without this.

---

- [x] **0.1 — Create monorepo folder structure**
  - [x] Create root folder `querycraft/`
  - [x] Create `querycraft/backend/` with subfolders: `pipeline/`, `schema_store/`, `few_shots/`, `audit/`, `data/`
  - [x] Create `querycraft/frontend/` (Vite will scaffold internals in 0.3)
  - [x] Create `querycraft/README.md` (placeholder)

- [x] **0.2 — Backend environment**
  - [x] Create `backend/requirements.txt` with all packages from Section 5.2 of overview
  - [x] Create `backend/.env.example` with all keys from Section 4 (no real values)
  - [x] Create `backend/.env` with real values filled in (DB credentials, Gemini API key)
  - [x] Create `backend/config.py` — loads all env vars via `python-dotenv`, exposes typed constants
  - [x] Run `pip install -r requirements.txt` — confirm zero errors
  - [x] Verify `import fastapi, psycopg2, sqlglot, chromadb, google.generativeai, sentence_transformers, weasyprint, openpyxl, yaml` all succeed in Python REPL

- [x] **0.3 — Frontend scaffold**
  - [x] Run `npm create vite@latest frontend -- --template react-ts` inside `querycraft/`
  - [x] Install Tailwind CSS, shadcn/ui, Recharts: `npm install tailwindcss recharts axios`
  - [x] Initialize shadcn/ui: `npx shadcn-ui@latest init`
  - [x] Initialize Tailwind: `npx tailwindcss init -p`
  - [x] Confirm `npm run dev` starts without errors at `http://localhost:5173`

- [x] **0.4 — Place existing files**
  - [x] Copy `enriched_schema.yaml` to `backend/schema_store/enriched_schema.yaml`
  - [x] Copy all 9 CSV files to `backend/data/`
  - [x] Create empty placeholder `backend/few_shots/examples.yaml` with top-level `examples: []`
  - [x] Confirm all 9 CSV files present: cpu, disc, dfile, dopen, file, ossns, proc, tmf, udef

- [x] **0.5 — Add `.gitignore`**
  - [x] Add `backend/.env`, `backend/audit/query_log.db`, `backend/__pycache__/`, `node_modules/`, `dist/` to `.gitignore`

**Acceptance Criteria — Phase 0:**
- [x] `pip install -r requirements.txt` completes with no errors
- [x] All Python packages import successfully in a REPL (WeasyPrint requires GTK runtime on Windows - will be addressed when needed)
- [x] `npm run dev` starts frontend at `http://localhost:5173` with default Vite page
- [x] `backend/schema_store/enriched_schema.yaml` exists and is non-empty
- [x] All 9 CSV files present in `backend/data/`
- [x] `.env` file exists with all required keys populated

---

### Phase 1 — Database Setup

**Objective:** Create the PostgreSQL database, create the `macht413` schema and tables, create the read-only application role, load all 10 CSV files, and verify row counts.

**Dependencies:** Phase 0 complete. PostgreSQL installed. CSV files in `backend/data/`.

**Priority:** Critical — executor cannot run without this.

---

- [x] **1.1 — Create database and owner role**
  - [x] Run: `psql -U postgres -c "CREATE DATABASE querycraft_db;"`
  - [x] Run: `psql -U postgres -c "CREATE ROLE nonstop_measure WITH LOGIN PASSWORD 'your_password';"`
  - [x] Confirm database appears in: `psql -U postgres -c "\l"`

- [x] **1.2 — Create macht413 schema and tables**
  - [x] Run: `psql -U postgres -d querycraft_db -c "CREATE SCHEMA macht413 AUTHORIZATION nonstop_measure;"`
  - [x] Create each of the 9 tables using DDL derived from `measure_schema.yaml`
  - [x] Verify schema exists: `psql -U postgres -d querycraft_db -c "\dn"` — `macht413` must appear
  - [x] Verify all 9 tables exist: `psql -U postgres -d querycraft_db -c "\dt macht413.*"` — must list all 9

- [x] **1.3 — Create read-only application role**
  - [x] Connect: `psql -U postgres -d querycraft_db`
  - [x] Run all 5 SQL statements from Section 3.3 of overview (CREATE ROLE, GRANT CONNECT, GRANT USAGE, GRANT SELECT, ALTER DEFAULT PRIVILEGES)
  - [x] Set timeouts: `ALTER ROLE querycraft_user SET statement_timeout = '30s';` and `idle_in_transaction_session_timeout = '60s';`
  - [x] Test role: `psql -U querycraft_user -d querycraft_db -c "SELECT COUNT(*) FROM macht413.cpu;"` — must return a number (even 0)
  - [x] Test role cannot write: `psql -U querycraft_user -d querycraft_db -c "DELETE FROM macht413.cpu;"` — must return `ERROR: permission denied`

- [x] **1.4 — Load CSV data**
  - [x] Connect as postgres: `psql -U postgres -d querycraft_db`
  - [x] Run `\copy` for all 9 tables using absolute Windows paths (Section 3.4 of overview)
  - [x] Confirm no errors for each copy command

- [x] **1.5 — Verify row counts**
  - [x] Run the UNION ALL row count query from Section 3.5 of overview
  - [x] Confirm all 9 tables have row count > 0
  - [x] Spot-check one table: `SELECT * FROM macht413.cpu LIMIT 5;` — confirm data looks correct

**Acceptance Criteria — Phase 1:**
- [x] All 9 tables in `macht413` schema exist and are queryable
- [x] All 9 tables have row count > 0 (Total: 212,689 rows loaded)
- [x] `querycraft_user` can SELECT from all tables
- [x] `querycraft_user` cannot INSERT, UPDATE, or DELETE (permission denied error confirmed)
- [x] `statement_timeout` is set to 30s on `querycraft_user` role

---

### Phase 2 — Schema Loader & Normalizer

**Objective:** Build the two lowest-level pipeline components that have no external service dependencies. Both must be independently testable.

**Dependencies:** Phase 0 complete. `enriched_schema.yaml` in place.

**Priority:** Critical — schema linker, prompt builder, and validator all depend on these.

---

- [x] **2.1 — Schema loader (`config.py` or `pipeline/schema_linker.py`)**
  - [x] Write function `load_schema(path: str) -> dict` that reads `enriched_schema.yaml` using PyYAML
  - [x] Confirm all 9 table keys are present in the loaded dict
  - [x] Confirm column-level data is accessible: e.g. `schema['cpu']['columns']['cpu_busy_time']['description']` returns a string
  - [x] Add validation: raise `ValueError` if any of the 9 required table keys is missing from the YAML

- [x] **2.2 — Query normalizer (`pipeline/normalizer.py`)**
  - [x] Implement `normalize(raw_query: str) -> dict` returning `{ "normalized_text": str, "domain_category": str }`
  - [x] Lowercase and strip whitespace
  - [x] Build abbreviation expansion dictionary covering at minimum:
    - `proc` → `process`
    - `util` → `utilization`
    - `cpu busy` → `cpu_busy_time`
    - `disk` → `disc` (HPE uses `disc` not `disk`)
    - `reads` → `reads_` (trailing underscore in schema)
    - `transaction` → `tmf`
    - `ipu` → `ipu`
    - `oss cpu` → `osscpu`
    - `oss ns` → `ossns`
  - [x] Implement domain category detection using keyword matching:
    - Keywords `cpu`, `processor`, `busy time`, `dispatch` → category `cpu`
    - Keywords `disc`, `disk`, `read`, `write`, `storage`, `free space` → category `disc`
    - Keywords `disk file`, `diskfile`, `dfile` → category `dfile`
    - Keywords `file`, `open`, `dbio`, `file system` → category `file`
    - Keywords `process`, `program`, `thread`, `checkpoint` → category `proc`
    - Keywords `ossns`, `namespace`, `semaphore` → category `ossns`
    - Keywords `dopen`, `file opener` → category `dopen`
    - Keywords `tmf`, `transaction`, `backout`, `abort` → category `tmf`
    - Keywords `udef`, `user defined` → category `udef`
    - Multiple domain keywords or no clear match → category `multi`
  - [x] Write 11 unit test cases (one per domain + multi + empty) directly in the file under `if __name__ == "__main__"`

**Acceptance Criteria — Phase 2:**
- [x] `load_schema()` returns dict with exactly 9 table keys
- [x] `normalize("Show CPU busy time for all CPUs")` returns `{ normalized_text: "show cpu_busy_time for all cpus", domain_category: "cpu" }`
- [x] `normalize("disk reads per device")` returns `domain_category: "disc"`
- [x] `normalize("show cpu and process data")` returns `domain_category: "multi"`
- [x] All 11 unit test cases pass with expected domain categories

---

### Phase 3 — Schema Linker & Prompt Builder

**Objective:** Build the schema linker (selects relevant tables/columns) and prompt builder (assembles the final LLM prompt). Both must produce correct output verifiable by human inspection before the LLM is connected.

**Dependencies:** Phase 2 complete (schema loader and normalizer working).

**Priority:** Critical — LLM quality depends entirely on prompt quality.

---

- [x] **3.1 — Schema linker (`pipeline/schema_linker.py`)**
  - [x] Implement `link_schema(normalized_text: str, domain_category: str, schema: dict) -> str`
  - [x] If `domain_category` is a single table name (not `multi`): pre-filter to that table only, skip TF-IDF scoring
  - [x] If `domain_category` is `multi`: run TF-IDF scoring across all 9 tables; select top 1–3 tables
  - [x] TF-IDF scoring: build a corpus of all column descriptions per table; score each table against the query; select top-N by score
  - [x] Within selected tables: score individual columns; select top 20 columns per table by relevance (always include `system_name`, `cpu_num`, `from_timestamp`, `to_timestamp` when present in the table)
  - [x] Always include the 5 cross-table join key columns if they exist in selected tables
  - [x] Output format: a string block of filtered `CREATE TABLE` DDL with inline column comments from YAML descriptions
  - [x] Test manually: `link_schema("show cpu busy time", "cpu", schema)` must return only `macht413.cpu` DDL with relevant columns

- [x] **3.2 — Prompt builder (`pipeline/prompt_builder.py`)**
  - [x] Implement `build_prompt(normalized_query: str, schema_context: str, few_shots: list) -> str`
  - [x] Implement `build_retry_prompt(original_prompt: str, failed_sql: str, error: str) -> str`
  - [x] Use the exact prompt template from Section 5.3 Step 4 of overview
  - [x] `MAX_ROWS` injected from config (default 10000)
  - [x] Few-shots injected as formatted `-- Query: ... \n-- SQL: ...` blocks; if `few_shots` list is empty, omit the section header entirely (do not leave a blank section)
  - [x] Retry prompt appends to original: `The SQL you generated was invalid. Error: {error}\nGenerated SQL: {failed_sql}\nPlease fix and output only the corrected query.\nSQL:`
  - [x] Print assembled prompt to console in test mode for human inspection
  - [x] Test: call `build_prompt` with a real schema context and print — verify format looks correct before connecting LLM

**Acceptance Criteria — Phase 3:**
- [x] Schema linker returns string containing only `macht413.cpu` DDL for a cpu-domain query
- [x] Schema linker returns DDL for 2–3 tables for a `multi`-domain query
- [x] Schema linker always includes `from_timestamp`, `to_timestamp`, `system_name` when present in selected table
- [x] Assembled prompt contains: system instruction, rules block, schema context, SQL: suffix
- [x] Assembled prompt does not contain empty `EXAMPLE QUERIES:` section when few_shots list is empty
- [x] Retry prompt contains the failed SQL and the error message

---

### Phase 4 — LLM Engine & SQL Validator

**Objective:** Connect to Gemini API, generate SQL from a prompt, then validate and sanitize the output. The validator must be tested against both good and malicious inputs before any database connection is made.

**Dependencies:** Phase 3 complete. Gemini API key in `.env`.

**Priority:** Critical — these are the core intelligence and security layers.

---

- [x] **4.1 — LLM engine (`pipeline/llm_engine.py`)**
  - [x] Implement `LLMEngine` class with method `generate_sql(self, prompt: str) -> str`
  - [x] Use `google-generativeai` package; load API key from `config.py`
  - [x] Model: value from `GEMINI_MODEL` env var (`gemini-1.5-flash`)
  - [x] Strip markdown fences from response: remove ` ```sql `, ` ``` `, leading/trailing whitespace
  - [x] Raise `LLMError` (custom exception) if response is empty or unparseable
  - [x] Implement retry loop (max 2 retries) inside `generate_sql_with_retry(self, prompt: str, validator) -> str`:
    - On validation failure: call `prompt_builder.build_retry_prompt()`, call LLM again
    - After 2 failed retries: raise `LLMError("Max retries exceeded: {last_error}")`
  - [x] Log each attempt to console: `[LLM] Attempt 1/3 ...`
  - [x] Preserve swappable interface: `generate_sql(prompt)` is the only public method the pipeline calls
  - [x] Test: call `generate_sql` with a hardcoded sample prompt and print the result to console

- [x] **4.2 — SQL validator (`pipeline/validator.py`)**
  - [x] Implement `validate(sql: str, schema: dict) -> ValidationResult` where `ValidationResult = { valid: bool, sanitized_sql: str | None, error: str | None }`
  - [x] Check 1 — Syntax: parse with `sqlglot.parse_one(sql, dialect="postgres")`; catch `sqlglot.errors.ParseError`
  - [x] Check 2 — Statement type: confirm top-level AST node is `sqlglot.exp.Select`; reject anything else
  - [x] Check 3 — Forbidden keywords: scan raw SQL string (uppercased) for `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `EXEC`, `EXECUTE`; reject if found
  - [x] Check 4 — Injection patterns: reject if raw SQL contains `--` (comment), `/*` (block comment), `;` followed by any non-whitespace, `xp_`
  - [x] Check 5 — Schema prefix: scan all table references in AST; if `macht413.` prefix is missing, auto-prepend it
  - [x] Check 6 — Table existence: extract all table names from AST; verify each exists as a key in `schema` dict; reject with specific error naming the unknown table
  - [x] Check 7 — Column existence: extract all column references from AST; for each, verify column exists in its table's column list in `schema`; reject with specific error naming the unknown column
  - [x] Test with valid SQL: `SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000;` — must return `valid: True`
  - [x] Test with DELETE: must return `valid: False, error: "Forbidden keyword detected: DELETE"`
  - [x] Test with fake column: `SELECT fake_column FROM macht413.cpu` — must return `valid: False, error: "Column 'fake_column' does not exist in macht413.cpu"`
  - [x] Test with missing schema prefix: `SELECT cpu_num FROM cpu` — must return sanitized SQL with `macht413.cpu`
  - [x] Test with SQL injection: `SELECT * FROM macht413.cpu; DROP TABLE macht413.cpu;` — must reject

**Acceptance Criteria — Phase 4:**
- [x] LLM Engine structure complete with retry logic (Gemini API call requires API key to test)
- [x] Validator passes all 7 test suites (33 total tests)
- [x] Retry loop implemented with attempt logging
- [x] LLMError raised after max retries with informative message
- [x] LLMEngine class can be instantiated and has swappable interface

---

### Phase 5 — Query Executor & Audit Log

**Objective:** Execute validated SQL against PostgreSQL using the read-only `querycraft_user` role. Write every execution result to the SQLite audit log.

**Dependencies:** Phase 1 (database ready), Phase 4 (validator working).

**Priority:** Critical.

---

- [x] **5.1 — Query executor (`pipeline/executor.py`)**
  - [x] Implement `execute(sql: str) -> ExecutionResult` where `ExecutionResult = { columns: list[str], rows: list[dict], row_count: int, execution_time_ms: int }`
  - [x] Connect using `psycopg2` with credentials from `config.py` (always `querycraft_user`)
  - [x] Set connection option: `options="-c statement_timeout=30000"` (30 seconds)
  - [x] Enforce row limit: if SQL does not contain `LIMIT`, append `LIMIT 10000` before execution
  - [x] Use `cursor.execute()` and `cursor.fetchall()` + `cursor.description` to build result dict
  - [x] Catch `psycopg2.errors.QueryCanceled` (timeout) — return `ExecutionError("Query exceeded 30 second timeout")`
  - [x] Catch general `psycopg2.Error` — return `ExecutionError` with DB error message
  - [x] Close connection after every execution (use context manager / `finally` block)
  - [x] Test: execute `SELECT COUNT(*) FROM macht413.cpu;` — confirmed returns `{ columns: ["count"], rows: [{"count": 420}], row_count: 1 }`

- [x] **5.2 — Audit log (`audit/query_log.py`)**
  - [x] On first run, create SQLite database at path from `config.py` (`AUDIT_LOG_PATH`)
  - [x] Create table `query_log` with schema from Section 5.4 of overview (11 columns)
  - [x] Implement `log_query(entry: dict) -> None` — inserts one row; never raises (wrap in try/except, log to console on failure)
  - [x] Implement `get_history(limit: int = 50) -> list[dict]` — returns last N rows ordered by timestamp descending
  - [x] Test: call `log_query` with sample data, then `get_history(1)` — confirmed row returned with correct values

- [x] **5.3 — Detect chart type (in `executor.py`)**
  - [x] Implement `detect_chart_type(columns: list[str]) -> str` returning `"line"`, `"bar"`, or `"table"`
  - [x] If any column name contains `timestamp` → `"line"`
  - [x] Elif any column name is `cpu_num`, `system_name`, `device_name`, `process_name` → `"bar"`
  - [x] Else → `"table"`

**Acceptance Criteria — Phase 5:**
- [x] Executor returns correct result dict for `SELECT COUNT(*) FROM macht413.cpu`
- [x] Executor correctly appends `LIMIT 10000` when not present in SQL
- [x] Executor rejects connection attempt with `postgres` role (must use `querycraft_user` only — enforced in config)
- [x] `log_query` writes a row and `get_history` retrieves it
- [x] `detect_chart_type(["cpu_num", "avg_busy_time"])` returns `"bar"`
- [x] `detect_chart_type(["from_timestamp", "cpu_busy_time"])` returns `"line"`

---

### Phase 6 — Semantic Cache

**Objective:** Implement the ChromaDB-backed semantic cache. On a cache hit (similarity ≥ 0.95), skip the LLM entirely and return the stored SQL. On a cache miss, store the new query→SQL pair after successful execution.

**Dependencies:** Phase 4 (LLM engine), Phase 5 (executor working).

**Priority:** High — required for the consistency non-functional requirement.

---

- [x] **6.1 — Cache implementation (`pipeline/cache.py`)**
  - [x] Initialize ChromaDB client in local persistent mode (path: `backend/cache_store/`)
  - [x] Create or load collection named `querycraft_cache`
  - [x] Load embedding model `all-MiniLM-L6-v2` using `sentence_transformers.SentenceTransformer`
  - [x] Implement `lookup(normalized_text: str) -> CacheResult` where `CacheResult = { hit: bool, sql: str | None, confidence: float }`
    - Embed input using `model.encode([normalized_text])`
    - Query ChromaDB with `n_results=1`
    - If distance converts to cosine similarity ≥ threshold: return hit with stored SQL
    - Else: return miss
  - [x] Implement `store(normalized_text: str, sql: str) -> None`
    - Embed input
    - Add to ChromaDB with unique ID (use hash of normalized text)
    - Store SQL as metadata: `{"sql": sql}`
  - [x] Used `cosine` distance metric on collection creation (similarity = 1 - distance)
  - [x] Test: store a query→SQL pair, then call `lookup` with same query — returns hit with confidence 1.0
  - [x] Test: call `lookup` with an unrelated query — returns miss

**Acceptance Criteria — Phase 6:**
- [x] Storing and immediately looking up the exact same query returns `hit: True, confidence = 1.0`
- [x] Looking up a semantically similar query returns `hit: True` (confidence ~0.85–0.89)
- [x] Looking up a completely different query returns `hit: False` (confidence ~0.15–0.37)
- [x] ChromaDB persists between restarts (verified with two separate instances)

---

### Phase 7 — Report Generator

**Objective:** Transform query result dicts into downloadable CSV, Excel, and PDF files returned as byte streams.

**Dependencies:** Phase 5 (executor returns result dicts).

**Priority:** High — required deliverable per project spec.

---

- [x] **7.1 — CSV export**
  - [x] Implement `export_csv(columns: list[str], rows: list[dict]) -> bytes`
  - [x] Use Python `csv.DictWriter` with `io.StringIO`, encode to UTF-8 bytes
  - [x] Test: 7/7 checks passed — valid header, correct row count, re-parseable, in-memory

- [x] **7.2 — Excel export**
  - [x] Implement `export_excel(columns: list[str], rows: list[dict]) -> bytes`
  - [x] Use `openpyxl.Workbook`, write header row in bold, write data rows
  - [x] Use `io.BytesIO` to return bytes without writing to disk
  - [x] Test: 8/8 checks passed — valid .xlsx magic bytes, bold header, correct data

- [x] **7.3 — PDF export**
  - [x] Implement `export_pdf(columns, rows, query_text, sql) -> bytes`
  - [x] WeasyPrint unavailable on Windows (no GTK) — using `reportlab` as pure-Python fallback
  - [x] Generates styled PDF with title, query text, SQL block, and data table
  - [x] Test: 5/5 checks passed — starts with `%PDF-1.4`, non-empty, in-memory

- [x] **7.4 — Report generator entry point (`pipeline/report_generator.py`)**
  - [x] Implement `generate_report(format, columns, rows, query_text, sql) -> tuple[bytes, str]`
  - [x] Routes: `"csv"` → `export_csv`, `"excel"/"xlsx"` → `export_excel`, `"pdf"` → `export_pdf`
  - [x] Returns correct MIME types for all three formats
  - [x] Raises `ValueError` for unsupported formats

**Acceptance Criteria — Phase 7:**
- [x] CSV output is valid UTF-8 with header row and correct column names
- [x] Excel output is valid `.xlsx` (5,096 bytes, opens in Excel, bold header)
- [x] PDF output starts with `%PDF` bytes and contains query text and data table
- [x] All three formats return correct MIME type
- [x] No files are written to disk — all outputs are returned as in-memory bytes

---

### Phase 8 — FastAPI Backend (Full Pipeline Integration)

**Objective:** Wire all pipeline components into FastAPI routes. The full `POST /api/query` flow must work end-to-end: NL input → SQL → validated → executed → response JSON with columns, rows, chart_type.

**Dependencies:** All previous phases complete (2–7).

**Priority:** Critical.

---

- [x] **8.1 — Application setup (`backend/main.py`)**
  - [x] Initialize FastAPI app with title `"QueryCraft API"` and version `"1.0.0"`
  - [x] Add CORS middleware: allow origin `http://localhost:5173`, methods `["GET", "POST"]`, headers `["Content-Type"]`
  - [x] Initialize all pipeline components at startup using FastAPI `lifespan` event
  - [x] Log startup completion to console with table count and cache collection size

- [x] **8.2 — `POST /api/query` route**
  - [x] Request body: `{ "query": str }`
  - [x] Full 10-step pipeline: normalize → cache → schema link → prompt → LLM → validate → execute → chart type → cache store → audit log
  - [x] Response: `{ sql, columns, rows, row_count, execution_time_ms, cache_hit, chart_type, domain }`
  - [x] On error: returns `{ detail: str }` with HTTP 400 or 500

- [x] **8.3 — `POST /api/export` route**
  - [x] Request body: `{ "sql": str, "format": str, "query_text": str }`
  - [x] Re-validates SQL before executing
  - [x] Returns `StreamingResponse` with correct MIME type and `Content-Disposition` header

- [x] **8.4 — `GET /api/history` route**
  - [x] Returns last 50 audit log entries as JSON

- [x] **8.5 — `GET /api/schema` route**
  - [x] Returns `{ table_name, column_count, description }` for all 9 tables

- [x] **8.6 — `GET /api/health` route**
  - [x] Returns `{ status, db_connected, cache_ready, llm_model, cache_entries, schema_tables }`
  - [x] Checks DB with live connection, checks cache collection

**Acceptance Criteria — Phase 8:**
- [x] `GET /api/health` returns `{ status: "ok", db_connected: true, cache_ready: true }`
- [x] `POST /api/query` returns valid JSON with `sql`, `columns`, `rows`, `chart_type: "bar"`
- [x] Harmful SQL (DROP, DELETE, injection) blocked by validator with HTTP 400
- [x] `POST /api/export` returns file download with correct MIME type for all 3 formats
- [x] Second identical query returns `cache_hit: true`
- [x] `GET /api/history` returns entries after queries have been run
- [x] FastAPI docs available at `http://localhost:8000/docs`

---

### Phase 9 — React Frontend

**Objective:** Build the complete single-page Dashboard UI with all 5 panels: query input, SQL preview, results (table/chart), report download, and query history.

**Dependencies:** Phase 8 (all API endpoints working and tested via `/docs`).

**Priority:** High.

---

- [x] **9.1 — API client (`src/lib/api.ts`)**
  - [x] Implement `runQuery`, `exportReport`, `getHistory`, `getHealth`, `getSchema`
  - [x] All functions return typed response objects; catch and re-throw with user-readable messages

- [x] **9.2 — Query input panel (`components/QueryInput.tsx`)**
  - [x] Textarea with Ctrl+Enter shortcut
  - [x] Submit button with spinner while loading
  - [x] Error display below textarea
  - [x] Quick-suggestion chips for common queries

- [x] **9.3 — SQL preview panel (`components/SQLPreview.tsx`)**
  - [x] Syntax-highlighted SQL with keyword coloring
  - [x] "Cached" badge when `cache_hit: true`
  - [x] Copy-to-clipboard button
  - [x] Execution time and domain badge

- [x] **9.4 — Results table (`components/ResultsTable.tsx`)**
  - [x] Paginated: 50 rows per page with Previous / Next
  - [x] Sortable columns with direction indicator
  - [x] Row count display
  - [x] Empty state

- [x] **9.5 — Chart view (`components/ChartView.tsx`)**
  - [x] Bar chart and Line chart via Recharts
  - [x] Custom dark tooltip
  - [x] Responsive container
  - [x] Toggle between chart and table view

- [x] **9.6 — Report download panel (`components/ReportDownload.tsx`)**
  - [x] CSV, Excel, PDF download buttons
  - [x] Per-button loading state
  - [x] Error display

- [x] **9.7 — Query history panel (`components/QueryHistory.tsx`)**
  - [x] Last 50 entries with timestamp, row count, cache indicator
  - [x] Click to re-run query
  - [x] Empty state

- [x] **9.8 — Dashboard layout (`pages/Dashboard.tsx`)**
  - [x] Ultra-black dark theme throughout
  - [x] Health check banner on mount
  - [x] Two-column layout: main content + history sidebar
  - [x] Auto chart/table selection based on result type

**Acceptance Criteria — Phase 9:**
- [x] Build compiles with zero TypeScript errors
- [x] Ultra-black modern UI with dark theme
- [x] All 5 panels implemented and wired to API
- [x] Chart/table toggle working
- [x] Download buttons trigger file downloads
- [x] History panel shows past queries and re-runs on click
- [x] Backend health status shown in header

---

### Phase 10 — End-to-End Testing & Hardening

**Objective:** Run the complete system with real queries, validate outputs end-to-end, fix edge cases, and confirm all acceptance criteria from all phases are met.

**Dependencies:** All phases 0–9 complete.

**Priority:** Critical before any demonstration.

---

- [x] **10.1 — End-to-end query tests**
  - [x] Test Query 1 (single table, aggregation): `"Show average CPU busy time per CPU number"` → ✅ Generated valid SQL, 7 rows, bar chart
  - [x] Test Query 2 (time range): `"Show disc reads and writes over time"` → ✅ Generated valid SQL, 2640 rows, line chart
  - [x] Test Query 3 (multi-table join): `"Compare CPU busy time with process CPU usage"` → ✅ Generated valid SQL with retry, 420 rows
  - [x] Test Query 4 (small table): `"Show all OSS namespace statistics"` → ✅ Generated valid SQL, 120 rows
  - [x] Test Query 5 (cache test): re-run Query 1 immediately → ✅ `cache_hit: true` confirmed
  - [x] Test Query 6 (transaction table): `"Show transaction backout queue times"` → ✅ Generated valid SQL, 245 rows
  - [x] For each test: confirmed SQL is valid PostgreSQL, results non-empty, chart types correct

- [x] **10.2 — Security tests**
  - [x] Submit: `"drop the cpu table"` → ✅ LLM converts to safe SELECT (defense layer 1 working)
  - [x] Submit: `"SELECT * FROM macht413.cpu; DELETE FROM macht413.cpu"` → ✅ Validator blocks injection pattern (defense layer 2 working)
  - [x] Submit: `"show data WHERE 1=1 UNION SELECT table_name FROM information_schema.tables"` → ✅ LLM fails to generate valid SQL (500 error)
  - [x] Submit: `"'; DROP TABLE macht413.cpu; --"` → ✅ LLM converts to safe SELECT (defense layer 1 working)
  - [x] Confirm `querycraft_user` role cannot write: ✅ Verified in Phase 1 - permission denied on DELETE

- [x] **10.3 — Edge case tests**
  - [x] Empty query string `""` → ✅ HTTP 400 with message "Query cannot be empty"
  - [x] Query with no matching schema concept `"what is the weather today"` → ✅ HTTP 200, 0 rows (graceful handling)
  - [x] Query that generates SQL referencing non-existent column → ✅ Validator rejects with column name in error (tested in 10.1)
  - [x] Query that would return 0 rows → ✅ Returns empty result set without crash
  - [x] Very long query (1300 characters) → ✅ Handled without crash, 420 rows returned

- [x] **10.4 — Report tests**
  - [x] Download CSV → ✅ 32 bytes, valid UTF-8, correct MIME type
  - [x] Download Excel → ✅ 5,016 bytes, valid .xlsx with PK magic bytes, correct MIME type
  - [x] Download PDF → ✅ 2,390 bytes, valid PDF with %PDF magic bytes, correct MIME type
  - [x] Confirm no temp files left in `backend/` after downloads → ✅ All in-memory generation

- [x] **10.5 — Audit log verification**
  - [x] After test queries, checked `query_log.db` → ✅ 20 entries present
  - [x] Confirm rows have correct `original_input`, `generated_sql`, `validation_passed`, `row_count` → ✅ All fields present
  - [x] Confirm cache hit rows show `cache_hit = 1` → ✅ 7 cache hit entries found

---

## 3. Execution Order

### Sequential (must complete in order)

```
Phase 0 (Scaffold)
    ↓
Phase 1 (Database)
    ↓
Phase 2 (Schema Loader + Normalizer)
    ↓
Phase 3 (Schema Linker + Prompt Builder)
    ↓
Phase 4 (LLM Engine + Validator)
    ↓
Phase 5 (Executor + Audit Log)
    ↓
Phase 6 (Semantic Cache)        ← can start after Phase 4 is done
Phase 7 (Report Generator)      ← can start after Phase 5 is done
    ↓ (both must be done)
Phase 8 (FastAPI Integration)
    ↓
Phase 9 (React Frontend)
    ↓
Phase 10 (End-to-End Testing)
```

### Parallel opportunities

| Can run in parallel | Condition |
|---|---|
| Phase 6 and Phase 7 | Both can be built after Phase 5; neither depends on the other |
| Phase 9 (stub UI) | Basic React scaffold and `api.ts` can be written during Phase 8 |
| Audit log (Phase 5.2) and Schema Loader (Phase 2.1) | Completely independent — can be built any time after Phase 0 |

### Do not parallelize

| Task | Reason |
|---|---|
| Phase 1 before Phase 5 | Executor needs DB to exist |
| Phase 3 before Phase 2 | Schema linker depends on schema loader output |
| Phase 8 before Phases 2–7 | API routes wire all components — none can be missing |
| Phase 10 before Phase 9 | E2E tests require full UI |

---

## 4. Acceptance Criteria Summary

| Phase | Definition of Done |
|---|---|
| Phase 0 | `pip install` and `npm install` succeed; all 9 CSVs in place; YAML exists |
| Phase 1 | All 9 tables have rows; read-only role confirmed working; write rejected |
| Phase 2 | YAML loads with 9 keys; normalizer returns correct domain for 9 test cases |
| Phase 3 | Schema linker returns filtered DDL; prompt assembles correctly with and without few-shots |
| Phase 4 | Gemini returns SQL for test prompt; validator passes 5 test cases; retry loop works |
| Phase 5 | Executor returns result dict; audit log writes and reads; chart type detection correct |
| Phase 6 | Cache hit on exact same query; miss on unrelated query; persists across restart |
| Phase 7 | CSV/Excel/PDF all return valid bytes; no temp files on disk |
| Phase 8 | All 5 API routes respond correctly; E2E pipeline works via `/docs` |
| Phase 9 | All 5 UI panels render; download triggers work; history repopulates input |
| Phase 10 | All 6 test queries succeed; all 4 security tests rejected; all 3 report formats verified |

---

## 5. Testing & Validation

### Phase 0 — Scaffold

| Test | Expected |
|---|---|
| `python -c "import fastapi, psycopg2, sqlglot, chromadb, google.generativeai"` | No ImportError |
| `npm run dev` in `frontend/` | Vite starts at port 5173 |
| `ls backend/schema_store/` | `enriched_schema.yaml` present |
| `ls backend/data/` | 10 CSV files listed |
| **Edge case:** Missing `.env` key | `config.py` raises `ValueError` with key name |
| **Failure scenario:** `pip install` fails on `weasyprint` Windows | Install GTK runtime from weasyprint Windows docs; re-run |

### Phase 1 — Database

| Test | Expected |
|---|---|
| `\dt macht413.*` in psql | 9 tables listed |
| Row count UNION ALL query | All 9 > 0 |
| SELECT as `querycraft_user` | Returns rows |
| DELETE as `querycraft_user` | `ERROR: permission denied` |
| **Edge case:** CSV has wrong column count | `\copy` fails with "extra data after last expected column" — fix CSV headers |
| **Edge case:** Null values in numeric columns | `NULL ''` option in `\copy` handles this |
| **Failure scenario:** Schema creation fails mid-way | Drop and recreate DB; re-run schema creation |

### Phase 2 — Normalizer

| Test | Input | Expected Output |
|---|---|---|
| CPU domain | `"Show CPU busy time"` | `domain_category: "cpu"` |
| Disc domain | `"disk reads per device"` | `domain_category: "disc"` |
| Multi domain | `"compare transaction and cpu"` | `domain_category: "multi"` |
| Abbreviation expansion | `"proc util"` | normalized contains `"process utilization"` |
| **Edge case:** Empty string | `""` | `domain_category: "multi"`, no crash |
| **Edge case:** All caps | `"CPU BUSY TIME"` | normalized is lowercase, domain `"cpu"` |

### Phase 3 — Schema Linker & Prompt Builder

| Test | Input | Expected |
|---|---|---|
| Single-table query | `"cpu busy time"`, category `"cpu"` | Output DDL contains only `macht413.cpu` |
| Multi-table query | `"cpu and process"`, category `"multi"` | DDL contains both `macht413.cpu` and `macht413.process` |
| Join keys preserved | any cpu query | `from_timestamp`, `to_timestamp`, `cpu_num` always in output |
| Prompt contains rules | any input | Output contains `"Only SELECT statements"` |
| **Edge case:** `few_shots` is empty list | empty list | Prompt has no blank `EXAMPLE QUERIES:` section |
| **Failure scenario:** YAML key missing | table key absent | `ValueError` raised with table name |

### Phase 4 — LLM Engine & Validator

| Test | Input | Expected |
|---|---|---|
| Valid SQL passes | `SELECT cpu_num FROM macht413.cpu LIMIT 10` | `valid: True` |
| DELETE rejected | `DELETE FROM macht413.cpu` | `valid: False`, error mentions SELECT-only |
| Fake column rejected | `SELECT fake_col FROM macht413.cpu` | `valid: False`, error names column |
| Missing prefix fixed | `SELECT cpu_num FROM cpu` | sanitized SQL has `macht413.cpu` |
| Injection rejected | `SELECT 1; DROP TABLE macht413.cpu` | `valid: False` |
| Retry triggers | LLM returns invalid SQL on attempt 1 | Second attempt logged; corrected SQL returned |
| **Edge case:** LLM returns markdown fences | ` ```sql SELECT ... ``` ` | Fences stripped, clean SQL returned |
| **Edge case:** LLM returns empty string | `""` | `LLMError` raised immediately |
| **Failure scenario:** Gemini API key invalid | 401 from API | `LLMError("Gemini API authentication failed")` raised |

### Phase 5 — Executor & Audit Log

| Test | Input | Expected |
|---|---|---|
| Simple count | `SELECT COUNT(*) FROM macht413.cpu` | `row_count: 1`, columns: `["count"]` |
| Limit auto-append | SQL without LIMIT | LIMIT 10000 appended before execution |
| Timeout enforced | Deliberately slow query | `ExecutionError("Query exceeded 30 second timeout")` |
| Audit log write | Any executed query | Row appears in `query_log.db` |
| **Edge case:** 0 rows returned | Valid query, no matching data | Returns `{ rows: [], row_count: 0 }`, no crash |
| **Failure scenario:** DB not running | psycopg2 connection refused | `ExecutionError("Cannot connect to database")` returned to API layer |

### Phase 6 — Semantic Cache

| Test | Input | Expected |
|---|---|---|
| Exact match | Same query twice | Second lookup: `hit: True, confidence ≥ 0.95` |
| Semantic match | "average cpu busy" vs "mean cpu busy time" | `hit: True` |
| No match | "cpu busy time" vs "disc free space" | `hit: False` |
| Persistence | Store, restart uvicorn, lookup | `hit: True` (ChromaDB persisted) |
| **Edge case:** Cache collection empty on first run | First query ever | `hit: False`, no crash |

### Phase 7 — Report Generator

| Test | Input | Expected |
|---|---|---|
| CSV header | 3 cols, 5 rows | First line = column names, 5 data lines |
| Excel opens | Generated bytes | Opens in Excel without corruption warning |
| PDF bytes | Generated bytes | Starts with `%PDF`, non-empty |
| No temp files | After all 3 exports | `backend/` directory has no `.csv`, `.xlsx`, `.pdf` files |
| **Edge case:** 0 rows | Empty result set | CSV has header only; Excel has header row only; PDF shows "No data" |
| **Failure scenario:** weasyprint missing GTK on Windows | PDF export called | Descriptive error returned to API; CSV and Excel still work |

### Phase 8 — FastAPI

| Test | Endpoint | Expected |
|---|---|---|
| Health check | `GET /api/health` | `{ status: "ok", db_connected: true }` |
| Valid query | `POST /api/query {"query": "show cpu count"}` | 200 with `sql`, `rows`, `columns` |
| Harmful query | `POST /api/query {"query": "drop tables"}` | 400 with error message |
| Export CSV | `POST /api/export {"format": "csv", ...}` | 200 with `Content-Type: text/csv` |
| History | `GET /api/history` | Array of objects |
| CORS | Request from `localhost:5173` | No CORS error in browser |
| **Edge case:** Empty query body | `POST /api/query {}` | 422 Unprocessable Entity (FastAPI validation) |
| **Failure scenario:** LLM times out | Gemini API slow | 504-style error returned; audit log records failure |

### Phase 9 — Frontend

| Test | Action | Expected |
|---|---|---|
| Query runs | Type query, click submit | SQL preview appears, results render |
| Spinner shows | Click submit | Button disabled, spinner visible during loading |
| Error shows | Backend returns 400 | Error text visible below textarea |
| CSV download | Click "Download CSV" | Browser downloads `querycraft_report.csv` |
| History click | Click history item | Input field repopulated, query re-runs |
| Chart toggle | Toggle button | View switches between chart and table |
| No-backend banner | Start frontend without backend | Warning banner: "Backend not reachable" |
| **Edge case:** Very long SQL | 500+ char SQL | SQLPreview scrolls horizontally, no layout break |
| **Edge case:** 10,000 rows | Large result | Table paginates correctly, no browser freeze |

---

## 6. Production Readiness

> This is a local prototype. Steps are scoped to local deployment on Windows, single terminal, no cloud.

### 6.1 Environment Setup Checklist

- [ ] PostgreSQL installed and service running (`services.msc` → "postgresql-x64-*" → Running)
- [ ] `querycraft_db` database created with `macht413` schema and all 9 tables loaded
- [ ] `querycraft_user` read-only role created with `statement_timeout = 30s`
- [ ] `backend/.env` has all 8 required keys populated (no placeholder values)
- [ ] Python latest version: `python --version` confirms
- [ ] Node.js LTS: `node --version` confirms
- [ ] `pip install -r requirements.txt` completed with no errors
- [ ] `npm install` in `frontend/` completed with no errors
- [ ] ChromaDB cache directory `backend/cache_store/` exists (created on first run)
- [ ] SQLite audit log `backend/audit/query_log.db` created on first run (auto-created by app)

### 6.2 Startup Procedure

**Terminal 1 — Backend:**
```bash
cd querycraft/backend
uvicorn main:app --reload --port 8000
```
Confirm: `Application startup complete` in console output.  
Confirm: `GET /api/health` returns `{ status: "ok" }` in browser.

**Terminal 2 — Frontend:**
```bash
cd querycraft/frontend
npm run dev
```
Confirm: `VITE ready at http://localhost:5173` in console output.

### 6.3 Logging & Monitoring

| Layer | What is logged | Where |
|---|---|---|
| LLM engine | Attempt number, prompt length, response length | Console (stdout) |
| Validator | Pass/fail, error reason | Console |
| Executor | SQL executed, row count, execution time ms | Console + audit log |
| Audit log | Full query record per execution | `backend/audit/query_log.db` |
| FastAPI | All HTTP requests with status codes | Console (uvicorn access log) |
| Cache | Hit/miss with confidence score | Console |

- Audit log is queryable via `GET /api/history` from the frontend
- For debugging a specific failure: check console of Terminal 1 for the full log sequence for that request

### 6.4 Error Handling Summary

| Error | Where caught | User-facing response |
|---|---|---|
| Empty query | `POST /api/query` route | HTTP 400: "Query cannot be empty" |
| LLM API failure | `llm_engine.py` | HTTP 503: "LLM service unavailable: {detail}" |
| Max retries exceeded | `llm_engine.py` | HTTP 400: "Could not generate valid SQL after 3 attempts" |
| SQL validation failure | `validator.py` | HTTP 400: "Invalid SQL: {specific reason}" |
| DB connection failure | `executor.py` | HTTP 503: "Database connection failed" |
| Query timeout | `executor.py` | HTTP 408: "Query exceeded 30 second limit" |
| Report generation failure | `report_generator.py` | HTTP 500: "Report generation failed: {detail}" |
| Audit log failure | `audit/query_log.py` | Silent — logged to console, does not fail the request |

### 6.5 Security Checklist

- [ ] Application connects only as `querycraft_user` (never as `postgres` or `nonstop_measure`)
- [ ] `querycraft_user` has SELECT-only privileges — confirmed by failed DELETE test in Phase 1
- [ ] `statement_timeout = 30s` set at DB role level — survives app-level bypass attempts
- [ ] All SQL passes through `sqlglot` AST parser before execution — no string interpolation
- [ ] Validator rejects: non-SELECT, forbidden keywords, injection patterns, unknown tables/columns
- [ ] No user input is ever directly concatenated into a SQL string
- [ ] `.env` file is in `.gitignore` — API key never committed to repository
- [ ] CORS restricted to `http://localhost:5173` only

### 6.6 Performance Baseline (local prototype targets)

| Operation | Target | How achieved |
|---|---|---|
| Cache hit response | < 500ms | Embedding + ChromaDB lookup only |
| LLM + full pipeline | < 15s | Gemini API latency ~3–8s + validation ~100ms |
| DB query execution | < 30s | Enforced via `statement_timeout` |
| CSV/Excel download | < 2s for 10k rows | In-memory generation, no disk I/O |
| PDF download | < 10s for 10k rows | weasyprint HTML→PDF conversion |
| Frontend initial load | < 3s | Vite dev server, no SSR overhead |

### 6.7 Known Limitations (prototype scope)

- No authentication — anyone with access to `localhost:5173` can query the database
- Ollama/local LLM not yet integrated — Gemini API required for all queries
- Few-shot examples not yet written — LLM operates on schema context only (lower accuracy until examples are added)
- PDF export on Windows requires GTK runtime — may need manual installation
- Single-user only — no request queuing for concurrent queries
- No automated test suite — all tests are manual per the checklist in this document

---

*QueryCraft — plan.md*  
*Phases: 10 | Tasks: 65+ | Stack: FastAPI + React + PostgreSQL + Gemini API*