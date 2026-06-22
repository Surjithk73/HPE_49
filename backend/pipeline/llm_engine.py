"""
LLM Engine for QueryCraft
Handles interaction with NVIDIA NIM (OpenAI-compatible) for SQL generation.

LLMEngine now delegates raw API calls to a ModelProvider (see model_provider.py).
Two factory functions expose the two logical roles:
  make_planner_engine()      — PLANNER role (intent clarification)
  make_sql_engine()          — SQL_GENERATOR role (SQL compilation)
  make_llm_engine()          — backward-compat alias for make_sql_engine()
"""
import re
import sys
import os

# Add parent directory to path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from config import SQL_GENERATOR_API_KEY, SQL_GENERATOR_MODEL
    NIM_AVAILABLE = True
except (ValueError, ImportError) as e:
    NIM_AVAILABLE = False
    SQL_GENERATOR_API_KEY = None
    SQL_GENERATOR_MODEL = "deepseek-ai/deepseek-v4-pro"
    print(f"Warning: NVIDIA NIM not configured: {e}")


class LLMError(Exception):
    """Custom exception for LLM-related errors."""
    pass


class BaseLLMEngine:
    """
    Shared interface for SQL-generating LLM backends.

    Subclasses must implement `generate_sql(prompt) -> str`. The retry loop
    and SQL extraction helpers live here so every backend shares identical
    behavior.
    """

    model_name: str = ""

    def generate_sql(self, prompt: str) -> tuple[str, str]:  # pragma: no cover - abstract
        raise NotImplementedError

    def generate_text(self, prompt: str) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def generate_sql_with_retry(self, prompt: str, validator, prompt_builder, max_retries: int = 2) -> tuple[str, str]:
        """
        Generate SQL with automatic retry on validation failure.

        Args:
            prompt: Initial prompt string
            validator: SQLValidator instance
            prompt_builder: PromptBuilder instance
            max_retries: Maximum number of retry attempts

        Returns:
            Tuple of (Valid SQL string, Raw LLM response string)

        Raises:
            LLMError: If all retries fail
        """
        last_error = None
        failed_sql = None
        current_prompt = prompt

        for attempt in range(max_retries + 1):
            print(f"[LLM] Attempt {attempt + 1}/{max_retries + 1}...")

            try:
                sql, raw_text = self.generate_sql(current_prompt)
                result = validator.validate(sql)

                if result.valid:
                    print(f"[LLM] ✓ Valid SQL generated on attempt {attempt + 1}")
                    return result.sanitized_sql, raw_text
                else:
                    print(f"[LLM] ✗ Validation failed: {result.error}")
                    last_error = result.error
                    failed_sql = sql

                    if attempt < max_retries:
                        current_prompt = prompt_builder.build_retry_prompt(
                            original_prompt=prompt,
                            failed_sql=failed_sql,
                            error=last_error,
                        )

            except LLMError as e:
                last_error = str(e)
                print(f"[LLM] ✗ Generation failed: {last_error}")

                if attempt >= max_retries:
                    break

        raise LLMError(f"Max retries exceeded. Last error: {last_error}")

    def _extract_sql(self, response_text: str) -> str:
        """
        Extract SQL from LLM response, removing markdown fences and explanations.
        """
        text = response_text.strip()

        sql_fence_pattern = r'```sql\s*(.*?)\s*```'
        match = re.search(sql_fence_pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        fence_pattern = r'```\s*(.*?)\s*```'
        match = re.search(fence_pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

        return text


class LLMEngine(BaseLLMEngine):
    """
    SQL generation engine. Delegates actual API calls to a ModelProvider.

    Pass a pre-built provider for the PLANNER/SQL_GENERATOR role factories,
    or omit it to get a NIMProvider built from the SQL-generator config
    (backward compat). Runtime model switching via POST /api/model still works:
    pass model= as before.
    """

    def __init__(self, api_key: str = None, model: str = None, provider=None):
        if provider is not None:
            self._provider = provider
            self.model_name = provider.model_name
        else:
            # Legacy path: build a NIMProvider from the SQL-generator config
            from pipeline.model_provider import NIMProvider
            from config import (
                NVIDIA_BASE_URL,
                SQL_GENERATOR_TEMPERATURE,
                SQL_GENERATOR_TOP_P,
            )
            _key = api_key or SQL_GENERATOR_API_KEY
            _model = model or SQL_GENERATOR_MODEL
            if not _key:
                raise LLMError(
                    "NVIDIA NIM API key not configured. "
                    "Set SQL_GENERATOR_API_KEY (or NVIDIA_API_KEY) in .env file"
                )
            self._provider = NIMProvider(
                api_key=_key,
                model_name=_model,
                base_url=NVIDIA_BASE_URL,
                temperature=SQL_GENERATOR_TEMPERATURE,
                top_p=SQL_GENERATOR_TOP_P,
            )
            self.model_name = _model

    def generate_sql(self, prompt: str) -> tuple[str, str]:
        try:
            raw = self._provider.generate(prompt)
            if not raw:
                raise LLMError("Empty response from LLM")
            return self._extract_sql(raw), raw
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Failed to generate SQL: {e}")

    def generate_text(self, prompt: str) -> str:
        try:
            result = self._provider.generate(prompt)
            if not result:
                raise LLMError("Empty response from LLM")
            return result.strip()
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Failed to generate text: {e}")


def _make_engine_for_role(
    model_name: str,
    api_key: str,
    temperature: float = 0.0,
    top_p: float = 1.0,
) -> "BaseLLMEngine":
    """Internal helper: builds an engine for a role's model + key + sampling."""
    try:
        from config import LLM_PROVIDER
    except (ValueError, ImportError):
        LLM_PROVIDER = "nvidia"

    if LLM_PROVIDER == "ollama":
        from pipeline.ollama_engine import OllamaEngine
        return OllamaEngine()

    from pipeline.model_provider import NIMProvider
    from config import NVIDIA_BASE_URL
    provider = NIMProvider(
        api_key=api_key,
        model_name=model_name,
        base_url=NVIDIA_BASE_URL,
        temperature=temperature,
        top_p=top_p,
    )
    return LLMEngine(provider=provider)


def make_planner_engine() -> "BaseLLMEngine":
    """Returns an engine configured for the PLANNER role (PLANNER_MODEL)."""
    from config import (
        PLANNER_MODEL,
        PLANNER_API_KEY,
        PLANNER_TEMPERATURE,
        PLANNER_TOP_P,
    )
    return _make_engine_for_role(
        PLANNER_MODEL, PLANNER_API_KEY, PLANNER_TEMPERATURE, PLANNER_TOP_P
    )


def make_sql_engine() -> "BaseLLMEngine":
    """Returns an engine configured for the SQL_GENERATOR role (SQL_GENERATOR_MODEL)."""
    from config import (
        SQL_GENERATOR_TEMPERATURE,
        SQL_GENERATOR_TOP_P,
    )
    return _make_engine_for_role(
        SQL_GENERATOR_MODEL,
        SQL_GENERATOR_API_KEY,
        SQL_GENERATOR_TEMPERATURE,
        SQL_GENERATOR_TOP_P,
    )


def make_llm_engine() -> "BaseLLMEngine":
    """Backward-compat alias for make_sql_engine()."""
    return make_sql_engine()


# Test the LLM engine (requires API key)
if __name__ == "__main__":
    print("Testing LLM Engine...")
    print("=" * 80)
    
    if not NIM_AVAILABLE or not SQL_GENERATOR_API_KEY:
        print("✗ NVIDIA NIM not configured")
        print("To test the LLM engine:")
        print("1. Set SQL_GENERATOR_API_KEY (or NVIDIA_API_KEY) in backend/.env")
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
        sql, raw = engine.generate_sql(test_prompt)
        
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
