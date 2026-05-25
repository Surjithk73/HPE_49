"""
LLM Engine base for QueryCraft.

Holds the provider-agnostic base class (retry loop + SQL extraction) and the
factory used by the rest of the pipeline. The only concrete backend is
OllamaEngine in pipeline/ollama_engine.py — SQL is generated against a local
Ollama server, no external API.
"""
import re


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

    def generate_sql(self, prompt: str) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def generate_text(self, prompt: str) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

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
                sql = self.generate_sql(current_prompt)
                result = validator.validate(sql)

                if result.valid:
                    print(f"[LLM] ✓ Valid SQL generated on attempt {attempt + 1}")
                    return result.sanitized_sql
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


def make_llm_engine() -> "BaseLLMEngine":
    """Return the configured LLM engine. Ollama is the only backend."""
    from pipeline.ollama_engine import OllamaEngine
    return OllamaEngine()
