"""
QueryCraft Comprehensive Stress Test
===============================================
Fixes from previous runs:
  - MAX_QUERY_COST raised to 250000 in .env
  - Added 3s delay between LLM queries to avoid Gemini 429 rate limits
  - Fixed reads_ column reference in SQL test #2
"""
import requests
import time
import json
import subprocess
import os

BASE = "http://localhost:8000"
RESULTS = []


def psql(sql):
    """Run a query via psql and return row count."""
    env = os.environ.copy()
    env["PGPASSWORD"] = "ro_pwd_123"
    proc = subprocess.run(
        ["psql", "-U", "querycraft_user", "-d", "querycraft_db",
         "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, env=env
    )
    lines = [l for l in proc.stdout.strip().split("\n") if l.strip()]
    return len(lines)


def api_query(q):
    t0 = time.time()
    r = requests.post(f"{BASE}/api/query", json={"query": q}, timeout=120)
    return r.status_code, r.json(), time.time() - t0


def api_sql(sql):
    t0 = time.time()
    r = requests.post(f"{BASE}/api/sql", json={"sql": sql}, timeout=120)
    return r.status_code, r.json(), time.time() - t0


def api_export(sql, fmt, query_text="test"):
    r = requests.post(f"{BASE}/api/export",
                      json={"sql": sql, "format": fmt, "query_text": query_text},
                      timeout=60)
    return r.status_code, r.content, r.headers.get("content-type", "")


def log(cat, query, expected, status, detail, pf, elapsed=0, source=""):
    RESULTS.append((cat, query, expected, status, detail, pf, elapsed, source))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: Natural Language Queries (25 queries across all 9 tables)
# ═══════════════════════════════════════════════════════════════════════════════
NL_QUERIES = [
    # --- Simple single-table ---
    ("cpu",   "Show average CPU busy time per CPU"),
    ("disc",  "Show disk read and write counts per device"),
    ("proc",  "List all process names with their CPU usage"),
    ("tmf",   "Show transaction backout counts"),
    ("dfile", "Top 20 files by total physical I/O calls"),
    ("dopen", "Count active opens per file and total requests across all openers"),
    ("udef",  "List all distinct user-defined counter names and how many processes set each"),
    ("file",  "Top 20 files by logical reads + writes"),
    ("ossns", "Average out all the server net values and show them to me"),

    # --- Complex / multi-table ---
    ("multi", "Analyze CPU utilization with memory pressure and identify bottlenecks"),
    ("multi", "Identify disk I/O hotspots by analyzing cache hit ratios and queue times"),
    ("multi", "Perform deep process analysis correlating CPU usage, memory and file I/O"),
    ("multi", "Analyze transaction performance correlating TMF stats with process activity"),
    ("multi", "Show comprehensive system health by aggregating CPU, memory, disk and process metrics"),

    # --- Edge cases ---
    ("cpu",   "show memory usage"),
    ("proc",  "which process consumes the most resources"),
    ("disc",  "Which device has the highest c0 misses?"),
    ("file",  "What is the implied cache hit percentage for file IO?"),
    ("dfile", "Give me a summary of DML activity — inserts updates deletes"),
    ("cpu",   "Show cpu queue length but with a really really long sentence that probably won't affect the embedding but might confuse the parser if it is not careful about truncation or maximum token limits since this is a deliberately verbose input"),

    # --- Queries referencing columns by description, not name ---
    ("proc",  "show me how many page faults each process has"),
    ("cpu",   "what is the interrupt overhead percentage for each CPU"),
    ("disc",  "show free disk space for each device"),
    ("ossns", "show semaphore wait counts"),
    ("tmf",   "how many transactions were aborted"),
]

print("# QueryCraft Stress Test Report — Final\n")
print(f"**Run at:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

# Clear cache
requests.delete(f"{BASE}/api/cache")
print("Cache cleared before test run.\n")

print("## 1. Natural Language Queries (25 queries)\n")
print("| # | Status | Table | Query | Time | Rows | Source | SQL / Error |")
print("|---|--------|-------|-------|------|------|--------|-------------|")

nl_pass = 0
nl_fail = 0
nl_details = []

for i, (table, q) in enumerate(NL_QUERIES, 1):
    try:
        code, body, elapsed = api_query(q)
        if code == 200:
            rows = body.get("row_count", 0)
            src  = "Cache" if body.get("cache_hit") else "LLM"
            sql  = body.get("sql", "")[:120].replace("|", "\\|").replace("\n", " ")
            log("NL", q, "200 + rows", code, f"{rows} rows", "✅ PASS", elapsed, src)
            print(f"| {i} | ✅ PASS | {table} | `{q[:60]}` | {elapsed:.1f}s | {rows} | {src} | `{sql}` |")
            nl_pass += 1
        else:
            err = body.get("detail", "Unknown")[:100].replace("|", "\\|").replace("\n", " ")
            log("NL", q, "200", code, err, "❌ FAIL", elapsed)
            print(f"| {i} | ❌ FAIL | {table} | `{q[:60]}` | {elapsed:.1f}s | - | - | {err} |")
            nl_fail += 1
            nl_details.append({"query": q, "error": err, "table": table})
    except Exception as e:
        log("NL", q, "200", 0, str(e)[:80], "❌ ERROR")
        print(f"| {i} | ❌ ERROR | {table} | `{q[:60]}` | - | - | - | {str(e)[:80]} |")
        nl_fail += 1
        nl_details.append({"query": q, "error": str(e)[:80], "table": table})

    # Rate limit protection: 3s delay between LLM calls
    time.sleep(3)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: Cache Hit/Miss Behaviour
# ═══════════════════════════════════════════════════════════════════════════════
print("\n## 2. Cache Hit/Miss Behaviour\n")
print("| # | Query | Expected | Actual | Status |")
print("|---|-------|----------|--------|--------|")

cache_tests = [
    ("Show average CPU busy time per CPU",             "Cache HIT (exact match)"),
    ("Show me the average CPU busy time for each CPU", "Cache HIT (semantic)"),
    ("Average CPU busy time grouped by CPU number",    "Cache HIT (semantic)"),
    ("Show disk read and write counts per device",     "Cache HIT (exact match)"),
    ("Show total reads and writes for each disk",      "Cache HIT (semantic)"),
    ("how many transactions were aborted",             "Cache HIT (exact match)"),
]

cache_pass = 0
cache_warn = 0
for i, (q, expected) in enumerate(cache_tests, 1):
    time.sleep(3)
    try:
        code, body, elapsed = api_query(q)
        if code == 200:
            hit = body.get("cache_hit", False)
            actual = "Cache HIT" if hit else "Cache MISS"
            if hit and "HIT" in expected:
                pf = "✅"
                cache_pass += 1
            elif not hit and "MISS" in expected:
                pf = "✅"
                cache_pass += 1
            else:
                pf = "⚠️"
                cache_warn += 1
            print(f"| {i} | `{q[:55]}` | {expected} | {actual} | {pf} |")
        else:
            err = body.get("detail", "")[:40]
            print(f"| {i} | `{q[:55]}` | {expected} | ERROR {code}: {err} | ❌ |")
    except Exception as e:
        print(f"| {i} | `{q[:55]}` | {expected} | {str(e)[:40]} | ❌ |")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: Direct SQL Mode — verified against psql
# ═══════════════════════════════════════════════════════════════════════════════
print("\n## 3. Direct SQL Mode (verified against psql)\n")
print("| # | Status | SQL | API Rows | psql Rows | Match? |")
print("|---|--------|-----|----------|-----------|--------|")

SQL_TESTS = [
    # Valid queries (disc uses reads not reads_ through API)
    ("SELECT cpu_num, AVG(cpu_busy_time) AS avg_busy FROM macht413.cpu GROUP BY cpu_num ORDER BY cpu_num LIMIT 10;", True),
    ("SELECT device_name, SUM(reads) AS total_reads, SUM(writes) AS total_writes FROM macht413.disc GROUP BY device_name ORDER BY total_reads DESC LIMIT 10;", True),
    ("SELECT COUNT(*) AS cnt FROM macht413.proc;", True),
    ("SELECT COUNT(*) AS cnt FROM macht413.file;", True),
    ("SELECT COUNT(*) AS cnt FROM macht413.dfile;", True),
    ("SELECT COUNT(*) AS cnt FROM macht413.dopen;", True),
    ("SELECT COUNT(*) AS cnt FROM macht413.ossns;", True),
    ("SELECT COUNT(*) AS cnt FROM macht413.tmf;", True),
    ("SELECT COUNT(*) AS cnt FROM macht413.udef;", True),
    # Validation — these MUST be blocked
    ("DROP TABLE macht413.cpu;", False),
    ("DELETE FROM macht413.cpu WHERE 1=1;", False),
    ("INSERT INTO macht413.cpu (cpu_num) VALUES (99);", False),
    ("UPDATE macht413.cpu SET cpu_num = 0;", False),
    ("SELECT * FROM macht413.cpu; DROP TABLE macht413.cpu;--", False),
]

sql_pass = 0
sql_fail = 0
for i, (sql, should_succeed) in enumerate(SQL_TESTS, 1):
    try:
        code, body, elapsed = api_sql(sql)
        api_rows = body.get("row_count", 0) if code == 200 else None

        if should_succeed:
            psql_count = psql(sql)
            match = "✅" if api_rows == psql_count else "❌"
            pf = "✅ PASS" if code == 200 and api_rows == psql_count else "❌ FAIL"
            if "PASS" in pf:
                sql_pass += 1
            else:
                sql_fail += 1
            print(f"| {i} | {pf} | `{sql[:70]}` | {api_rows} | {psql_count} | {match} |")
        else:
            pf = "✅ PASS" if code != 200 else "❌ FAIL"
            if "PASS" in pf:
                sql_pass += 1
            else:
                sql_fail += 1
            err = body.get("detail", "")[:60].replace("|", "\\|")
            print(f"| {i} | {pf} | `{sql[:70]}` | BLOCKED | N/A | {err} |")
    except Exception as e:
        sql_fail += 1
        print(f"| {i} | ❌ ERROR | `{sql[:70]}` | - | - | {str(e)[:50]} |")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: Export Tests (CSV, Excel, PDF)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n## 4. Export Tests\n")
print("| Format | Status | Size | Content-Type | Notes |")
print("|--------|--------|------|-------------|-------|")

export_sql = "SELECT cpu_num, AVG(cpu_busy_time) AS avg_busy FROM macht413.cpu GROUP BY cpu_num ORDER BY cpu_num LIMIT 5"
export_pass = 0

for fmt in ["csv", "excel", "pdf"]:
    try:
        code, content, ctype = api_export(export_sql, fmt)
        if code == 200:
            size = len(content)
            ok = size > 0
            notes = ""
            if fmt == "csv":
                text = content.decode("utf-8", errors="replace")
                lines = [l for l in text.strip().split("\n") if l.strip()]
                notes = f"{len(lines)} lines, header: `{lines[0][:60] if lines else 'EMPTY'}`"
            elif fmt == "excel":
                notes = f"XLSX magic: `{content[:4].hex()}` (PK zip)"
            elif fmt == "pdf":
                notes = f"PDF header: `{content[:5].decode('ascii', errors='replace')}`"
            pf = "✅ PASS" if ok else "❌ FAIL"
            if ok:
                export_pass += 1
            print(f"| {fmt} | {pf} | {size:,} B | {ctype} | {notes} |")
        else:
            print(f"| {fmt} | ❌ FAIL | - | - | HTTP {code} |")
    except Exception as e:
        print(f"| {fmt} | ❌ ERROR | - | - | {str(e)[:60]} |")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: Summary
# ═══════════════════════════════════════════════════════════════════════════════
print("\n## 5. System Stats\n")
try:
    r = requests.get(f"{BASE}/api/stats")
    stats = r.json()
    print(f"- **Total queries logged:** {stats.get('total_queries')}")
    print(f"- **Cache hit rate:** {stats.get('cache_hit_rate', 0):.1%}")
    print(f"- **Avg execution time:** {stats.get('avg_execution_time_ms', 0):.0f} ms")
    print(f"- **Validation failure rate:** {stats.get('validation_failure_rate', 0):.1%}")
    print(f"- **Retry rate:** {stats.get('retry_rate', 0):.1%}")
except Exception as e:
    print(f"- Stats unavailable: {e}")

print("\n## 6. Detailed Failure Log\n")
if nl_details:
    print("| Table | Query | Error |")
    print("|-------|-------|-------|")
    for d in nl_details:
        print(f"| {d['table']} | `{d['query'][:60]}` | {d['error'][:80]} |")
else:
    print("No NL failures recorded!")

print(f"\n## 7. Overall Scorecard\n")
print(f"| Category | Passed | Failed | Total |")
print(f"|----------|--------|--------|-------|")
print(f"| Natural Language | {nl_pass} | {nl_fail} | {nl_pass+nl_fail} |")
print(f"| Cache Behaviour | {cache_pass} | {cache_warn} warns | {len(cache_tests)} |")
print(f"| Direct SQL | {sql_pass} | {sql_fail} | {sql_pass+sql_fail} |")
print(f"| Exports | {export_pass} | {3-export_pass} | 3 |")
total_pass = nl_pass + sql_pass + export_pass
total_fail = nl_fail + sql_fail + (3-export_pass)
print(f"| **TOTAL** | **{total_pass}** | **{total_fail}** | **{total_pass+total_fail}** |")
