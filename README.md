# QueryCraft

> Natural Language to SQL Performance Report Generator for HPE NonStop Systems

QueryCraft lets analysts query HPE NonStop server performance data using plain English. Type a question, get back a SQL query, results table or chart, and a downloadable report — no SQL knowledge required.

**Stack:** FastAPI · React · PostgreSQL · Google Gemini API · ChromaDB  
**Database:** `macht413` schema · 11 tables · 212,689+ rows of real HPE NonStop measurement data

---

## Prerequisites

Install these before anything else:

| Tool | Version | Notes |
|------|---------|-------|
| PostgreSQL | Latest stable | Must be running locally on port 5432 |
| Python | 3.10+ | |
| Node.js | 18+ LTS | |
| Git | Any | |

You also need a **Google Gemini API key** — get one free at https://aistudio.google.com/app/apikey

---

## Step 1 — Clone the repo

```bash
git clone https://github.com/Surjithk73/HPE_49.git
cd HPE_49
```

---

## Step 2 — Set up the PostgreSQL database

### 2.1 Create the database, schema, and roles

Connect to PostgreSQL as the superuser and run:

```sql
-- Create database
CREATE DATABASE querycraft_db;

-- Create schema owner role
CREATE ROLE nonstop_measure WITH LOGIN PASSWORD 'your_owner_password';

-- Connect to the new database, then run:
\c querycraft_db

-- Create schema
CREATE SCHEMA macht413 AUTHORIZATION nonstop_measure;

-- Create read-only app role
CREATE ROLE querycraft_user WITH LOGIN PASSWORD 'your_readonly_password';
GRANT CONNECT ON DATABASE querycraft_db TO querycraft_user;
GRANT USAGE ON SCHEMA macht413 TO querycraft_user;
GRANT SELECT ON ALL TABLES IN SCHEMA macht413 TO querycraft_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA macht413 GRANT SELECT ON TABLES TO querycraft_user;

-- Set safety timeouts
ALTER ROLE querycraft_user SET statement_timeout = '30s';
ALTER ROLE querycraft_user SET idle_in_transaction_session_timeout = '60s';
```

Or use the automated script (fill in your postgres password first):

```bash
# Edit POSTGRES_PASSWORD, OWNER_PASSWORD, READONLY_PASSWORD in the script first
python backend/setup_scripts/setup_database_auto.py
```

### 2.2 Create the tables

```bash
psql -U postgres -d querycraft_db -f backend/setup_scripts/create_tables.sql
```

All column types are correctly defined in this file — no post-load fixes required.

### 2.3 Load the CSV data

```bash
# Edit POSTGRES_PASSWORD in the script first, then:
python backend/setup_scripts/load_csv_data_auto.py
```

Or manually via psql (update the paths to match your system):

```sql
\copy macht413.cpu   FROM 'C:/path/to/HPE_49/measurefiles/cpucsv'   WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.disc  FROM 'C:/path/to/HPE_49/measurefiles/disccsv'  WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.dfile FROM 'C:/path/to/HPE_49/measurefiles/dfilecsv' WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.dopen FROM 'C:/path/to/HPE_49/measurefiles/dopencsv' WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.file  FROM 'C:/path/to/HPE_49/measurefiles/filecsv'  WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.ossns FROM 'C:/path/to/HPE_49/measurefiles/ossnscsv' WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.proc  FROM 'C:/path/to/HPE_49/measurefiles/proccsv'  WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.tmf   FROM 'C:/path/to/HPE_49/measurefiles/tmfcsv'   WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.udef  FROM 'C:/path/to/HPE_49/measurefiles/udefcsv'  WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.sqlp  FROM 'C:/path/to/HPE_49/backend/data/D2/sqlpcsv'  WITH (FORMAT csv, HEADER true, NULL '');
\copy macht413.sqls  FROM 'C:/path/to/HPE_49/backend/data/D2/sqlscsv'  WITH (FORMAT csv, HEADER true, NULL '');
```

### 2.4 Verify

```sql
SELECT 'cpu'   AS tbl, COUNT(*) FROM macht413.cpu
UNION ALL SELECT 'disc',  COUNT(*) FROM macht413.disc
UNION ALL SELECT 'dfile', COUNT(*) FROM macht413.dfile
UNION ALL SELECT 'dopen', COUNT(*) FROM macht413.dopen
UNION ALL SELECT 'file',  COUNT(*) FROM macht413.file
UNION ALL SELECT 'ossns', COUNT(*) FROM macht413.ossns
UNION ALL SELECT 'proc',  COUNT(*) FROM macht413.proc
UNION ALL SELECT 'tmf',   COUNT(*) FROM macht413.tmf
UNION ALL SELECT 'udef',  COUNT(*) FROM macht413.udef;
```

Expected total: **212,689 rows** across all 9 tables.

---

## Step 3 — Configure the backend

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and fill in your values:

```env
# PostgreSQL — use the read-only role created in Step 2
DB_HOST=localhost
DB_PORT=5432
DB_NAME=querycraft_db
DB_USER=querycraft_user
DB_PASSWORD=your_readonly_password

# Gemini API — get key from https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash

# App settings (defaults are fine)
MAX_ROWS=10000
QUERY_TIMEOUT_SECONDS=30
CACHE_SIMILARITY_THRESHOLD=0.95
AUDIT_LOG_PATH=audit/query_log.db
SCHEMA_YAML_PATH=schema_store/enriched_schema.yaml
FEW_SHOTS_PATH=few_shots/examples.yaml
```

---

## Step 4 — Install dependencies

**Backend:**
```bash
cd backend
pip install -r requirements.txt
```

> First run will download the `BAAI/bge-large-en-v1.5` embedding model (~1.3GB) from HuggingFace. This only happens once — it's cached locally after that. The API is available immediately while the model loads in the background.

**Frontend:**
```bash
cd frontend
npm install
```

---

## Step 5 — Run the system

Open two terminals:

**Terminal 1 — Backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API is available within ~1 second. The embedding model loads in the background — cache hits are available once `[Cache] Embedding model ready` appears in the terminal (usually within 15 seconds).

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

**Open:** http://localhost:5173

---

## Step 6 — Verify everything is working

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "ok",
  "db_connected": true,
  "cache_ready": true,
  "cache_model_ready": true,
  "llm_model": "gemini-2.0-flash",
  "cache_entries": 0,
  "schema_tables": 9
}
```

If `db_connected` is `false`, check your `.env` credentials and that PostgreSQL is running.  
If `cache_model_ready` is `false`, the embedding model is still loading — wait a few seconds and retry.

---

## Using QueryCraft

### Example queries to try

**Simple:**
- `Show average CPU busy time per CPU`
- `Show disk read and write counts per device`
- `List all process names with their CPU usage`
- `Show transaction backout counts`

**Complex:**
- `Identify the top 5 most CPU-intensive processes and show their CPU usage percentage, memory pages, messages sent and received, and the overall CPU utilization for that CPU at the same time interval`
- `Analyze disk I/O hotspots by calculating cache hit ratios and queue times per device`
- `Show system health by aggregating CPU, disk, and process metrics grouped by timestamp`

### Exporting results

After running a query, use the Download buttons in the UI to export as:
- **CSV** — full dataset
- **Excel** — formatted with bold headers
- **PDF** — includes query text, SQL, and data table (capped at 500 rows; use CSV/Excel for full data)

### Cache management

Repeated or semantically similar queries are served from the local ChromaDB cache (0.95 cosine similarity threshold) — no Gemini API call needed. Manage the cache at http://localhost:5173/cache

---

## Project structure

```
HPE_49/
├── backend/
│   ├── main.py                        # FastAPI app, all routes
│   ├── config.py                      # Env var loader
│   ├── requirements.txt
│   ├── .env.example                   # Copy to .env and fill in
│   ├── pipeline/
│   │   ├── normalizer.py              # Query normalization + domain detection
│   │   ├── cache.py                   # ChromaDB semantic cache
│   │   ├── schema_linker.py           # TF-IDF table/column selection
│   │   ├── prompt_builder.py          # LLM prompt assembly
│   │   ├── llm_engine.py              # Gemini API + retry logic
│   │   ├── validator.py               # SQLGlot security + correctness checks
│   │   ├── executor.py                # psycopg2 connection pool + execution
│   │   └── report_generator.py        # CSV / Excel / PDF export
│   ├── schema_store/
│   │   └── enriched_schema.yaml       # Full schema with column descriptions and correct types
│   ├── few_shots/
│   │   └── examples.yaml              # NL→SQL examples for the LLM
│   ├── audit/
│   │   └── query_log.py               # SQLite audit log
│   ├── setup_scripts/                 # One-time DB setup utilities
│   └── tests/                         # Unit + integration tests
├── frontend/
│   └── src/
│       ├── pages/                     # Dashboard, CacheManagement, HowItWorks
│       ├── components/                # QueryInput, ResultsTable, ChartView, etc.
│       └── lib/api.ts                 # All API calls
├── measurefiles/                      # Source CSV data files (9 tables)
└── docs/
    ├── Project_Overview.md            # Full architecture + design decisions
    ├── NOTES.md                       # Known issues, gotchas, benchmarks
    └── plan.md                        # Original build plan (all phases complete)
```

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | System health check |
| `POST` | `/api/query` | Run a natural language query |
| `POST` | `/api/sql` | Run a raw SQL query directly |
| `POST` | `/api/export` | Download results as CSV / Excel / PDF |
| `GET` | `/api/history` | Last 50 queries from audit log |
| `GET` | `/api/stats` | Analytics: hit rate, avg time, top domains |
| `GET` | `/api/schema` | Table names and column counts |
| `GET` | `/api/cache` | View cached query entries |
| `DELETE` | `/api/cache` | Clear all cache entries |
| `GET` | `/api/cache/threshold` | Read current similarity threshold |
| `POST` | `/api/cache/threshold` | Update threshold at runtime |

Interactive docs: http://localhost:8000/docs

---

## Troubleshooting

**Backend won't start**
- Check PostgreSQL is running: `pg_isready -h localhost -p 5432`
- Check all keys are set in `backend/.env`
- Check Python version: `python --version` (needs 3.10+)

**`db_connected: false` in health check**
- Verify `DB_USER`, `DB_PASSWORD`, `DB_NAME` in `.env`
- Test manually: `psql -U querycraft_user -d querycraft_db -h localhost`
- Make sure `querycraft_user` role was created and granted SELECT

**`cache_model_ready: false` in health check**
- The embedding model is still loading in the background — wait a few seconds and retry
- Queries will work immediately but won't benefit from cache hits until the model is ready

**LLM returns errors / no SQL generated**
- Check `GEMINI_API_KEY` is valid and has quota remaining
- Check internet connection (Gemini API is the only external call)
- Look at backend terminal for the specific error

**Frontend shows "Backend unreachable"**
- Make sure backend is running on port 8000
- Check no firewall is blocking localhost:8000

**Embedding model download hangs on first start**
- Needs internet access on first run to download `BAAI/bge-large-en-v1.5` (~1.3GB)
- After first download it's cached at `~/.cache/huggingface/hub/` and works offline

---

## Security notes

- The app connects to PostgreSQL as `querycraft_user` — a **SELECT-only** role. It cannot write, modify, or delete any data.
- All generated SQL passes through a 7-layer validator (SQLGlot AST parsing) before execution. No raw user input ever reaches the database.
- `statement_timeout = 30s` is enforced at both the DB role level and the connection level.
- This is a **single-user local deployment** — there is no authentication, rate limiting, or encryption. Do not expose it on a public network.

---

*QueryCraft v1.0.0 — HPE NonStop Performance Report Generator*
