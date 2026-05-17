"""
LLM Engine for QueryCraft
Handles interaction with Gemini API for SQL generation.
"""
import re
import sys
import os

# Add parent directory to path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from config import GEMINI_API_KEY, GEMINI_MODEL
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except (ValueError, ImportError) as e:
    GEMINI_AVAILABLE = False
    GEMINI_API_KEY = None
    GEMINI_MODEL = "gemini-1.5-flash"
    print(f"Warning: Gemini API not configured: {e}")


class LLMError(Exception):
    """Custom exception for LLM-related errors."""
    pass


class LLMEngine:
    """Handles SQL generation using Gemini API."""
    
    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize the LLM engine.
        
        Args:
            api_key: Gemini API key (defaults to config value)
            model: Model name (defaults to config value)
        """
        self.api_key = api_key or GEMINI_API_KEY
        self.model_name = model or GEMINI_MODEL
        
        if not self.api_key:
            raise LLMError("Gemini API key not configured. Set GEMINI_API_KEY in .env file")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
    
    def generate_sql(self, prompt: str) -> str:
        """
        Generate SQL from a prompt.
        
        Args:
            prompt: Complete prompt string
            
        Returns:
            Raw SQL string
            
        Raises:
            LLMError: If generation fails
        """
        try:
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                raise LLMError("Empty response from LLM")
            
            # Extract and clean SQL
            sql = self._extract_sql(response.text)
            
            return sql
            
        except Exception as e:
            raise LLMError(f"Failed to generate SQL: {str(e)}")
    
    def generate_sql_with_retry(self, prompt: str, validator, prompt_builder, max_retries: int = 2) -> str:
        """
        Generate SQL with automatic retry on validation failure.
        
        Args:
            prompt: Initial prompt string
            validator: SQLValidator instance
            prompt_builder: PromptBuilder instance
            max_retries: Maximum number of retry attempts
            
        Returns:
            Valid SQL string
            
        Raises:
            LLMError: If all retries fail
        """
        last_error = None
        failed_sql = None
        current_prompt = prompt
        
        for attempt in range(max_retries + 1):
            print(f"[LLM] Attempt {attempt + 1}/{max_retries + 1}...")
            
            try:
                # Generate SQL
                sql = self.generate_sql(current_prompt)
                
                # Validate
                result = validator.validate(sql)
                
                if result.valid:
                    print(f"[LLM] ✓ Valid SQL generated on attempt {attempt + 1}")
                    return result.sanitized_sql
                else:
                    print(f"[LLM] ✗ Validation failed: {result.error}")
                    last_error = result.error
                    failed_sql = sql
                    
                    # Build retry prompt if we have attempts left
                    if attempt < max_retries:
                        current_prompt = prompt_builder.build_retry_prompt(
                            original_prompt=prompt,
                            failed_sql=failed_sql,
                            error=last_error
                        )
                    
            except LLMError as e:
                last_error = str(e)
                print(f"[LLM] ✗ Generation failed: {last_error}")
                
                if attempt >= max_retries:
                    break
        
        # All retries exhausted
        raise LLMError(f"Max retries exceeded. Last error: {last_error}")
    
    def _extract_sql(self, response_text: str) -> str:
        """
        Extract SQL from LLM response, removing markdown fences and explanations.
        
        Args:
            response_text: Raw response from LLM
            
        Returns:
            Cleaned SQL string
        """
        # Remove markdown code fences
        text = response_text.strip()
        
        # Pattern 1: ```sql ... ```
        sql_fence_pattern = r'```sql\s*(.*?)\s*```'
        match = re.search(sql_fence_pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Pattern 2: ``` ... ```
        fence_pattern = r'```\s*(.*?)\s*```'
        match = re.search(fence_pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Pattern 3: No fences - return the whole text
        # The LLM should follow instructions to return only SQL
        return text


# Test the LLM engine (requires API key)
if __name__ == "__main__":
    print("Testing LLM Engine...")
    print("=" * 80)
    
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        print("✗ Gemini API not configured")
        print("To test the LLM engine:")
        print("1. Set GEMINI_API_KEY in backend/.env")
        print("2. Run: python llm_engine.py")
        sys.exit(1)
    
    try:
        # Initialize engine
        engine = LLMEngine()
        print(f"✓ LLM Engine initialized with model: {engine.model_name}")
        
        # Test prompt
        test_prompt = """You are a SQL expert for HPE NonStop performance monitoring systems.
Generate a single valid PostgreSQL SELECT query for the schema 'macht413'.

STRICT RULES:
- Output ONLY the raw SQL query. No explanation, no markdown, no backticks.
- Only SELECT statements. No INSERT, UPDATE, DELETE, DROP, ALTER, or any DDL.
- Always qualify table names: macht413.table_name
- Always include LIMIT 10000 unless a smaller limit is specified.

SCHEMA CONTEXT:
-- Table: macht413.cpu
CREATE TABLE macht413.cpu (
    system_name TEXT,
    cpu_num BIGINT,
    cpu_busy_time BIGINT
);

USER REQUEST:
Show average CPU busy time per CPU

SQL:"""
        
        print("\n" + "-" * 80)
        print("Test Prompt:")
        print(test_prompt[:200] + "...")
        print("-" * 80)
        
        # Generate SQL
        print("\nGenerating SQL...")
        sql = engine.generate_sql(test_prompt)
        
        print("\n" + "-" * 80)
        print("Generated SQL:")
        print(sql)
        print("-" * 80)
        
        # Verify it looks like SQL
        if 'SELECT' in sql.upper() and 'FROM' in sql.upper():
            print("\n✓ Response looks like valid SQL")
        else:
            print("\n✗ Response doesn't look like SQL")
        
        print("\n" + "=" * 80)
        print("✓ LLM Engine test complete!")
        print("=" * 80)
        
    except LLMError as e:
        print(f"\n✗ LLM Error: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
