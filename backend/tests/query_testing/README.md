# Query Testing

Automated stress tests for the QueryCraft NL-to-SQL pipeline.

## Quick Start

```bash
# 1. Make sure the backend is running
cd backend
uvicorn main:app --reload --port 8000

# 2. Run the stress test (from this directory)
cd tests/query_testing
python stress_test.py
```

The script outputs a Markdown report to stdout. To save results:

```bash
python stress_test.py > stress_test_result.md
```

## What It Tests

| Category | Count | Description |
|----------|-------|-------------|
| **Natural Language** | 25 | Queries across all 9 tables — simple, complex joins, edge cases |
| **Direct SQL** | 14 | Raw SELECT queries verified against `psql`, plus injection/DDL blocking |
| **Cache Behaviour** | 6 | Exact match, semantic similarity, and distant rephrasing |
| **Exports** | 3 | CSV, Excel, PDF — validates file format and content |

### Natural Language Query Categories

- **Simple single-table** (9 queries) — one table, basic aggregations (e.g. `"Show average CPU busy time per CPU"`)
- **Complex multi-table** (5 queries) — JOINs, correlated analysis (e.g. `"Perform deep process analysis correlating CPU usage, memory and file I/O"`)
- **Edge cases** (6 queries) — ambiguous phrasing, verbose input, column-by-description references
- **Column description** (5 queries) — uses human descriptions instead of column names (e.g. `"show memory usage"` instead of `"show pres_pages_end"`)

### SQL Validation Tests

- 9 valid SELECTs — row counts compared with `psql` output
- 5 malicious queries — `DROP`, `DELETE`, `INSERT`, `UPDATE`, SQL injection

## Prerequisites

- Backend running on `http://localhost:8000`
- PostgreSQL with `macht413` schema populated
- Valid NVIDIA NIM API key(s) in `backend/.env` (PLANNER_API_KEY / SQL_GENERATOR_API_KEY)
- Python packages: `requests`
