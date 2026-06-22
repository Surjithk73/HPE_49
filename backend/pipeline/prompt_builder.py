"""
Prompt Builder for QueryCraft
Assembles the final LLM prompt from components.
"""
from typing import List, Dict
import sys
import os
import yaml

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
                     few_shots: List[Dict] = None, target_db: str = "macht413") -> str:
        """
        Build the complete LLM prompt.
        
        Args:
            normalized_query: Normalized query text
            schema_context: Filtered schema DDL from schema linker
            few_shots: List of example queries (optional)
            target_db: Target database schema prefix
            
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
                
                # Dynamically inject the actual target database into the few shots
                sql = sql.replace('macht413.', f"{target_db}.")
                
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
            
        # Load and format database bounds
        bounds_section = ""
        bounds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema_store', 'database_bounds.yaml')
        if os.path.exists(bounds_path):
            with open(bounds_path, 'r', encoding='utf-8') as f:
                bounds_data = yaml.safe_load(f)
                
            db_bounds = bounds_data.get('database_bounds', {}).get(target_db, {})
            if db_bounds:
                bounds_str = "\n".join([f"  - Table {t}: " + ", ".join([f"{k} bounds: {v[0]} to {v[1]}" for k, v in cols.items()]) for t, cols in db_bounds.items()])
                bounds_section = f"\nARRAY COLUMN BOUNDS FOR {target_db.upper()}:\nWhen expanding columns with [n], use these index limits to generate the actual SQL columns (e.g. if bounds are 0 to 7, expand to col0, col1... col7):\n{bounds_str}\n"
        
        # Assemble the complete prompt using the refactored layout
        prompt = f"""You are a SQL expert for HPE NonStop performance monitoring systems.
Generate a single valid PostgreSQL SELECT query for the schema '{target_db}'.

OUTPUT CONTRACT:
1. You MUST output a `<thought>` block explaining your reasoning and explicitly mapping requested metrics to the specific schema tables/columns.
2. If a requested metric does not exist in the schema, explicitly state in your `<thought>` block which substitute column you chose or how you derived it, or state that the metric is being omitted.
3. Immediately after the `<thought>` block, output ONLY the raw SQL query wrapped in standard markdown code fences (```sql\n...\n```). Do not output any other text.
4. Only SELECT statements. No DDL/DML.
5. Always qualify tables: {target_db}.table_name.
6. Only use columns shown in the schema context; never invent column names.
7. Always include LIMIT {self.max_rows} unless a smaller limit is specified.

FORMULA REFERENCE LEGEND:
The `delta_time` column represents the measurement interval and is measured in MICROSECONDS. 
When computing metrics, you must account for multiple intervals/CPUs in your denominator.
Define `base_time_us` = (MAX(delta_time) * COUNT(DISTINCT from_timestamp))
(NOTE: If normalizing metrics with `ipus`, redefine `base_time_us` = SUM(delta_time * ipus) instead)
Apply these formulas based on the counter tags in the schema:
- [Busy counter]       percentage  = col * 100.0 / NULLIF(base_time_us, 0)
- [Queue counter]      avg queue   = col * 1.0   / NULLIF(base_time_us, 0)
- [Queue-Busy counter] percentage  = col * 100.0 / NULLIF(base_time_us, 0)
- [Incrementing counter] rate/sec  = col * 1000000.0 / NULLIF(base_time_us, 0)
- [Accumulating counter] bytes/sec = col * 1000000.0 / NULLIF(base_time_us, 0)
- [Response-time counter] avg time = col / NULLIF(transaction_count_col, 0)
- [Lockwait counter]  avg wait µs  = col / NULLIF(requests_blocked, 0)
- [Snapshot counter]  use directly — no rate conversion needed.

AGGREGATION & MATH RULES:
- HIGHEST PRIORITY: The FEW-SHOT EXAMPLES provided below are curated by experts (HPT). If a few-shot example contradicts the FORMULA REFERENCE LEGEND or any other rule, the few-shot example STRICTLY OVERRIDES the rigid rules. Always follow the patterns in the examples first!
- If a specific formula is provided directly in the schema comment for a column, it strictly overrides the global FORMULA REFERENCE LEGEND.
- When calculating Queue lengths or ratios that may result in very small decimals, explicitly CAST the final result to NUMERIC(10,4) so it does not truncate to 0.
- When computing process-category breakdowns from {target_db}.proc grouped by cpu_num, use SUM(CASE WHEN ...) for the numerator and `base_time_us` for the denominator.
- Use from_timestamp / to_timestamp for time filtering.

CROSS-TABLE & JOIN RULES:
- CRITICAL: The from_timestamp values have microsecond precision and DO NOT match exactly across tables. You MUST use DATE_TRUNC('second', from_timestamp) on BOTH sides of timestamp join conditions. Direct equality joins will return zero rows.
- CRITICAL: When joining 3 or more tables that each have many rows, ALWAYS use CTEs to pre-aggregate each table down to (system_name, ts) first, then join the small aggregated results.

SCHEMA CONTEXT:
{schema_context}
{bounds_section}
{few_shot_section}
USER REQUEST:
{normalized_query}"""
        
        return prompt
    
    def build_spec_prompt(
        self,
        spec,
        schema_context: str,
        few_shots: List[Dict] = None,
        target_db: str = "macht413",
        dialect: str = "postgres",
    ) -> str:
        """
        Build a SQL_GENERATOR prompt from a completed IntentSpec.

        Uses the same structure as build_prompt() but replaces the raw user
        query with a structured intent block. The dialect is injected into
        the system instruction so the model targets the right SQL variant.
        """
        from pipeline.intent_spec import IntentSpec
        spec_block = spec.to_prompt_block() if hasattr(spec, "to_prompt_block") else str(spec)

        _DIALECT_NOTES = {
            "postgres": "Use standard PostgreSQL syntax. LIMIT n is correct.",
            "sqlmx":    "Use HPE NonStop SQL/MX syntax. Use [FIRST n] instead of LIMIT n.",
            "sqlmp":    "Use HPE NonStop SQL/MP syntax. Use [FIRST n] instead of LIMIT n.",
        }
        dialect_note = _DIALECT_NOTES.get(dialect.lower(), f"Dialect: {dialect}.")

        # Reuse build_prompt() with the spec block as the "query" — the spec
        # block already contains structured intent; the system instruction adds
        # the dialect note at the top.
        base_prompt = self.build_prompt(
            normalized_query=spec_block,
            schema_context=schema_context,
            few_shots=few_shots,
            target_db=target_db,
        )

        # Inject dialect note right after the opening system instruction line
        dialect_line = f"\nSQL DIALECT: {dialect_note}\n"
        base_prompt = base_prompt.replace(
            f"Generate a single valid PostgreSQL SELECT query for the schema '{target_db}'.",
            f"Generate a single valid SQL SELECT query for the schema '{target_db}'.\n{dialect_note}",
        )
        return base_prompt

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
    assert "OUTPUT CONTRACT:" in prompt
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
