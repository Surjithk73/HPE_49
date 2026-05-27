"""
Prompt Builder for QueryCraft
Assembles the final LLM prompt from components.
"""
from typing import List, Dict
import sys
import os

# Add parent directory to path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Try to import MAX_ROWS from config, fallback to default if config validation fails
try:
    from config import MAX_ROWS
except (ValueError, ImportError):
    MAX_ROWS = 10000


class PromptBuilder:
    """Builds prompts for the LLM engine."""
    
    def __init__(self, max_rows: int = MAX_ROWS):
        """
        Initialize the prompt builder.
        
        Args:
            max_rows: Maximum rows to return (injected from config)
        """
        self.max_rows = max_rows
    
    def build_prompt(self, normalized_query: str, schema_context: str, 
                     few_shots: List[Dict] = None) -> str:
        """
        Build the complete LLM prompt.
        
        Args:
            normalized_query: Normalized query text
            schema_context: Filtered schema DDL from schema linker
            few_shots: List of example queries (optional)
            
        Returns:
            Complete prompt string ready for LLM
        """
        if few_shots is None:
            few_shots = []
        
        # Build few-shot examples section as explicit input/output pairs.
        # Gemini follows the pattern more reliably when each example is a
        # labeled INPUT/OUTPUT block separated by a delimiter, rather than
        # interleaved SQL comments which the model can mistake for schema.
        few_shot_section = ""
        if few_shots:
            blocks = []
            for i, example in enumerate(few_shots, 1):
                query = example.get('query', '').strip()
                sql = example.get('sql', '').strip()
                blocks.append(
                    f"### Example {i}\n"
                    f"INPUT: {query}\n"
                    f"OUTPUT:\n<thought>\nMapping metrics for: {query}\n</thought>\n```sql\n{sql}\n```"
                )
            few_shot_section = (
                "\nEXAMPLES (follow this INPUT/OUTPUT pattern exactly):\n"
                + "\n\n---\n\n".join(blocks)
                + "\n"
            )
        
        # Assemble the complete prompt using the exact template from Project_Overview.md
        prompt = f"""You are a SQL expert for HPE NonStop performance monitoring systems.
Generate a single valid PostgreSQL SELECT query for the schema 'macht413'.

STRICT RULES:
- You must output a brief `<thought>` block before writing the SQL. Use this block to explicitly map the user's requested metrics to the specific schema tables/columns and explain your reasoning.
- After the `<thought>` block, output ONLY the raw SQL query wrapped in standard markdown code fences (```sql\n...\n```). No other explanation.
- Only SELECT statements. No DDL/DML.
- Always qualify tables: macht413.table_name.
- Only use columns shown in the schema context; never invent column names.
- Use from_timestamp / to_timestamp for time filtering.

COUNTER MATH RULES (apply to every table — delta_time is in microseconds):
- delta_time is the SAME value for every row in the same measurement interval.
  NEVER use SUM(delta_time) as a denominator — it inflates by row count and produces near-zero results.
  When grouping rows (GROUP BY cpu_num, device_name, etc.) always use MAX(delta_time) as the denominator.
- [Busy counter]       percentage  = col * 100.0 / NULLIF(MAX(delta_time), 0)
- [Queue counter]      avg queue   = col * 1.0   / NULLIF(MAX(delta_time), 0)
- [Queue-Busy counter] percentage  = col * 100.0 / NULLIF(MAX(delta_time), 0)
- [Incrementing counter] rate/sec  = col * 1000000.0 / NULLIF(MAX(delta_time), 0)
- [Accumulating counter] bytes/sec = col * 1000000.0 / NULLIF(MAX(delta_time), 0)
- [Response-time counter] avg time = col / NULLIF(transaction_count_col, 0)
- [Lockwait counter]  avg wait µs  = col / NULLIF(requests_blocked, 0)
- [Snapshot counter]  use directly — no rate conversion needed.
- The column comments in SCHEMA CONTEXT show each column's counter type and formula.
  Always follow the formula shown there.

AGGREGATION RULES:
- When computing process-category breakdowns from macht413.proc grouped by cpu_num,
  use SUM(CASE WHEN ...) for the numerator and MAX(delta_time) for the denominator.
- When a query asks for "percentage of interval" or "utilization %", always divide
  the Busy/Queue counter by MAX(delta_time), never by SUM(delta_time).
- For cache hit ratios: hits * 100.0 / NULLIF(hits + misses, 0) — do NOT involve delta_time.
- For lock wait averages: lockwait_time / NULLIF(requests_blocked, 0).

CROSS-TABLE RULES:
- CRITICAL — cross-table joins on timestamps: The from_timestamp values have microsecond precision and DO NOT match exactly across tables. You MUST use DATE_TRUNC('second', from_timestamp) on BOTH sides of timestamp join conditions. Direct equality joins will return zero rows.
- CRITICAL — multi-table aggregation performance: When joining 3 or more tables that each have many rows (proc has 110k rows, file has 61k rows), ALWAYS use CTEs to pre-aggregate each table down to (system_name, ts) first, then join the small aggregated results. Flat multi-table joins with DATE_TRUNC will time out. Pattern: WITH t1 AS (SELECT DATE_TRUNC('second', from_timestamp) AS ts, system_name, AGG(...) FROM macht413.table GROUP BY 1,2), ... SELECT ... FROM t1 LEFT JOIN t2 ON t1.system_name=t2.system_name AND t1.ts=t2.ts

- Intent Mapping: If a user asks for a metric using non-technical terms (e.g., "bottleneck", "sluggish"), map their intent to the closest matching column provided in the SCHEMA CONTEXT. If absolutely no logical match exists, use the most relevant primary metric for that table (e.g., cpu_busy_time for cpu).
- Always include LIMIT {self.max_rows} unless a smaller limit is specified.

SCHEMA CONTEXT:
{schema_context}
{few_shot_section}
USER REQUEST:
{normalized_query}"""
        
        return prompt
    
    def build_retry_prompt(self, original_prompt: str, failed_sql: str, error: str) -> str:
        """
        Build a retry prompt after validation failure.
        
        Args:
            original_prompt: The original prompt that was sent
            failed_sql: The SQL that failed validation
            error: The validation error message
            
        Returns:
            Retry prompt with error feedback
        """
        retry_prompt = f"""{original_prompt}

The SQL you generated was invalid. Error: {error}
Generated SQL: {failed_sql}
Please fix the SQL. Output your reasoning in a `<thought>` block, followed by the corrected SQL wrapped in ```sql\n...\n```.

SQL:"""
        
        return retry_prompt


# Test the prompt builder
if __name__ == "__main__":
    print("Testing Prompt Builder...")
    print("=" * 80)
    
    # Test 1: Basic prompt with schema context, no few-shots
    print("\n[Test 1] Basic prompt without few-shots")
    print("-" * 80)
    
    builder = PromptBuilder()
    
    sample_schema = """-- Table: macht413.cpu
-- Purpose: CPU utilization and performance metrics
CREATE TABLE macht413.cpu (
    system_name TEXT  -- System identifier,
    cpu_num BIGINT  -- CPU number,
    from_timestamp TIMESTAMP  -- Measurement start time,
    to_timestamp TIMESTAMP  -- Measurement end time,
    cpu_busy_time BIGINT  -- CPU busy time in microseconds
);"""
    
    prompt = builder.build_prompt(
        normalized_query="show average cpu_busy_time per cpu",
        schema_context=sample_schema,
        few_shots=[]
    )
    
    print(prompt)
    print("\n" + "=" * 80)
    
    # Verify prompt structure
    assert "You are a SQL expert" in prompt
    assert "STRICT RULES:" in prompt
    assert "SCHEMA CONTEXT:" in prompt
    assert "USER REQUEST:" in prompt
    assert f"LIMIT {MAX_ROWS}" in prompt
    assert "EXAMPLES" not in prompt  # Should be omitted when empty
    print("✓ Basic prompt structure correct")
    
    # Test 2: Prompt with few-shot examples
    print("\n[Test 2] Prompt with few-shot examples")
    print("-" * 80)
    
    few_shots = [
        {
            "query": "Show CPU busy time per CPU",
            "sql": "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000;"
        },
        {
            "query": "List all systems",
            "sql": "SELECT DISTINCT system_name FROM macht413.cpu LIMIT 10000;"
        }
    ]
    
    prompt_with_examples = builder.build_prompt(
        normalized_query="show total cpu busy time",
        schema_context=sample_schema,
        few_shots=few_shots
    )
    
    print(prompt_with_examples)
    print("\n" + "=" * 80)
    
    # Verify few-shot section
    assert "EXAMPLES (follow this INPUT/OUTPUT pattern exactly):" in prompt_with_examples
    assert "### Example 1" in prompt_with_examples
    assert "INPUT: Show CPU busy time per CPU" in prompt_with_examples
    assert "OUTPUT:\n<thought>" in prompt_with_examples
    assert "```sql\nSELECT cpu_num" in prompt_with_examples
    assert "### Example 2" in prompt_with_examples
    print("✓ Few-shot examples included correctly")
    
    # Test 3: Retry prompt
    print("\n[Test 3] Retry prompt with error feedback")
    print("-" * 80)
    
    failed_sql = "SELECT fake_column FROM macht413.cpu"
    error = "Column 'fake_column' does not exist in macht413.cpu"
    
    retry_prompt = builder.build_retry_prompt(
        original_prompt=prompt,
        failed_sql=failed_sql,
        error=error
    )
    
    print(retry_prompt)
    print("\n" + "=" * 80)
    
    # Verify retry prompt structure
    assert "The SQL you generated was invalid" in retry_prompt
    assert error in retry_prompt
    assert failed_sql in retry_prompt
    assert "Please fix the SQL" in retry_prompt
    print("✓ Retry prompt structure correct")
    
    # Test 4: Custom max_rows
    print("\n[Test 4] Custom max_rows value")
    print("-" * 80)
    
    custom_builder = PromptBuilder(max_rows=5000)
    custom_prompt = custom_builder.build_prompt(
        normalized_query="test query",
        schema_context=sample_schema
    )
    
    assert "LIMIT 5000" in custom_prompt
    assert "LIMIT 10000" not in custom_prompt
    print("✓ Custom max_rows injected correctly")
    
    print("\n" + "=" * 80)
    print("✓ All Prompt Builder tests passed!")
