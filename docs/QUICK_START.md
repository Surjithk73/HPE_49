# QueryCraft — Quick Start Guide

**Status:** ✅ Production Ready  
**Last Updated:** April 12, 2026

---

## 🚀 Start the System

### 1. Start Backend (Terminal 1)
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Wait for:** `[QueryCraft] Startup complete` (takes ~15 seconds on first run)

### 2. Start Frontend (Terminal 2)
```bash
cd frontend
npm run dev
```

**Access:** http://localhost:5173

---

## 🧪 Quick Test

### Via API (curl):
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show average CPU busy time per CPU"}'
```

### Via Browser:
1. Open http://localhost:5173
2. Type: "Show average CPU busy time per CPU"
3. Click Submit
4. See results in table/chart

---

## 📊 System Health Check

```bash
curl http://localhost:8000/api/health
```

**Expected:**
```json
{
  "status": "ok",
  "db_connected": true,
  "cache_ready": true,
  "llm_model": "gemini-3.1-flash-lite-preview",
  "cache_entries": 2,
  "schema_tables": 9
}
```

---

## 💡 Example Queries

### Simple Queries:
- "Show average CPU busy time per CPU"
- "List all process names with their CPU usage"
- "Show disk read and write counts per device"
- "What is the total CPU busy time for CPU 0"
- "Show transaction backout counts"

### Complex Queries:
- "Compare CPU busy time with process CPU usage for CPU 0"
- "Show disk reads and CPU busy time correlation over time"
- "Find disks with free space below 1000000"
- "Show top 10 processes by memory usage with their CPU time"
- "Calculate CPU utilization percentage for each CPU"

---

## 📥 Export Reports

### Via API:
```bash
# Get SQL from a query first
SQL="SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000"

# Export as CSV
curl -X POST http://localhost:8000/api/export \
  -H "Content-Type: application/json" \
  -d "{\"sql\": \"$SQL\", \"format\": \"csv\", \"query_text\": \"Test query\"}" \
  --output report.csv

# Export as Excel
curl -X POST http://localhost:8000/api/export \
  -H "Content-Type: application/json" \
  -d "{\"sql\": \"$SQL\", \"format\": \"excel\", \"query_text\": \"Test query\"}" \
  --output report.xlsx

# Export as PDF
curl -X POST http://localhost:8000/api/export \
  -H "Content-Type: application/json" \
  -d "{\"sql\": \"$SQL\", \"format\": \"pdf\", \"query_text\": \"Test query\"}" \
  --output report.pdf
```

### Via Frontend:
1. Run a query
2. Click "Download CSV" / "Download Excel" / "Download PDF"
3. File downloads automatically

---

## 🔍 View Query History

### Via API:
```bash
curl http://localhost:8000/api/history
```

### Via Frontend:
- See "Query History" panel on the right side
- Click any entry to re-run that query

---

## 📁 Important Files

### Configuration:
- `backend/.env` — Database credentials, Gemini API key
- `backend/config.py` — Configuration loader

### Data:
- `backend/data/*.csv` — 9 CSV files (212,689 rows total)
- `backend/schema_store/enriched_schema.yaml` — Schema definitions
- `backend/few_shots/examples.yaml` — 16 query examples for LLM

### Logs:
- `backend/audit/query_log.db` — SQLite audit log (all queries)
- `backend/cache_store/` — ChromaDB semantic cache

### Tests:
- `backend/test_phase10.py` — Comprehensive test suite
- `backend/PHASE10_TEST_RESULTS.md` — Detailed test results

---

## 🛠️ Troubleshooting

### Backend won't start:
1. Check PostgreSQL is running: `Get-Service -Name "*postgresql*"`
2. Check database exists: `psql -U postgres -l | grep querycraft_db`
3. Check .env file has all required keys
4. Wait 15 seconds for embedding model to load

### Database connection error:
1. Verify credentials in `backend/.env`
2. Test connection: `psql -U querycraft_user -d querycraft_db -h localhost`
3. Check `querycraft_user` role exists

### LLM not generating SQL:
1. Check Gemini API key in `backend/.env`
2. Check internet connection
3. Look for errors in backend terminal

### Cache not working:
1. Check `backend/cache_store/` directory exists
2. Wait for embedding model to load (~10 seconds)
3. Check backend logs for cache initialization

### Frontend not connecting:
1. Check backend is running on port 8000
2. Check CORS settings in `backend/main.py`
3. Clear browser cache

---

## 📊 Database Schema

### Tables (9):
- `macht413.cpu` — CPU utilization (420 rows)
- `macht413.disc` — Disk I/O (2,640 rows)
- `macht413.dfile` — Disk files (34,265 rows)
- `macht413.dopen` — File openers (870 rows)
- `macht413.file` — File operations (60,969 rows)
- `macht413.ossns` — OSS namespace (120 rows)
- `macht413.proc` — Processes (110,520 rows)
- `macht413.tmf` — Transactions (245 rows)
- `macht413.udef` — User defined (2,640 rows)

### Common Columns (for joins):
- `system_name` — Server instance
- `cpu_num` — CPU number
- `from_timestamp` — Start time
- `to_timestamp` — End time
- `u_loadid_loadid` — Session ID

---

## 🔒 Security Notes

### What's Protected:
✅ Only SELECT queries allowed  
✅ Read-only database role  
✅ 30-second query timeout  
✅ SQL injection blocked  
✅ Malicious keywords blocked  

### What's NOT Protected:
⚠️ No authentication (single-user local deployment)  
⚠️ No rate limiting  
⚠️ No encryption (localhost only)  

---

## 📞 Support

### Documentation:
- `README.md` — Project overview
- `Project_Overview.md` — Detailed architecture
- `plan.md` — Implementation phases
- `TESTING_COMPLETE.md` — Test results summary
- `backend/PHASE10_TEST_RESULTS.md` — Detailed test results

### API Documentation:
- http://localhost:8000/docs — Interactive Swagger UI
- http://localhost:8000/redoc — ReDoc documentation

---

## 🎯 Quick Commands

```bash
# Start backend
cd backend && uvicorn main:app --reload --port 8000

# Start frontend
cd frontend && npm run dev

# Run tests
cd backend && python test_phase10.py

# Check health
curl http://localhost:8000/api/health

# Run a query
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show CPU statistics"}'

# View history
curl http://localhost:8000/api/history

# Check database
psql -U querycraft_user -d querycraft_db -h localhost

# View audit log
sqlite3 backend/audit/query_log.db "SELECT * FROM query_log ORDER BY timestamp DESC LIMIT 10;"
```

---

*QueryCraft v1.0.0 — HPE NonStop Performance Report Generator*  
*Ready to use! 🚀*
