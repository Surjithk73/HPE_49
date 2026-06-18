import os
import sys
import time
import yaml
import json
import re
import concurrent.futures
from openai import OpenAI
from groq import Groq
import google.generativeai as genai
import psycopg2
import sqlglot

# Setup paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pipeline.schema_loader import load_schema
from pipeline.normalizer import QueryNormalizer
from pipeline.schema_linker import SchemaLinker
from pipeline.prompt_builder import PromptBuilder
from pipeline.few_shot_retriever import FewShotRetriever
from pipeline.validator import SQLValidator
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, SCHEMA_YAML_PATH, FEW_SHOTS_PATH

# Temporary hardcoded API keys
NVIDIA_API_KEY = "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"
GROQ_API_KEY = "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"

# Test set path
TEST_SET_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "few_shots",
    "model_evaluation_test_set.yaml"
)

# Target DB
TARGET_DB = "machd500"

def load_test_cases():
    with open(TEST_SET_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("test_set", [])

def extract_sql(text):
    """Robust SQL extraction from LLM response."""
    if not text:
        return ""
    text = text.strip()
    
    # Try ```sql ... ```
    sql_fence_pattern = r'```sql\s*(.*?)\s*```'
    match = re.search(sql_fence_pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
        
    # Try ``` ... ```
    fence_pattern = r'```\s*(.*?)\s*```'
    match = re.search(fence_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
        
    # If no fences, find the last thought block (if any) and take everything after it
    if "</thought>" in text:
        parts = text.split("</thought>")
        text_after = parts[-1].strip()
        # Find if there's any SELECT in text_after
        if "select" in text_after.lower():
            return text_after
            
    # Fallback to the whole text
    return text

def query_nvidia_model(model_name, prompt, temperature, top_p):
    """Query NVIDIA NIM API."""
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_API_KEY
    )
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            top_p=top_p,
            max_tokens=4096,
            stream=False
        )
        content = completion.choices[0].message.content or ""
        reasoning = getattr(completion.choices[0].message, "reasoning_content", None)
        return {"content": content, "reasoning": reasoning, "error": None}
    except Exception as e:
        return {"content": "", "reasoning": None, "error": str(e)}

def query_groq_model(model_name, prompt, temperature, top_p):
    """Query Groq API."""
    client = Groq(api_key=GROQ_API_KEY)
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            top_p=top_p,
            max_tokens=4096,
            stream=False
        )
        content = completion.choices[0].message.content or ""
        # Groq's qwen models might support reasoning_content or reasoning in delta/choice
        reasoning = getattr(completion.choices[0].message, "reasoning", None)
        return {"content": content, "reasoning": reasoning, "error": None}
    except Exception as e:
        return {"content": "", "reasoning": None, "error": str(e)}

def query_gemini_model(model_name, prompt, temperature, top_p):
    """Query Gemini API."""
    try:
        from config import GEMINI_API_KEY
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name)
        
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=4096,
        )
        response = model.generate_content(prompt, generation_config=generation_config)
        content = response.text or ""
        return {"content": content, "reasoning": None, "error": None}
    except Exception as e:
        return {"content": "", "reasoning": None, "error": str(e)}

def evaluate_single_query(test_case, model_info, prompt, schema_validator):
    """Evaluate a single test case against a model."""
    model_name = model_info["name"]
    provider = model_info["provider"]
    temperature = model_info["temperature"]
    top_p = model_info["top_p"]
    
    print(f"  Querying {model_name} for Case {test_case['id']}...")
    
    t0 = time.time()
    if provider == "nvidia":
        res = query_nvidia_model(model_name, prompt, temperature, top_p)
    elif provider == "groq":
        res = query_groq_model(model_name, prompt, temperature, top_p)
    elif provider == "google":
        res = query_gemini_model(model_name, prompt, temperature, top_p)
    else:
        res = {"content": "", "reasoning": None, "error": f"Unknown provider: {provider}"}
    latency = time.time() - t0
    
    if res["error"]:
        return {
            "case_id": test_case["id"],
            "prompt": test_case["prompt"],
            "expected_sql": test_case["sql"],
            "raw_output": "",
            "reasoning": "",
            "extracted_sql": "",
            "latency": latency,
            "status": "API_ERROR",
            "reason": f"API request failed: {res['error']}"
        }
        
    raw_content = res["content"]
    reasoning = res["reasoning"] or ""
    extracted_sql = extract_sql(raw_content)
    
    # Try to extract reasoning from thought blocks if not provided in api metadata
    if not reasoning and "<thought>" in raw_content and "</thought>" in raw_content:
        thought_match = re.search(r'<thought>\s*(.*?)\s*</thought>', raw_content, re.DOTALL | re.IGNORECASE)
        if thought_match:
            reasoning = thought_match.group(1).strip()
            
    # Validate the generated SQL
    val = schema_validator.validate(extracted_sql, TARGET_DB)
    if not val.valid:
        return {
            "case_id": test_case["id"],
            "prompt": test_case["prompt"],
            "expected_sql": test_case["sql"],
            "raw_output": raw_content,
            "reasoning": reasoning,
            "extracted_sql": extracted_sql,
            "latency": latency,
            "status": "VALIDATION_FAILED",
            "reason": f"SQL Schema Validation failed: {val.error}"
        }
        
    # Compare with reference SQL
    expected_sql_replaced = test_case["sql"].replace("%db%", TARGET_DB)
    
    # 1. AST comparison
    ast_match = False
    try:
        ast_gen = sqlglot.parse_one(extracted_sql, read="postgres")
        ast_exp = sqlglot.parse_one(expected_sql_replaced, read="postgres")
        if ast_gen == ast_exp:
            ast_match = True
    except Exception:
        pass
        
    # 2. Database Execution comparison (thread-safe local connection)
    exec_match = False
    exec_error = None
    data_diff_reason = None
    
    db_conn = None
    try:
        db_conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        # Get reference rows
        with db_conn.cursor() as cur:
            cur.execute(expected_sql_replaced)
            exp_rows = cur.fetchall()
            exp_cols = [desc[0] for desc in cur.description]
            
        # Get generated rows
        with db_conn.cursor() as cur:
            cur.execute(extracted_sql)
            gen_rows = cur.fetchall()
            gen_cols = [desc[0] for desc in cur.description]
            
        # Compare columns and rows
        missing_cols = [c for c in exp_cols if c not in gen_cols]
        
        if missing_cols and len(exp_cols) == len(gen_cols):
            # Same number of columns, maybe alias mismatch. Try comparing by position.
            filtered_gen_rows = gen_rows
            missing_cols = []  # ignore missing cols, rely on position
        elif missing_cols:
            # Cannot align columns
            data_diff_reason = f"Missing required columns: {missing_cols}"
            filtered_gen_rows = None
        else:
            # All expected columns are present, extract them
            col_indices = [gen_cols.index(c) for c in exp_cols]
            filtered_gen_rows = [tuple(row[i] for i in col_indices) for row in gen_rows]

        if not data_diff_reason:
            if len(exp_rows) != len(filtered_gen_rows):
                data_diff_reason = f"Row count mismatch: expected {len(exp_rows)}, got {len(filtered_gen_rows)}"
            else:
                # Sort for comparison
                def safe_sort_key(row):
                    return tuple(str(val) for val in row)
                sorted_exp = sorted(exp_rows, key=safe_sort_key)
                sorted_gen = sorted(filtered_gen_rows, key=safe_sort_key)
                
                if sorted_exp != sorted_gen:
                    data_diff_reason = "Data content mismatch: rows returned different values"
                else:
                    exec_match = True
                    
                    if len(exp_cols) != len(gen_cols):
                        data_diff_reason = f"Execution match, but generated extra columns. Expected: {exp_cols}, Got: {gen_cols}"
                    elif exp_cols != gen_cols:
                        data_diff_reason = f"Column alias differences: expected {exp_cols}, got {gen_cols}"
    except Exception as e:
        exec_error = str(e)
        if db_conn:
            db_conn.rollback()
    finally:
        if db_conn:
            db_conn.close()
        
    # Determine correctness status
    if ast_match:
        status = "CORRECT"
        reason = "AST Match"
    elif exec_match:
        if data_diff_reason: # Column alias mismatch
            status = "NEAR_CORRECT"
            reason = f"Execution match, but column aliases differ: {data_diff_reason}"
        else:
            status = "CORRECT"
            reason = "Execution Match"
    else:
        status = "INCORRECT"
        if exec_error:
            reason = f"PostgreSQL Execution failed: {exec_error}"
        elif data_diff_reason:
            reason = f"Data mismatch: {data_diff_reason}"
        else:
            reason = "AST and Data mismatch (no database execution error)"
            
    return {
        "case_id": test_case["id"],
        "prompt": test_case["prompt"],
        "expected_sql": expected_sql_replaced,
        "raw_output": raw_content,
        "reasoning": reasoning,
        "extracted_sql": extracted_sql,
        "latency": latency,
        "status": status,
        "reason": reason
    }

def main():
    print("Initializing components...")
    schema_loader = load_schema(SCHEMA_YAML_PATH)
    schema = schema_loader.get_schema()
    normalizer = QueryNormalizer()
    linker = SchemaLinker(schema)
    builder = PromptBuilder()
    validator = SQLValidator(schema)
    
    # Load few shots for the retriever
    with open(FEW_SHOTS_PATH, "r", encoding="utf-8") as f:
        few_shots_data = yaml.safe_load(f)
    few_shots = few_shots_data.get("examples", []) if few_shots_data else []
    retriever = FewShotRetriever(few_shots, persist_path="cache_store")

    
    # Test cases
    test_cases = load_test_cases()
    print(f"Loaded {len(test_cases)} test cases.")
    
    # Build prompt for each test case
    print("Building prompts for all test cases...")
    prompts = []
    for tc in test_cases:
        norm = normalizer.normalize(tc["prompt"])
        norm_text = norm["normalized_text"]
        domain = tc["domain"]
        schema_context = linker.link_schema(norm_text, domain, TARGET_DB)
        top_few_shots = retriever.get_top_k(norm_text, k=3)
        prompt = builder.build_prompt(norm_text, schema_context, top_few_shots, TARGET_DB)
        prompts.append((tc, prompt))
        
    models = [
        {
            "id": "gemini-3.1-flash-lite",
            "name": "gemini-3.1-flash-lite",
            "provider": "google",
            "temperature": 0.2,
            "top_p": 0.8
        },
        {
            "id": "gpt-oss-20b",
            "name": "openai/gpt-oss-20b",
            "provider": "nvidia",
            "temperature": 1.0,
            "top_p": 1.0
        },
        {
            "id": "qwen-80b",
            "name": "qwen/qwen3-next-80b-a3b-instruct",
            "provider": "nvidia",
            "temperature": 0.6,
            "top_p": 0.7
        }
    ]
    
    evaluation_results = {}
    
    for idx, model in enumerate(models):
        print(f"\nEvaluating Model {idx + 1}/{len(models)}: {model['name']}...")
        model_results = []
        
        # Chunk prompts to handle 10 RPM rate limit for Gemini
        chunk_size = 10 if model["provider"] == "google" else len(prompts)
        for i in range(0, len(prompts), chunk_size):
            chunk = prompts[i:i + chunk_size]
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for tc, prompt in chunk:
                    futures.append(
                        executor.submit(evaluate_single_query, tc, model, prompt, validator)
                    )
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        res = future.result()
                        model_results.append(res)
                    except Exception as exc:
                        print(f"  Query generated an exception: {exc}")
            
            if i + chunk_size < len(prompts) and model["provider"] == "google":
                print(f"Rate limit pause: waiting 60 seconds before next batch of {chunk_size}...")
                time.sleep(60)
                    
        # Sort results by case ID
        model_results.sort(key=lambda x: x["case_id"])
        evaluation_results[model["id"]] = {
            "model_info": model,
            "results": model_results
        }

    
    # Write report
    generate_markdown_report(evaluation_results)

def generate_markdown_report(evaluation_results):
    report_content = []
    report_content.append("# Model Evaluation Report: Natural Language to SQL")
    report_content.append(f"**Run Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append(f"**Target Database Schema:** `{TARGET_DB}`\n")
    
    # Summary Table
    report_content.append("## Summary of Model Performance\n")
    report_content.append("| Model | Total | Correct | Near-Correct | Incorrect / Fail | Success % | Avg Latency |")
    report_content.append("|-------|-------|---------|--------------|------------------|-----------|-------------|")
    
    for m_id, data in evaluation_results.items():
        m_info = data["model_info"]
        results = data["results"]
        total = len(results)
        correct = sum(1 for r in results if r["status"] == "CORRECT")
        near = sum(1 for r in results if r["status"] == "NEAR_CORRECT")
        failed = sum(1 for r in results if r["status"] in ["INCORRECT", "VALIDATION_FAILED", "API_ERROR"])
        success_pct = ((correct + near) / total) * 100 if total > 0 else 0
        avg_latency = sum(r["latency"] for r in results) / total if total > 0 else 0
        
        report_content.append(
            f"| `{m_info['name']}` | {total} | {correct} | {near} | {failed} | {success_pct:.1f}% | {avg_latency:.2f}s |"
        )
    report_content.append("\n---\n")
    
    # Detailed breakdown per model
    for m_id, data in evaluation_results.items():
        m_info = data["model_info"]
        results = data["results"]
        
        report_content.append(f"## Evaluation Details: `{m_info['name']}`\n")
        report_content.append("| Case ID | NL Query | Status | Latency | Match Reason / Error |")
        report_content.append("|---------|----------|--------|---------|----------------------|")
        
        for r in results:
            status_emoji = "✅" if r["status"] == "CORRECT" else ("🟡" if r["status"] == "NEAR_CORRECT" else "❌")
            report_content.append(
                f"| {r['case_id']} | `{r['prompt']}` | {status_emoji} {r['status']} | {r['latency']:.2f}s | {r['reason']} |"
            )
            
        report_content.append("\n### Missed Queries Analysis\n")
        missed = [r for r in results if r["status"] != "CORRECT"]
        if not missed:
            report_content.append("No missed queries! Perfect execution.")
        else:
            for idx, r in enumerate(missed, 1):
                report_content.append(f"#### {idx}. Case {r['case_id']}: `{r['prompt']}`")
                report_content.append(f"- **Status:** `{r['status']}`")
                report_content.append(f"- **Issue Reason:** {r['reason']}")
                if r["reasoning"]:
                    report_content.append(f"- **Model Thought Process:**\n  ```\n  {r['reasoning']}\n  ```")
                report_content.append(f"- **Expected SQL:**\n  ```sql\n  {r['expected_sql']}\n  ```")
                if r["extracted_sql"]:
                    report_content.append(f"- **Generated SQL:**\n  ```sql\n  {r['extracted_sql']}\n  ```")
                else:
                    report_content.append(f"- **Raw LLM Output:**\n  ```\n  {r['raw_output']}\n  ```")
                report_content.append("")
                
        report_content.append("\n---\n")
        
    report_str = "\n".join(report_content)
    
    # Write to local file
    local_report_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "evaluation_report.md"
    )
    with open(local_report_path, "w", encoding="utf-8") as f:
        f.write(report_str)
    print(f"Markdown report written to: {local_report_path}")
    
    # Also write to artifacts directory
    artifact_dir = r"C:\Users\surji\.gemini\antigravity\brain\54e37be7-cfee-4b7e-982e-dee28e3f005d"
    artifact_report_path = os.path.join(artifact_dir, "evaluation_report.md")
    with open(artifact_report_path, "w", encoding="utf-8") as f:
        f.write(report_str)
    print(f"Artifact report written to: {artifact_report_path}")

if __name__ == "__main__":
    main()
