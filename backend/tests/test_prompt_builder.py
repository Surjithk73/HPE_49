"""
Integration tests for Prompt Builder with Schema Linker
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pipeline.schema_loader import load_schema
from pipeline.normalizer import QueryNormalizer
from pipeline.schema_linker import SchemaLinker
from pipeline.prompt_builder import PromptBuilder


def test_full_pipeline():
    """Test the complete pipeline from query to prompt."""
    print("\n" + "=" * 80)
    print("INTEGRATION TEST: Normalizer → Schema Linker → Prompt Builder")
    print("=" * 80)
    
    # Initialize components
    loader = load_schema('../schema_store/enriched_schema.yaml')
    schema = loader.get_schema()
    
    normalizer = QueryNormalizer()
    linker = SchemaLinker(schema)
    builder = PromptBuilder()
    
    # Test queries
    test_cases = [
        {
            "query": "Show average CPU busy time per CPU",
            "expected_domain": "cpu",
            "expected_tables": ["cpu"]
        },
        {
            "query": "List disk reads and writes per device",
            "expected_domain": "disc",
            "expected_tables": ["disc"]
        },
        {
            "query": "Compare CPU and process utilization",
            "expected_domain": "multi",
            "expected_tables": ["cpu", "proc"]  # Should include both
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n[Test Case {i}] Query: '{test['query']}'")
        print("-" * 80)
        
        # Step 1: Normalize
        norm_result = normalizer.normalize(test['query'])
        normalized_text = norm_result['normalized_text']
        domain = norm_result['domain_category']
        
        print(f"Normalized: '{normalized_text}'")
        print(f"Domain: {domain}")
        
        assert domain == test['expected_domain'], f"Expected domain {test['expected_domain']}, got {domain}"
        
        # Step 2: Link schema
        schema_context = linker.link_schema(normalized_text, domain)
        
        print(f"\nSchema Context ({len(schema_context)} chars):")
        print(schema_context[:300] + "..." if len(schema_context) > 300 else schema_context)
        
        # Verify expected tables are in context
        for table in test['expected_tables']:
            assert f"macht413.{table}" in schema_context, f"Expected table {table} not in schema context"
        
        # Step 3: Build prompt
        prompt = builder.build_prompt(
            normalized_query=normalized_text,
            schema_context=schema_context,
            few_shots=[]
        )
        
        print(f"\nPrompt ({len(prompt)} chars):")
        print(prompt[:400] + "..." if len(prompt) > 400 else prompt)
        
        # Verify prompt structure
        assert "You are a SQL expert" in prompt
        assert "STRICT RULES:" in prompt
        assert "SCHEMA CONTEXT:" in prompt
        assert normalized_text in prompt
        assert "SQL:" in prompt
        assert "EXAMPLE QUERIES:" not in prompt  # No few-shots provided
        
        print(f"✓ Test case {i} passed")
    
    print("\n" + "=" * 80)
    print("✓ All integration tests passed!")
    print("=" * 80)


def test_with_few_shots():
    """Test prompt building with few-shot examples."""
    print("\n" + "=" * 80)
    print("TEST: Prompt Builder with Few-Shot Examples")
    print("=" * 80)
    
    loader = load_schema('../schema_store/enriched_schema.yaml')
    schema = loader.get_schema()
    
    normalizer = QueryNormalizer()
    linker = SchemaLinker(schema)
    builder = PromptBuilder()
    
    # Normalize query
    norm_result = normalizer.normalize("Show CPU busy time")
    normalized_text = norm_result['normalized_text']
    domain = norm_result['domain_category']
    
    # Link schema
    schema_context = linker.link_schema(normalized_text, domain)
    
    # Build prompt with few-shots
    few_shots = [
        {
            "query": "Show average CPU busy time per CPU",
            "sql": "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000;"
        }
    ]
    
    prompt = builder.build_prompt(
        normalized_query=normalized_text,
        schema_context=schema_context,
        few_shots=few_shots
    )
    
    print(f"Prompt with few-shots ({len(prompt)} chars):")
    print(prompt[:600] + "..." if len(prompt) > 600 else prompt)
    
    # Verify few-shot section is present
    assert "EXAMPLE QUERIES:" in prompt
    assert "-- Query: Show average CPU busy time per CPU" in prompt
    assert "-- SQL: SELECT cpu_num" in prompt
    
    print("\n✓ Few-shot examples correctly included in prompt")
    print("=" * 80)


def test_retry_prompt():
    """Test retry prompt generation."""
    print("\n" + "=" * 80)
    print("TEST: Retry Prompt Generation")
    print("=" * 80)
    
    builder = PromptBuilder()
    
    original_prompt = """You are a SQL expert for HPE NonStop performance monitoring systems.
Generate a single valid PostgreSQL SELECT query for the schema 'macht413'.

STRICT RULES:
- Output ONLY the raw SQL query. No explanation, no markdown, no backticks.

SCHEMA CONTEXT:
-- Table: macht413.cpu
CREATE TABLE macht413.cpu (
    cpu_num BIGINT,
    cpu_busy_time BIGINT
);

USER REQUEST:
show cpu busy time

SQL:"""
    
    failed_sql = "SELECT fake_column FROM macht413.cpu"
    error = "Column 'fake_column' does not exist in macht413.cpu"
    
    retry_prompt = builder.build_retry_prompt(
        original_prompt=original_prompt,
        failed_sql=failed_sql,
        error=error
    )
    
    print(f"Retry prompt ({len(retry_prompt)} chars):")
    print(retry_prompt)
    
    # Verify retry prompt contains all necessary parts
    assert original_prompt in retry_prompt
    assert "The SQL you generated was invalid" in retry_prompt
    assert error in retry_prompt
    assert failed_sql in retry_prompt
    assert "Please fix the SQL" in retry_prompt
    
    print("\n✓ Retry prompt correctly generated")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_full_pipeline()
        test_with_few_shots()
        test_retry_prompt()
        
        print("\n" + "=" * 80)
        print("✓✓✓ ALL PROMPT BUILDER TESTS PASSED ✓✓✓")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
