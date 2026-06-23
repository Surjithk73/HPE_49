import requests
import json
import time
import os
import sys
from concurrent.futures import ThreadPoolExecutor

PROMPTS = [
    # --- cpu table (6 prompts) ---
    {"group": "cpu", "query": "Show CPU busy percentage for each CPU"},
    {"group": "cpu", "query": "Show the average CPU ready queue length per CPU"},
    {"group": "cpu", "query": "Show interrupt busy percentage per CPU ordered by interrupt busy time descending"},
    {"group": "cpu", "query": "Show the acceleration profile per CPU with TNS, accelerated, and native busy percentages"},
    {"group": "cpu", "query": "Show CPU busy percentage for each CPU normalized by IPU count, with values between 0 and 100"},
    {"group": "cpu", "query": "Show average dispatches per second, disc I/Os per second, and cache hits per second for each CPU"},

    # --- disc table (5 prompts) ---
    {"group": "disc", "query": "Show average read and write throughput in bytes per second per disk device"},
    {"group": "disc", "query": "Show average read queue length and write queue length per disk device"},
    {"group": "disc", "query": "Show disk cache hit ratio across all cache levels per device"},
    {"group": "disc", "query": "Show disk device busy percentage, read queue busy percentage, and write queue busy percentage per device"},
    {"group": "disc", "query": "Show top 5 disk devices by total requests per second"},

    # --- dfile table (4 prompts) ---
    {"group": "dfile", "query": "Show average driver input and output calls per second per disk file"},
    {"group": "dfile", "query": "Show average cache read hits and cache write hits per disk file"},
    {"group": "dfile", "query": "Show average open queue length per disk file ordered by open queue length descending"},
    {"group": "dfile", "query": "Show total lock wait time and number of lock timeouts per disk file"},

    # --- dopen table (3 prompts) ---
    {"group": "dopen", "query": "Show average driver input and output calls per second per file opener process"},
    {"group": "dopen", "query": "Show total lock wait time and lock timeouts per file opener grouped by file name"},
    {"group": "dopen", "query": "Show average cache hits and cache write hits per opener process across all open files"},

    # --- file table (4 prompts) ---
    {"group": "file", "query": "Show top 20 files by total logical reads and writes combined"},
    {"group": "file", "query": "Show total messages sent and message bytes per file grouped by opener process name"},
    {"group": "file", "query": "Show total lock wait time and number of lock escalations per file"},
    {"group": "file", "query": "Show average requests per second and average reply queue time per open file"},

    # --- proc table (5 prompts) ---
    {"group": "proc", "query": "Show top 10 processes by CPU busy time"},
    {"group": "proc", "query": "Show average dispatches per second and page faults per second per process"},
    {"group": "proc", "query": "Show average messages sent per second and messages received per second per process"},
    {"group": "proc", "query": "Show average present pages queue length and memory queue time percentage per process"},
    {"group": "proc", "query": "Show average file reads per second and file writes per second per process"},

    # --- tmf table (4 prompts) ---
    {"group": "tmf", "query": "Show home transaction abort rate per CPU as a percentage of total home transactions"},
    {"group": "tmf", "query": "Show average home transactions per second and remote transactions per second per CPU"},
    {"group": "tmf", "query": "Show transaction backout queue time average queue length per CPU"},
    {"group": "tmf", "query": "Show average home network transactions per second and their average response time per CPU"},

    # --- ossns table (3 prompts) ---
    {"group": "ossns", "query": "Show OSS namespace server cache hit ratio for both inode cache and local cache per process"},
    {"group": "ossns", "query": "Show average DP2 messages per second and DP2 message queue time per OSS namespace process"},
    {"group": "ossns", "query": "Show average semaphore waits per second and semaphore wait queue time per OSS namespace process"},

    # --- sqls table (3 prompts) ---
    {"group": "sqls", "query": "Show top 10 SQL statements by total number of calls per process"},
    {"group": "sqls", "query": "Show average elapsed busy time per SQL statement call grouped by process name"},
    {"group": "sqls", "query": "Show total lock waits and lock escalations per SQL statement grouped by process name"},

    # --- sqlp table (2 prompts) ---
    {"group": "sqlp", "query": "Show total SQL statement compiles and recompiles per process"},
    {"group": "sqlp", "query": "Show average SQL new process creation time per process"},

    # --- udef table (1 prompt) ---
    {"group": "udef", "query": "Show the sum of user-defined counter values grouped by counter name and process name"},
]


API_URL = "http://127.0.0.1:8000"
RESULTS_FILE = "test_results.json"
HTML_FILE = "test_report.html"

def run_single_test(item, session_id=None):
    payload = {"query": item['query'], "target_db": "machd500"}
    if session_id: payload["session_id"] = session_id
    
    try:
        start_t = time.time()
        r = requests.post(f"{API_URL}/api/query/start", json=payload, timeout=600)
        elapsed = time.time() - start_t
        
        if r.status_code == 200:
            data = r.json()
            return {
                "group": item["group"],
                "query": item["query"],
                "state": data.get("state"),
                "sql": data.get("sql", ""),
                "clarification_questions": data.get("questions", []),
                "data_preview": data.get("results", [])[:5] if data.get("results") else [],
                "time_sec": round(elapsed, 2),
                "error": data.get("error", ""),
                "session_id": data.get("session_id"),
                "debug_prompt": data.get("debug_prompt", ""),
                "raw_llm_output": data.get("raw_llm_output", "")
            }
        else:
            return {
                "group": item["group"], "query": item["query"],
                "state": "error", "error": f"HTTP {r.status_code}: {r.text}",
                "time_sec": round(elapsed, 2)
            }
    except Exception as e:
        return {"group": item["group"], "query": item["query"], "state": "exception", "error": str(e)}

def run_test():
    print("Setting model to GPT OSS 20B...")
    try:
        r = requests.post(f"{API_URL}/api/model", json={"model": "openai/gpt-oss-20b"})
        print(f"Model set: {r.status_code}")
    except Exception as e:
        print(f"Failed to connect to API: {e}")
        return

    results = []
    
    # Separate parallelizable prompts and chained prompts
    parallel_prompts = [p for p in PROMPTS if not p.get("is_chain")]
    chain_prompts = [p for p in PROMPTS if p.get("is_chain")]
    
    # Chunk parallel prompts into batches of 10
    chunk_size = 10
    chunks = [parallel_prompts[i:i + chunk_size] for i in range(0, len(parallel_prompts), chunk_size)]
    
    for idx, chunk in enumerate(chunks):
        print(f"Running Parallel Batch {idx+1}/{len(chunks)} ({len(chunk)} prompts)...")
        with ThreadPoolExecutor(max_workers=chunk_size) as executor:
            futures = [executor.submit(run_single_test, item) for item in chunk]
            for future in futures:
                results.append(future.result())
        
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
            
        if idx < len(chunks) - 1 or len(chain_prompts) > 0:
            print("Waiting 60 seconds to avoid NVIDIA rate limits...")
            time.sleep(60)

    if chain_prompts:
        print(f"Running {len(chain_prompts)} chained prompts sequentially...")
        current_session_id = None
        for item in chain_prompts:
            res = run_single_test(item, current_session_id)
            if res.get("session_id"):
                current_session_id = res["session_id"]
            results.append(res)
            
            with open(RESULTS_FILE, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
                
            # Sleep 3 seconds between chain prompts just to be safe
            time.sleep(3)

    print("All tests finished. Generating HTML...")
    generate_html(results)

def generate_html(results):
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NL-to-SQL Batch Test Report</title>
        <style>
            body { font-family: 'Inter', -apple-system, sans-serif; background-color: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }
            h1 { color: #58a6ff; text-align: center; border-bottom: 1px solid #30363d; padding-bottom: 10px; }
            .group-header { background-color: #161b22; padding: 10px; border: 1px solid #30363d; border-radius: 6px; margin-top: 30px; font-size: 1.2em; color: #79c0ff; }
            .test-card { background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px; margin-top: 10px; padding: 15px; margin-left: 20px; }
            .query-text { font-size: 1.1em; font-weight: bold; color: #e6edf3; margin-bottom: 10px; }
            .badge { display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; margin-bottom: 10px; }
            .badge-ready { background-color: #238636; color: white; }
            .badge-clarify { background-color: #d29922; color: white; }
            .badge-error { background-color: #da3633; color: white; }
            pre { background-color: #161b22; padding: 10px; border-radius: 6px; overflow-x: auto; border: 1px solid #30363d; color: #e6edf3; font-family: Consolas, monospace; }
            .table-wrap { overflow-x: auto; margin-top: 10px; }
            table { border-collapse: collapse; width: 100%; font-size: 0.9em; }
            th, td { border: 1px solid #30363d; padding: 8px; text-align: left; }
            th { background-color: #21262d; }
            .time { font-size: 0.8em; color: #8b949e; float: right; }
        </style>
    </head>
    <body>
        <h1>NL-to-SQL Batch Test Report (GPT OSS 20B)</h1>
    """

    groups = {}
    for r in results:
        groups.setdefault(r['group'], []).append(r)

    for g_name, items in groups.items():
        html += f'<div class="group-header">{g_name}</div>'
        for r in items:
            state = r.get('state', 'unknown')
            badge_class = "badge-error"
            if state == "query_ready": badge_class = "badge-ready"
            elif state == "awaiting_clarification": badge_class = "badge-clarify"

            html += f'''
            <div class="test-card">
                <div class="time">{r.get('time_sec', 0)}s</div>
                <div class="query-text">"{r['query']}"</div>
                <div class="badge {badge_class}">{str(state).upper()}</div>
            '''

            if r.get("error"):
                html += f'<div><strong style="color:#da3633;">Error:</strong> {r["error"]}</div>'

            if state == "awaiting_clarification" and r.get("clarification_questions"):
                html += "<div><strong>Planner Questions:</strong><ul>"
                for q in r["clarification_questions"]:
                    html += f"<li>{q.get('question_text', '')}</li>"
                html += "</ul></div>"
            
            if r.get("sql"):
                html += f'<div><strong>Generated SQL:</strong><pre>{r["sql"]}</pre></div>'
                
            if r.get("debug_prompt"):
                html += f'<details><summary style="cursor:pointer; color:#79c0ff; margin-bottom:5px;"><strong>Show LLM Prompt</strong></summary><pre style="white-space: pre-wrap;">{r["debug_prompt"]}</pre></details>'
                
            if r.get("raw_llm_output"):
                html += f'<details><summary style="cursor:pointer; color:#79c0ff; margin-bottom:5px;"><strong>Show LLM Raw Output / Reasoning</strong></summary><pre style="white-space: pre-wrap;">{r["raw_llm_output"]}</pre></details>'
                
            if r.get("data_preview") and isinstance(r["data_preview"], list) and len(r["data_preview"]) > 0:
                html += '<div><strong>Data Preview (Top 5 rows):</strong><div class="table-wrap"><table><tr>'
                keys = r["data_preview"][0].keys()
                for k in keys: html += f"<th>{k}</th>"
                html += "</tr>"
                for row in r["data_preview"]:
                    html += "<tr>"
                    for k in keys: html += f"<td>{row.get(k, '')}</td>"
                    html += "</tr>"
                html += "</table></div></div>"
            elif state == "query_ready":
                html += "<div><em>No data returned (0 rows)</em></div>"
            
            html += "</div>"

    html += """
    </body>
    </html>
    """

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML Report generated at: {HTML_FILE}")

if __name__ == "__main__":
    run_test()
