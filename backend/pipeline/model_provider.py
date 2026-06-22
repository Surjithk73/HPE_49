"""
ModelProvider — swappable LLM backend interface for QueryCraft.

Two logical roles (PLANNER, SQL_GENERATOR) each receive a ModelProvider.
Both point at GeminiProvider today; swap to LocalProvider later via config
without touching any pipeline logic.

Contract: generate(prompt, system_prompt="") -> str  (raw text response)
SQL extraction, retry logic, and validation stay in the engine layer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ModelProvider(ABC):
    """Minimal interface every backend must satisfy."""

    model_name: str = ""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Return raw text response. Raises LLMError on failure."""
        ...


class GeminiProvider(ModelProvider):
    """Calls Google Gemini API. No model-specific logic should live elsewhere."""

    def __init__(self, api_key: str, model_name: str) -> None:
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError as exc:
            from pipeline.llm_engine import LLMError
            raise LLMError("google-generativeai package not installed") from exc

        if not api_key:
            from pipeline.llm_engine import LLMError
            raise LLMError("Gemini API key not configured. Set GEMINI_API_KEY in .env")

        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model_name)
        self.model_name = model_name

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        from pipeline.llm_engine import LLMError

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        try:
            response = self._model.generate_content(full_prompt)
            if not response or not response.text:
                raise LLMError("Empty response from Gemini")
            return response.text
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Gemini API call failed: {exc}") from exc


class OllamaProvider(ModelProvider):
    """
    Stub — not yet wired for the clarification pipeline.
    For SQL generation via Ollama today, set LLM_PROVIDER=ollama;
    the pipeline uses OllamaEngine directly (see pipeline/ollama_engine.py).
    This class exists as the seam for a future local-model swap.
    """

    def __init__(self, model_name: str = "") -> None:
        self.model_name = model_name

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError(
            "OllamaProvider is a stub. "
            "Set LLM_PROVIDER=ollama to use the OllamaEngine path instead."
        )
