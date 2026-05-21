# QueryCraft Stress Test Report — Final

**Run at:** 2026-05-21 15:58:49

Cache cleared before test run.

## 1. Natural Language Queries (25 queries)

| # | Status | Table | Query | Time | Rows | Source | SQL / Error |
|---|--------|-------|-------|------|------|--------|-------------|
| 1 | ✅ PASS | cpu | `Show average CPU busy time per CPU` | 1.5s | 7 | LLM | `SELECT cpu_num, AVG(cpu_busy_time) AS avg_busy_time FROM macht413.cpu GROUP BY cpu_num ORDER BY cpu_num LIMIT 10000` |
| 2 | ✅ PASS | disc | `Show disk read and write counts per device` | 9.2s | 18 | LLM | `SELECT device_name, SUM(requests) AS total_requests, SUM(read_qbusy_time) AS total_read_busy, SUM(write_qbusy_time) AS t` |
| 3 | ✅ PASS | proc | `List all process names with their CPU usage` | 1.8s | 10000 | LLM | `SELECT process_name, cpu_busy_time FROM macht413.proc ORDER BY cpu_busy_time DESC LIMIT 10000` |
| 4 | ✅ PASS | tmf | `Show transaction backout counts` | 1.7s | 1 | LLM | `SELECT SUM(aborting_trans) AS total_aborts FROM macht413.tmf LIMIT 10000` |
| 5 | ✅ PASS | dfile | `Top 20 files by total physical I/O calls` | 1.9s | 20 | LLM | `SELECT file_name_volume \|\| '.' \|\| file_name_subvol \|\| '.' \|\| file_name_filename AS file_path, device_name, driver_input_` |
| 6 | ✅ PASS | dopen | `Count active opens per file and total requests across all op` | 16.6s | 12 | LLM | `SELECT file_name_volume \|\| '.' \|\| file_name_subvol \|\| '.' \|\| file_name_filename AS file_path, COUNT(*) AS open_count, SU` |
| 7 | ✅ PASS | udef | `List all distinct user-defined counter names and how many pr` | 1.9s | 22 | LLM | `SELECT name, COUNT(DISTINCT process_name) AS process_count, COUNT(*) AS row_count FROM macht413.udef WHERE NOT name IS N` |
| 8 | ✅ PASS | file | `Top 20 files by logical reads + writes` | 1.3s | 20 | LLM | `SELECT file_name_volume \|\| '.' \|\| file_name_subvol \|\| '.' \|\| file_name_filename AS file_path, writes, records_accessed, ` |
| 9 | ✅ PASS | ossns | `Average out all the server net values and show them to me` | 1.7s | 1 | LLM | `SELECT AVG(rr_processed) AS avg_rr_processed, AVG(rr_redir_sent) AS avg_rr_redir_sent, AVG(checkpoint_reqs) AS avg_check` |
| 10 | ✅ PASS | multi | `Analyze CPU utilization with memory pressure and identify bo` | 13.1s | 420 | LLM | `SELECT c.cpu_num, c.from_timestamp, c.cpu_busy_time * 100.0 / NULLIF(c.delta_time, 0) AS cpu_utilization_pct, c.cpu_qtim` |
| 11 | ✅ PASS | multi | `Identify disk I/O hotspots by analyzing cache hit ratios and` | 2.1s | 0 | LLM | `SELECT device_name, (c0_write_cleans + c0_write_dirtys + c0_write_misses) AS total_cache_ops, CASE WHEN (c0_write_cleans` |
| 12 | ✅ PASS | multi | `Perform deep process analysis correlating CPU usage, memory ` | 15.7s | 10000 | LLM | `SELECT p.system_name, p.cpu_num, p.pin, p.process_name, p.from_timestamp, p.cpu_busy_time / NULLIF(p.delta_time, 0) * 10` |
| 13 | ✅ PASS | multi | `Analyze transaction performance correlating TMF stats with p` | 15.8s | 0 | LLM | `SELECT t.from_timestamp, t.cpu_num, t.home_trans, t.remote_trans, t.aborting_trans, t.home_trans_qtime / NULLIF(t.home_t` |
| 14 | ✅ PASS | multi | `Show comprehensive system health by aggregating CPU, memory,` | 6.7s | 420 | LLM | `SELECT c.from_timestamp, COUNT(DISTINCT c.cpu_num) AS total_cpus, AVG(c.cpu_qtime / NULLIF(c.delta_time, 0)) AS avg_cpu_` |
| 15 | ✅ PASS | cpu | `show memory usage` | 1.2s | 420 | LLM | `SELECT cpu_num, from_timestamp, mem_mb, starting_free_mem, ending_free_mem, swaps, page_requests, page_scans, mm_page_sc` |
| 16 | ✅ PASS | proc | `which process consumes the most resources` | 2.0s | 10000 | LLM | `SELECT process_name, cpu_num, pin, (cpu_busy_time / NULLIF(delta_time, 0) * 100) AS cpu_pct, pres_pages_end AS current_m` |
| 17 | ✅ PASS | disc | `Which device has the highest c0 misses?` | 1.4s | 18 | LLM | `SELECT device_name, SUM(c0_misses) AS total_c0_misses FROM macht413.disc GROUP BY device_name ORDER BY total_c0_misses D` |
| 18 | ✅ PASS | file | `What is the implied cache hit percentage for file IO?` | 13.4s | 10000 | LLM | `SELECT file_name_volume \|\| '.' \|\| file_name_subvol \|\| '.' \|\| file_name_filename AS file_path, opener_device_name, file_t` |
| 19 | ❌ FAIL | dfile | `Give me a summary of DML activity — inserts updates deletes` | 4.7s | - | - | LLM error: Max retries exceeded. Last error: Forbidden keyword detected: INSERT |
| 20 | ✅ PASS | cpu | `Show cpu queue length but with a really really long sentence` | 1.6s | 420 | LLM | `SELECT cpu_num, cpu_qtime / NULLIF(delta_time, 0) AS avg_cpu_queue_length FROM macht413.cpu ORDER BY from_timestamp DESC` |
| 21 | ✅ PASS | proc | `show me how many page faults each process has` | 1.4s | 849 | LLM | `SELECT process_name, SUM(page_faults) AS total_page_faults FROM macht413.proc GROUP BY process_name ORDER BY total_page_` |
| 22 | ✅ PASS | cpu | `what is the interrupt overhead percentage for each CPU` | 2.0s | 420 | LLM | `SELECT cpu_num, intr_busy_time * 100.0 / NULLIF(delta_time, 0) AS interrupt_busy_pct FROM macht413.cpu ORDER BY cpu_num ` |
| 23 | ✅ PASS | disc | `show free disk space for each device` | 1.4s | 2640 | LLM | `SELECT device_name, starting_free_space, ending_free_space, starting_free_blocks, ending_free_blocks FROM macht413.disc ` |
| 24 | ✅ PASS | ossns | `show semaphore wait counts` | 1.3s | 120 | LLM | `SELECT process_name, sem_waits FROM macht413.ossns ORDER BY sem_waits DESC LIMIT 10000` |
| 25 | ✅ PASS | tmf | `how many transactions were aborted` | 1.3s | 1 | LLM | `SELECT SUM(aborting_trans) AS total_aborted_transactions FROM macht413.tmf LIMIT 10000` |

## 2. Cache Hit/Miss Behaviour

| # | Query | Expected | Actual | Status |
|---|-------|----------|--------|--------|
| 1 | `Show average CPU busy time per CPU` | Cache HIT (exact match) | Cache HIT | ✅ |
| 2 | `Show me the average CPU busy time for each CPU` | Cache HIT (semantic) | Cache HIT | ✅ |
| 3 | `Average CPU busy time grouped by CPU number` | Cache HIT (semantic) | Cache MISS | ⚠️ |
| 4 | `Show disk read and write counts per device` | Cache HIT (exact match) | Cache HIT | ✅ |
| 5 | `Show total reads and writes for each disk` | Cache HIT (semantic) | Cache MISS | ⚠️ |
| 6 | `how many transactions were aborted` | Cache HIT (exact match) | Cache HIT | ✅ |

## 3. Direct SQL Mode (verified against psql)

| # | Status | SQL | API Rows | psql Rows | Match? |
|---|--------|-----|----------|-----------|--------|
| 1 | ✅ PASS | `SELECT cpu_num, AVG(cpu_busy_time) AS avg_busy FROM macht413.cpu GROUP` | 7 | 7 | ✅ |
| 2 | ✅ PASS | `SELECT device_name, SUM(reads) AS total_reads, SUM(writes) AS total_wr` | 10 | 10 | ✅ |
| 3 | ✅ PASS | `SELECT COUNT(*) AS cnt FROM macht413.proc;` | 1 | 1 | ✅ |
| 4 | ✅ PASS | `SELECT COUNT(*) AS cnt FROM macht413.file;` | 1 | 1 | ✅ |
| 5 | ✅ PASS | `SELECT COUNT(*) AS cnt FROM macht413.dfile;` | 1 | 1 | ✅ |
| 6 | ✅ PASS | `SELECT COUNT(*) AS cnt FROM macht413.dopen;` | 1 | 1 | ✅ |
| 7 | ✅ PASS | `SELECT COUNT(*) AS cnt FROM macht413.ossns;` | 1 | 1 | ✅ |
| 8 | ✅ PASS | `SELECT COUNT(*) AS cnt FROM macht413.tmf;` | 1 | 1 | ✅ |
| 9 | ✅ PASS | `SELECT COUNT(*) AS cnt FROM macht413.udef;` | 1 | 1 | ✅ |
| 10 | ✅ PASS | `DROP TABLE macht413.cpu;` | BLOCKED | N/A | SQL validation failed: Forbidden keyword detected: DROP |
| 11 | ✅ PASS | `DELETE FROM macht413.cpu WHERE 1=1;` | BLOCKED | N/A | SQL validation failed: Forbidden keyword detected: DELETE |
| 12 | ✅ PASS | `INSERT INTO macht413.cpu (cpu_num) VALUES (99);` | BLOCKED | N/A | SQL validation failed: Forbidden keyword detected: INSERT |
| 13 | ✅ PASS | `UPDATE macht413.cpu SET cpu_num = 0;` | BLOCKED | N/A | SQL validation failed: Forbidden keyword detected: UPDATE |
| 14 | ✅ PASS | `SELECT * FROM macht413.cpu; DROP TABLE macht413.cpu;--` | BLOCKED | N/A | SQL validation failed: Potential SQL injection pattern detec |

## 4. Export Tests

| Format | Status | Size | Content-Type | Notes |
|--------|--------|------|-------------|-------|
| csv | ✅ PASS | 131 B | text/csv; charset=utf-8 | 6 lines, header: `cpu_num,avg_busy` |
| excel | ✅ PASS | 5,111 B | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | XLSX magic: `504b0304` (PK zip) |
| pdf | ✅ PASS | 12,535 B | application/pdf | PDF header: `%PDF-` |

## 5. System Stats

- **Total queries logged:** 166
- **Cache hit rate:** 6.0%
- **Avg execution time:** 22 ms
- **Validation failure rate:** 34.9%
- **Retry rate:** 6.4%

## 6. Detailed Failure Log

| Table | Query | Error |
|-------|-------|-------|
| dfile | `Give me a summary of DML activity — inserts updates deletes` | LLM error: Max retries exceeded. Last error: Forbidden keyword detected: INSERT |

## 7. Overall Scorecard

| Category | Passed | Failed | Total |
|----------|--------|--------|-------|
| Natural Language | 24 | 1 | 25 |
| Cache Behaviour | 4 | 2 warns | 6 |
| Direct SQL | 14 | 0 | 14 |
| Exports | 3 | 0 | 3 |
| **TOTAL** | **41** | **1** | **42** |
