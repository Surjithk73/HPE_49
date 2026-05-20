# QueryCraft — Project Overview

> Natural Language to SQL Performance Report Generator for HPE NonStop Systems

---

## 1. Project Summary

**Name:** QueryCraft  
**Purpose:** Allow analysts to query HPE NonStop server performance data using plain English. System interprets query, generates SQL, executes against PostgreSQL, and returns structured reports.  
**Database Schema:** `macht413` — 9 tables (cpu, disc, dfile, dopen, file, ossns, proc, tmf, udef), static historical data.  
**Data Source:** Real HPE NonStop measurement data.

---

## 2. Monorepo Structure

```
querycraft/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── .env
│   ├── requirements.txt
│   ├── pipeline/
│   │   ├── normalizer.py
│   │   ├── cache.py
│   │   ├── schema_linker.py
│   │   ├── prompt_builder.py
│   │   ├── llm_engine.py
│   │   ├── validator.py
│   │   ├── executor.py
│   │   └── report_generator.py
│   ├── schema_store/
│   │   └── enriched_schema.yaml        # Combined YAML, all 9 tables, 883 lines
│   ├── few_shots/
│   │   └── examples.yaml               # To be added later
│   ├── audit/
│   │   └── query_log.db                # SQLite audit log
│   └── data/
│       ├── cpu.csv
│       ├── disc.csv
│       ├── disc_cache.csv
│       ├── endpoint.csv
│       ├── file.csv
│       ├── ipu.csv
│       ├── osscpu.csv
│       ├── ossns.csv
│       ├── process.csv
│       └── tmf.csv
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── QueryInput.tsx
│   │   │   ├── ResultsTable.tsx
│   │   │   ├── ChartView.tsx
│   │   │   ├── QueryHistory.tsx
│   │   │   ├── SQLPreview.tsx
│   │   │   └── ReportDownload.tsx
│   │   ├── pages/
│   │   │   └── Dashboard.tsx
│   │   └── lib/
│   │       └── api.ts
└── README.md
```

---

## 3. Database Setup

### 3.1 PostgreSQL Version
Use latest stable PostgreSQL. Install locally on Windows.

### 3.2 Restore Schema

The `macht413` schema and all 9 tables are created by loading the CSV files from the `measurefiles/` folder. Each CSV file corresponds to one table. Run the steps below to set up the database before loading data.

```bash
# Step 1: Create database
psql -U postgres -c "CREATE DATABASE querycraft_db;"

# Step 2: Create schema owner role
psql -U postgres -c "CREATE ROLE nonstop_measure WITH LOGIN PASSWORD 'your_password';"

# Step 3: Create the macht413 schema
psql -U postgres -d querycraft_db -c "CREATE SCHEMA macht413 AUTHORIZATION nonstop_measure;"
```

### 3.3 Create Read-Only Application Role

```sql
-- Run in psql connected to querycraft_db
CREATE ROLE querycraft_user WITH LOGIN PASSWORD 'your_readonly_password';
GRANT CONNECT ON DATABASE querycraft_db TO querycraft_user;
GRANT USAGE ON SCHEMA macht413 TO querycraft_user;
GRANT SELECT ON ALL TABLES IN SCHEMA macht413 TO querycraft_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA macht413 GRANT SELECT ON TABLES TO querycraft_user;

-- Set safety limits on connection
ALTER ROLE querycraft_user SET statement_timeout = '30s';
ALTER ROLE querycraft_user SET idle_in_transaction_session_timeout = '60s';
```

### 3.4 Load CSV Data

Each CSV file corresponds to one table. Load using psql `\copy`:

```bash
psql -U postgres -d querycraft_db
```

Then inside psql, run for each table:

```sql
\copy macht413.cpu FROM 'C:/path/to/querycraft/backend/data/cpu.csv' WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.disc FROM 'C:/path/to/querycraft/backend/data/disc.csv' WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.disc_cache FROM 'C:/path/to/querycraft/backend/data/disc_cache.csv' WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.endpoint FROM 'C:/path/to/querycraft/backend/data/endpoint.csv' WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.file FROM 'C:/path/to/querycraft/backend/data/file.csv' WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.ipu FROM 'C:/path/to/querycraft/backend/data/ipu.csv' WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.osscpu FROM 'C:/path/to/querycraft/backend/data/osscpu.csv' WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.ossns FROM 'C:/path/to/querycraft/backend/data/ossns.csv' WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.process FROM 'C:/path/to/querycraft/backend/data/process.csv' WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.tmf FROM 'C:/path/to/querycraft/backend/data/tmf.csv' WITH (FORMAT csv, HEADER true, NULL '');
```

### 3.5 Verify

```sql
SELECT table_name, COUNT(*) 
FROM information_schema.tables t
JOIN macht413.cpu ON true  -- replace with each table to spot-check row counts
WHERE table_schema = 'macht413'
GROUP BY table_name;

-- Quick row count check per table:
SELECT 'cpu' AS tbl, COUNT(*) FROM macht413.cpu
UNION ALL SELECT 'disc', COUNT(*) FROM macht413.disc
UNION ALL SELECT 'disc_cache', COUNT(*) FROM macht413.disc_cache
UNION ALL SELECT 'endpoint', COUNT(*) FROM macht413.endpoint
UNION ALL SELECT 'file', COUNT(*) FROM macht413.file
UNION ALL SELECT 'ipu', COUNT(*) FROM macht413.ipu
UNION ALL SELECT 'osscpu', COUNT(*) FROM macht413.osscpu
UNION ALL SELECT 'ossns', COUNT(*) FROM macht413.ossns
UNION ALL SELECT 'process', COUNT(*) FROM macht413.process
UNION ALL SELECT 'tmf', COUNT(*) FROM macht413.tmf;
```

---

## 4. Environment Variables

### `backend/.env`

```env
# PostgreSQL (read-only app user)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=querycraft_db
DB_USER=querycraft_user
DB_PASSWORD=your_readonly_password

# Gemini API
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.1-flash-lite

# App settings
MAX_ROWS=10000
QUERY_TIMEOUT_SECONDS=30
CACHE_SIMILARITY_THRESHOLD=0.95
AUDIT_LOG_PATH=audit/query_log.db
SCHEMA_YAML_PATH=schema_store/enriched_schema.yaml
FEW_SHOTS_PATH=few_shots/examples.yaml
```

---

## 5. Backend

### 5.1 Tech Stack

| Concern | Library |
|---|---|
| API framework | FastAPI |
| PostgreSQL driver | psycopg2 |
| SQL parsing + validation | sqlglot |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| Vector cache | chromadb |
| LLM | Gemini API (google-generativeai) |
| PDF export | weasyprint |
| Excel export | openpyxl |
| CSV export | Python standard library |
| Audit log | SQLite via sqlite3 |
| Config | python-dotenv |
| YAML parsing | PyYAML |

### 5.2 `requirements.txt`

```
fastapi
uvicorn[standard]
psycopg2-binary
sqlglot
sentence-transformers
chromadb
google-generativeai
weasyprint
openpyxl
python-dotenv
pyyaml
pandas
```

### 5.3 Pipeline — Step by Step

#### Step 1 — Query Normalizer (`pipeline/normalizer.py`)

- Input: raw user text string
- Actions:
  - Lowercase entire string
  - Strip leading/trailing whitespace
  - Expand HPE-specific abbreviations (e.g. `proc` → `process`, `util` → `utilization`, `cpu busy` → `cpu_busy_time`)
  - Detect domain category: one of `cpu`, `disc`, `file`, `process`, `ipu`, `osscpu`, `ossns`, `endpoint`, `tmf`, `disc_cache`, or `multi`
- Output: `{ normalized_text: str, domain_category: str }`

#### Step 2 — Semantic Cache (`pipeline/cache.py`)

- Backed by ChromaDB collection named `querycraft_cache`
- Embedding model: `all-MiniLM-L6-v2` via sentence-transformers
- On each query:
  - Embed normalized text
  - Query ChromaDB for nearest neighbor
  - If cosine similarity ≥ 0.95: return cached SQL (cache hit)
  - Else: return cache miss
- Cache write happens after successful query execution (background)
- Input: normalized text string
- Output: `{ hit: bool, sql: str | None, confidence: float }`

#### Step 3 — Schema Linker (`pipeline/schema_linker.py`)

- Runs only on cache miss
- Loads `enriched_schema.yaml`
- Uses domain category from normalizer to pre-filter candidate tables
- Scores each table's column descriptions against the query using TF-IDF + keyword overlap
- Selects top 1–3 tables and top relevant columns per table
- Returns filtered schema context as a formatted string (subset CREATE TABLE DDL + column descriptions)
- Input: normalized text, domain category, enriched schema
- Output: filtered schema context string

#### Step 4 — Prompt Builder (`pipeline/prompt_builder.py`)

Assembles final LLM prompt using this fixed template:

```
You are a SQL expert for HPE NonStop performance monitoring systems.
Generate a single valid PostgreSQL SELECT query for the schema 'macht413'.

STRICT RULES:
- Output ONLY the raw SQL query. No explanation, no markdown, no backticks.
- Only SELECT statements. No INSERT, UPDATE, DELETE, DROP, ALTER, or any DDL.
- Always qualify table names: macht413.table_name
- Only use columns listed in the schema context below.
- Use from_timestamp and to_timestamp for any time-based filtering.
- Always include LIMIT {MAX_ROWS} unless a smaller limit is specified.

SCHEMA CONTEXT:
{filtered_schema_context}

EXAMPLE QUERIES:
{few_shot_examples}

USER REQUEST:
{normalized_query}

SQL:
```

- Input: filtered schema context, few-shot examples, normalized query
- Output: assembled prompt string

#### Step 5 — LLM Engine (`pipeline/llm_engine.py`)

- Uses `google-generativeai` Python package
- Model: value from `GEMINI_MODEL` env var (`gemini-3.1-flash-lite`)
- Sends assembled prompt
- Extracts only the SQL text from response (strip markdown fences if present)
- Future: swap to Ollama by changing this file only — all other pipeline unchanged
- Input: prompt string
- Output: raw SQL string from model

#### Step 6 — SQL Validator + Security Guard (`pipeline/validator.py`)

Uses `sqlglot` to parse and validate. Enforces:

1. Valid SQL syntax (sqlglot parse succeeds)
2. Top-level statement is SELECT only
3. No semicolons that chain statements
4. No forbidden keywords: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `EXEC`, `EXECUTE`
5. No SQL injection patterns: `--`, `/*`, `xp_`, `UNION` (unless in valid subquery context)
6. All referenced table names exist in `macht413` schema
7. All referenced column names exist in their respective tables
8. `macht413.` schema prefix present on all table references (auto-prepend if missing)

- Input: raw SQL string from LLM, enriched schema (for column existence check)
- Output: `{ valid: bool, sanitized_sql: str | None, error: str | None }`

#### Step 7 — Error Recovery (inside `pipeline/llm_engine.py`)

If validator returns invalid:

- Max 2 retry attempts
- Retry prompt appends to original:
  ```
  The SQL you generated was invalid. Error: {error_message}
  Generated SQL: {failed_sql}
  Please fix the SQL and output only the corrected query.
  SQL:
  ```
- After 2 failed retries: return user-facing error message
- Input: original prompt, failed SQL, error description
- Output: corrected SQL or final failure

#### Step 8 — Query Executor (`pipeline/executor.py`)

- Connects as `querycraft_user` (read-only role)
- Connection string from `.env`
- Sets `options="-c statement_timeout=30000"` on connection
- Enforces `LIMIT {MAX_ROWS}` at executor level (appends if missing)
- Returns result as list of dicts
- Writes to audit log after every execution (success or failure)
- Input: validated SQL string
- Output: `{ columns: list[str], rows: list[dict], row_count: int, execution_time_ms: int }`

#### Step 9 — Report Generator (`pipeline/report_generator.py`)

Three export modes triggered by user choice:

| Format | Library | Notes |
|---|---|---|
| CSV | Python `csv` | Direct from result rows |
| Excel | `openpyxl` | Formatted table with header row |
| PDF | `weasyprint` | HTML template → PDF, includes chart image if applicable |

Chart generation (for UI and PDF):
- Line chart: when results contain timestamp column (`from_timestamp` or `to_timestamp`)
- Bar chart: when results contain a grouping column (`cpu_num`, `system_name`, `device_name`)
- Default: plain table
- Chart images generated server-side using `matplotlib`, embedded in PDF

- Input: query result dict, requested format, query metadata
- Output: file bytes (returned as FastAPI `StreamingResponse` for download)

### 5.4 Audit Log (`audit/query_log.db`)

SQLite table schema:

```sql
CREATE TABLE query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    original_input TEXT NOT NULL,
    normalized_input TEXT NOT NULL,
    domain_category TEXT,
    generated_sql TEXT,
    validation_passed INTEGER,
    validation_error TEXT,
    cache_hit INTEGER,
    row_count INTEGER,
    execution_time_ms INTEGER,
    export_format TEXT
);
```

### 5.5 API Endpoints (`main.py`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/query` | Main pipeline — NL → SQL → results |
| `GET` | `/api/history` | Returns last 50 audit log entries |
| `POST` | `/api/export` | Download report (CSV / Excel / PDF) |
| `GET` | `/api/schema` | Returns table names and column counts |
| `GET` | `/api/health` | Health check |

#### `POST /api/query` Request Body

```json
{
  "query": "Show average CPU busy time per CPU for all measurements"
}
```

#### `POST /api/query` Response

```json
{
  "sql": "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000",
  "columns": ["cpu_num", "avg"],
  "rows": [...],
  "row_count": 16,
  "execution_time_ms": 142,
  "cache_hit": false,
  "chart_type": "bar"
}
```

#### `POST /api/export` Request Body

```json
{
  "sql": "SELECT ...",
  "format": "excel"
}
```

---

## 6. Frontend

### 6.1 Tech Stack

| Concern | Library |
|---|---|
| Framework | React + Vite |
| Language | TypeScript |
| Styling | Tailwind CSS |
| Components | shadcn/ui |
| Charts | Recharts |
| HTTP client | fetch (native) or axios |
| State | React useState / useEffect |

### 6.2 Pages and Components

**Single-page app (`Dashboard.tsx`)** with these sections:

#### Query Input Panel
- Large textarea for natural language input
- Submit button
- Loading spinner during API call
- Error display on failure

#### SQL Preview Panel
- Displays generated SQL after query runs
- Syntax-highlighted code block (read-only)
- Shown below query input

#### Results Panel
- Auto-selects chart or table based on `chart_type` from API response
- **Table view**: paginated, sortable columns
- **Line chart**: timestamp on X axis, metric on Y axis (Recharts `LineChart`)
- **Bar chart**: category on X axis, value on Y axis (Recharts `BarChart`)
- Toggle between chart and table view

#### Report Download Panel
- Three buttons: Download CSV, Download Excel, Download PDF
- Calls `/api/export` with current SQL + selected format
- Triggers browser file download

#### Query History Panel
- Sidebar or bottom panel
- Shows last 50 queries from `/api/history`
- Click to re-run a past query
- Shows timestamp, truncated query text, row count

### 6.3 API Integration (`src/lib/api.ts`)

```typescript
const API_BASE = 'http://localhost:8000';

export async function runQuery(query: string) {
  const res = await fetch(`${API_BASE}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
  });
  return res.json();
}

export async function exportReport(sql: string, format: 'csv' | 'excel' | 'pdf') {
  const res = await fetch(`${API_BASE}/api/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sql, format })
  });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `querycraft_report.${format === 'excel' ? 'xlsx' : format}`;
  a.click();
}

export async function getHistory() {
  const res = await fetch(`${API_BASE}/api/history`);
  return res.json();
}
```

---

## 7. Enriched Schema Store

**File:** `backend/schema_store/enriched_schema.yaml`  
**Format:** Combined YAML, all 9 tables. Already written (883 lines).

Schema linker reads this file to:
1. Match user query domain to relevant tables
2. Extract column descriptions for prompt context
3. Validate column names in SQL validator

Tables covered:
- `macht413.cpu` — 134 columns — CPU utilization, busy times, memory, network stats
- `macht413.disc` — 58 columns — Disk I/O, requests, free space, queue times
- `macht413.disc_cache` — 18 columns — Disk cache hits, misses, dirty blocks
- `macht413.endpoint` — 38 columns — Network endpoint I/O and retries
- `macht413.file` — 68 columns — File opens, reads/writes, DBIO, cache stats
- `macht413.ipu` — 8 columns — IPU busy time and dispatches
- `macht413.osscpu` — 162 columns — OSS filesystem cache, buffers, proxy stats
- `macht413.ossns` — 38 columns — OSS namespace, checkpoints, semaphores
- `macht413.process` — 148 columns — Per-process CPU, memory, I/O, threads
- `macht413.tmf` — 28 columns — Transaction stats and backouts

### Cross-Table Join Keys

All major tables share these common columns for joining:

| Column | Purpose |
|---|---|
| `system_name` | Identifies the NonStop server instance |
| `cpu_num` | Links cpu, process, ipu, and per-CPU tables |
| `from_timestamp` | Start of measurement interval |
| `to_timestamp` | End of measurement interval |
| `u_loadid_loadid` | Measurement session identifier |

Example cross-table join:
```sql
SELECT c.cpu_num, c.cpu_busy_time, p.process_name, p.cpu_busy_time AS proc_cpu
FROM macht413.cpu c
JOIN macht413.process p
  ON c.system_name = p.system_name
  AND c.cpu_num = p.cpu_num
  AND c.from_timestamp = p.from_timestamp
LIMIT 10000;
```

---

## 8. Few-Shot Examples

**File:** `backend/few_shots/examples.yaml`  
**Status:** To be provided separately. Placeholder file must exist at startup.

Format when populated:

```yaml
examples:
  - domain: cpu
    query: "Show average CPU busy time per CPU"
    sql: "SELECT cpu_num, AVG(cpu_busy_time) AS avg_busy_time FROM macht413.cpu GROUP BY cpu_num ORDER BY cpu_num LIMIT 10000;"

  - domain: disc
    query: "Show disk read and write counts per device"
    sql: "SELECT device_name, SUM(reads_) AS total_reads, SUM(writes) AS total_writes FROM macht413.disc GROUP BY device_name ORDER BY total_reads DESC LIMIT 10000;"
```

---

## 9. LLM Engine — Gemini API

**Current model:** `gemini-3.1-flash-lite`  
**Package:** `google-generativeai`  
**Future replacement:** Ollama with local SQLCoder model — swap `pipeline/llm_engine.py` only.

LLM engine interface contract (must be preserved when switching):

```python
class LLMEngine:
    def generate_sql(self, prompt: str) -> str:
        # Returns raw SQL string or raises LLMError
        ...
```

---

## 10. Running the Project

### Terminal 1 — Backend

```bash
cd querycraft/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Terminal 2 — Frontend

```bash
cd querycraft/frontend
npm install
npm run dev
```

Frontend runs at: `http://localhost:5173`  
Backend runs at: `http://localhost:8000`  
API docs at: `http://localhost:8000/docs`

---

## 11. Build Order for AI IDE

Build components strictly in this order. Do not proceed to next step until current step is verified working.

1. **Project scaffold** — monorepo folder structure, `requirements.txt`, `package.json`, `.env.example`
2. **Database setup** — restore schema, create roles, load CSVs (follow Section 3 exactly)
3. **Enriched schema loader** — load and parse `enriched_schema.yaml` in Python, verify all 9 tables accessible
4. **Query normalizer** — standalone, unit-testable, no external dependencies
5. **Schema linker** — reads YAML, scores tables/columns against query, returns filtered context
6. **Prompt builder** — assembles prompt from parts, verify output looks correct manually
7. **LLM engine** — Gemini API call, verify SQL comes back for sample prompt
8. **SQL validator** — sqlglot-based, test with good and bad SQL inputs
9. **Query executor** — psycopg2, read-only connection, test with hardcoded SELECT
10. **Semantic cache** — ChromaDB setup, embed + store + retrieve test
11. **Audit log** — SQLite setup, verify writes after executor runs
12. **Report generator** — CSV first, then Excel, then PDF
13. **FastAPI routes** — wire all pipeline components into `/api/query` and `/api/export`
14. **React frontend** — scaffold, then QueryInput → ResultsTable → ChartView → QueryHistory → ReportDownload
15. **End-to-end test** — full query from UI to downloaded report

---

## 12. Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| LLM | Gemini API (swappable) | Available now; Ollama later |
| SQL validation | sqlglot AST parsing | Reliable, not regex-based |
| Cache | ChromaDB + sentence-transformers | Zero-config, local |
| DB connection | Read-only role only | Security requirement |
| Prompt | Fixed template in file | Tunable without code change |
| Schema context | Filtered per query | Avoids context window overflow |
| Retry logic | Max 2 retries with error feedback | Handles LLM SQL errors |
| Audit | SQLite separate from main DB | Keeps concerns isolated |
| Report download | StreamingResponse (FastAPI) | No temp files on server |
| Chart type | Auto-detected from result columns | Better UX, no user choice needed |

---

## 13. Security Rules (Non-Negotiable)

- App **never** connects as `nonstop_measure` or `postgres` owner roles
- Only `querycraft_user` (SELECT-only) used at runtime
- Validator rejects anything that is not a top-level SELECT
- `statement_timeout = 30s` enforced at DB role level
- No raw user input ever reaches the database directly
- All SQL passes through sqlglot parser before execution
- Max 10,000 rows enforced at executor level

---

*QueryCraft — HPE NonStop Performance Report Generator*  
*Schema: macht413 | Tables: 10 | LLM: Gemini API | Stack: FastAPI + React*