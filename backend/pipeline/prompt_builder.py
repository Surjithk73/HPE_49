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
                sql = sql.replace('%db%.', f"{target_db}.")
                
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

FORMULA REFERENCE LEGEND (Use as fallback if not demonstrated in EXAMPLES):
The `delta_time` column represents the measurement interval and is measured in MICROSECONDS. 
When computing metrics, you must account for multiple intervals/CPUs in your denominator.
Define `base_time_us` = (MAX(delta_time) * COUNT(DISTINCT from_timestamp))
Apply these formulas based on the counter tags in the schema ONLY when the calculation isn't obvious from the examples:
- [Busy counter]       percentage  = col * 100.0 / NULLIF(base_time_us, 0)
- [Queue counter]      avg queue   = col * 1.0   / NULLIF(base_time_us, 0)
- [Queue-Busy counter] percentage  = col * 100.0 / NULLIF(base_time_us, 0)
- [Incrementing counter] rate/sec  = col * 1000000.0 / NULLIF(base_time_us, 0)
- [Accumulating counter] bytes/sec = col * 1000000.0 / NULLIF(base_time_us, 0)
- [Response-time counter] avg time = col / NULLIF(transaction_count_col, 0)
- [Lockwait counter]  avg wait µs  = col / NULLIF(requests_blocked, 0)
- [Snapshot counter]  use directly — no rate conversion needed.

AGGREGATION & MATH RULES:
- If a specific formula is provided directly in the schema comment for a column, it strictly overrides the global FORMULA REFERENCE LEGEND.
- When calculating Queue lengths or ratios that may result in very small decimals, consider explicitly CASTing the final result to NUMERIC(10,4) if necessary.
- When computing process-category breakdowns from {target_db}.proc grouped by cpu_num, use SUM(CASE WHEN ...) for the numerator.
- Use from_timestamp / to_timestamp for time filtering.

CROSS-TABLE & JOIN RULES:
- The from_timestamp values have microsecond precision and DO NOT match exactly across tables. You generally MUST use DATE_TRUNC('second', from_timestamp) on BOTH sides of timestamp join conditions unless instructed otherwise by an example.
- When joining 3 or more tables that each have many rows, consider using CTEs to pre-aggregate if it avoids multiplying rows.

CRITICAL INSTRUCTION ON EXAMPLES: 
The EXAMPLES section contains the highest priority instructions. The behavior, formulas, and structural patterns (like whether or not to use CTEs, what columns to include, and whether to cast) demonstrated in the EXAMPLES completely SUPERSEDE the rules above. Only apply the fallback rules if the examples do not cover the requested behavior.

SCHEMA CONTEXT:
{schema_context}
{bounds_section}
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

    def build_refinement_prompt(
        self,
        original_query: str,
        current_sql: str,
        refinement_instruction: str,
        schema_context: str,
        few_shots: List[Dict] = None,
        target_db: str = "macht413",
    ) -> str:
        """
        Build a prompt that rewrites an existing SQL query based on a plain-English
        refinement instruction from the user.

        The full pipeline (normalize → schema link → few-shots) is run again so
        the model always has fresh context. The original question and current SQL
        are injected as additional context so the model understands what already
        works and only applies the targeted change.

        Args:
            original_query:         The original natural language query.
            current_sql:            The SQL that was already generated.
            refinement_instruction: Plain-English change the user wants (e.g. 'filter to CPU 0').
            schema_context:         Filtered schema DDL from schema linker.
            few_shots:              Retrieved few-shot examples.
            target_db:              Target database schema prefix.

        Returns:
            Complete prompt string for the refinement LLM call.
        """
        base_prompt = self.build_prompt(
            normalized_query=original_query,
            schema_context=schema_context,
            few_shots=few_shots or [],
            target_db=target_db,
        )

        refinement_context = f"""
REFINEMENT CONTEXT:
The user previously asked: "{original_query}"
You generated this SQL, which executed successfully:
```sql
{current_sql}
```

The user now wants you to refine it with the following instruction:
"{refinement_instruction}"

Apply ONLY the requested change. Keep all other aspects of the SQL identical to the current SQL above unless the refinement instruction explicitly changes them.
Output your reasoning in a `<thought>` block, then output the refined SQL in a ```sql block.
"""
        return base_prompt + refinement_context



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
    print("[OK] Basic prompt structure correct")
    
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
    print("[OK] Few-shot examples included correctly")
    
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
    print("[OK] Retry prompt structure correct")
    
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
    print("[OK] Custom max_rows injected correctly")
    
    print("\n" + "=" * 80)
    print("[OK] All Prompt Builder tests passed!")
