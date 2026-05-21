# QueryCraft — Development Notes

Consolidated from historical phase summaries, test results, and fix logs.
Keep this file updated as the project evolves.

---

## System Status

All 10 build phases (0–10) are complete. The system is production-ready for local single-user deployment.

- Backend: FastAPI on port 8000
- Frontend: React/Vite on port 5173
- Database: PostgreSQL `querycraft_db`, schema `macht413`, 212,689 rows across 9 tables
- LLM: Gemini API (`gemini-3.1-flash-lite` — configured in `.env`)
- Cache: ChromaDB in `backend/cache_store/`, similarity threshold 0.95 (code) — note: some older docs say 0.85, the actual value in `config.py` is 0.95
- Audit log: SQLite at `backend/audit/query_log.db`

---

## Database Row Counts (verified)

| Table   | Rows    |
|---------|---------|
| cpu     | 420     |
| disc    | 2,640   |
| dfile   | 34,265  |
| dopen   | 870     |
| file    | 60,969  |
| ossns   | 120     |
| proc    | 110,520 |
| tmf     | 245     |
| udef    | 2,640   |
| **Total** | **212,689** |

---

## Schema Stats

- `enriched_schema.yaml`: 9 tables, 601 total columns, 487 queryable columns (114 internal filtered)
- `few_shots/examples.yaml`: 14 examples (4 simple + 10 complex multi-table)

---

## All-Tables Datatype Fix (completed May 21, 2026)

**Problem:** The CSV loader imported every column as TEXT by default. Aggregate functions
(`SUM`, `AVG`, `MAX`, etc.) fail with `function sum(text) does not exist` on any counter
column that was not explicitly cast at load time. This affected all 9 tables — not just ossns.

**Affected tables and column counts fixed:**
- cpu: 3 columns  
- dfile: 19 columns  
- disc: 21 columns  
- dopen: 10 columns  
- file: 14 columns (ip_ip_addr intentionally left as TEXT — contains IP address strings)  
- ossns: 3 columns  
- proc: 49 columns  
- tmf: 10 columns  
- udef: 16 columns  
- **Total: 145 columns converted to BIGINT**

**Fix applied:** `backend/setup_scripts/fix_all_column_types.py` — run once as postgres superuser.
All 212,689 rows preserved. Safe to re-run (skips already-BIGINT columns).

**Prevention:** The fix script is now in the repo. Run it after any fresh CSV load.

---

## OSSNS Datatype Fix (completed April 13, 2026)

**Problem:** 12 columns in `macht413.ossns` were loaded as TEXT instead of BIGINT, breaking `AVG()`, `SUM()`, etc.

**Fix applied:** `backend/setup_scripts/fix_ossns_datatypes.py` was run with postgres superuser credentials. All 12 columns converted to BIGINT. All 212,689 rows preserved.

**Affected columns (all now BIGINT):**
`ic_entries`, `lc_entries`, `rr_processed`, `rr_redir_sent`, `rr_redir_processed`,
`ic_lookups`, `lc_lookups`, `checkpoint_reqs`, `checkpoint_blks`, `dp2_dd_reqs`,
`gettime_reqs`, `settime_reqs`

**Prevention:** `backend/setup_scripts/create_tables.sql` has been corrected. Future DB setups will use BIGINT for these columns.

If you ever need to re-run the fix (e.g. fresh DB setup from old scripts):
```bash
cd backend/setup_scripts
python fix_ossns_datatypes.py
```

---

## Known Issues / Gotchas

1. **`reads_` trailing underscore** — The `disc` table uses `reads_` (not `reads`) to avoid a PostgreSQL reserved word conflict. The normalizer handles this automatically, but be aware when writing raw SQL.

2. **`disc` not `disk`** — HPE NonStop uses `disc`. The normalizer expands `disk` → `disc` automatically.

3. **PDF backend on Windows** — WeasyPrint requires GTK (unavailable on Windows). `report_generator.py` falls back to `reportlab` automatically. Both produce valid PDFs.

4. **Cache threshold discrepancy** — Fixed. `.env` was set to `0.85` but `config.py` defaulted to `0.95`. Both are now aligned at `0.95`. The `HowItWorks.tsx` UI text has also been updated to say "95%".

5. **Dead dependencies:**
   - Frontend: `axios` is installed but `api.ts` uses native `fetch`
   - Frontend: `@reduxjs/toolkit` is installed but plain React state is used
   - Backend: `pandas` is in `requirements.txt` but not imported anywhere in the pipeline

6. **Chart view caps at 200 rows** — `ChartView.tsx` only renders the first 200 rows for performance. This is not communicated clearly to users.

7. **PDF caps at 500 rows** — `report_generator.py` limits PDF output to 500 rows with a note. CSV and Excel export all rows.

8. **No frontend input length limit** — The query textarea has no max-length guard before sending to the API.

9. **`DELETE /api/cache/query` routing** — Registered as `/api/cache/query` with a `?query=` param. FastAPI may have routing ambiguity with `DELETE /api/cache`. Worth testing if cache deletion behaves unexpectedly.

---

## Performance Benchmarks (from Phase 10 testing)

| Metric | Result |
|--------|--------|
| Cache hit response | ~190ms |
| Full pipeline (LLM + DB) | 63–191ms DB, ~1–2s total |
| CSV export | Instant |
| Excel export | Instant |
| PDF export | Instant |
| Embedding model load (first start) | ~10–15 seconds |

---

## Security Verification (Phase 10)

All four defense layers confirmed working:
1. LLM converts malicious natural language to safe SELECT statements
2. SQLGlot validator blocks forbidden keywords and injection patterns
3. `querycraft_user` DB role is SELECT-only (writes return permission denied)
4. `statement_timeout = 30s` enforced at both role level and connection level

Direct validator tests (33/33 passed): DELETE, DROP, ALTER, INSERT, UPDATE, TRUNCATE, EXEC all blocked. Injection patterns (`--`, `/*`, `;` chaining, `xp_`) all blocked.

---

## LLM Notes

- Model: `gemini-3.1-flash-lite` (set in `.env`)
- Retry logic: max 2 retries on validation failure, with error feedback to LLM
- Interface is swappable — to migrate to Ollama, only `pipeline/llm_engine.py` needs to change
- The `LLMEngine.generate_sql(prompt)` method is the only public contract the pipeline uses

---

## Architecture Diagram

The interactive SVG diagram lives in `frontend/src/components/ArchitectureDiagram.tsx`.
- Canvas: 1640×600px, nodes are 180×90px
- Nodes are draggable (positions reset on page refresh)
- Hover over a node to highlight its connected paths
- Accessible at: http://localhost:5173/how-it-works

---

## Future Enhancements (noted but out of scope)

- Ollama / local LLM swap (architecture already supports it)
- User authentication
- Cloud deployment
- Automated pytest suite (Phase 10 tests are currently manual)
- Save/favorite queries
- Query scheduling
- Email reports
- Zoom/pan controls on architecture diagram
- Persist diagram node positions to localStorage
