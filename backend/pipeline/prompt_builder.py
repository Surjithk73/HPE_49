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
                    f"OUTPUT:\n{sql}"
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
- Output ONLY the raw SQL query. No explanation, no markdown, no backticks.
- Only SELECT statements. No INSERT, UPDATE, DELETE, DROP, ALTER, or any DDL.
- Always qualify table names: macht413.table_name
- Only use columns listed in the schema context below.
- Use from_timestamp and to_timestamp for any time-based filtering.
- CRITICAL — joining across tables: from_timestamp values are microsecond-precision and DO NOT match exactly between tables (e.g. cpu vs disc samples are offset by a few milliseconds). NEVER use `a.from_timestamp = b.from_timestamp` in a JOIN — it will return zero rows. Instead, either (a) omit from_timestamp from the join predicate and join on (system_name, cpu_num, ...) with aggregation, or (b) bucket the timestamp on both sides via `date_trunc('second', from_timestamp)` before joining. Pre-aggregating each side in a CTE before the join is usually cleanest.
- Always include LIMIT {self.max_rows} unless a smaller limit is specified.
- IMPORTANT: When using ORDER BY, only order by actual column names from the table, NOT by aliases defined in SELECT.
- If you need to order by a calculated value, repeat the calculation in ORDER BY instead of using the alias.
- For disc table cache metrics: The disc table has 8 cache levels (c0 through c7). When calculating cache statistics, you MUST include ALL 8 levels (c0_hits + c0_misses + c1_hits + c1_misses + ... + c7_hits + c7_misses). Do NOT simplify to just c0 or a subset of levels.
- CRITICAL: You MUST always include column names in your SELECT clause. NEVER generate "SELECT FROM table" without columns. If you cannot find a requested column in the schema, use only the columns that exist and skip the missing ones.

SCHEMA CONTEXT:
{schema_context}
{few_shot_section}
USER REQUEST:
{normalized_query}

SQL:"""
        
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
Please fix the SQL and output only the corrected query.

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
    assert "SQL:" in prompt
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
    assert "OUTPUT:\nSELECT cpu_num" in prompt_with_examples
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
