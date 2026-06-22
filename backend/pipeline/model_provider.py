"""
ModelProvider — swappable LLM backend interface for QueryCraft.

Two logical roles (PLANNER, SQL_GENERATOR) each receive a ModelProvider.
Both point at NIMProvider (NVIDIA NIM) today; swap to a local provider later
via config without touching any pipeline logic.

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


class NIMProvider(ModelProvider):
    """
    Calls NVIDIA NIM (OpenAI-compatible). No model-specific logic should live
    elsewhere — only this class knows about the NIM endpoint and client.

    Sampling params are passed per role (deterministic for SQL generation,
    slightly relaxed for the planner) — see the role factories in llm_engine.py.
    """

    DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

    def __init__(
        self,
        api_key: str,
        model_name: str,
        base_url: str = DEFAULT_BASE_URL,
        temperature: float = 0.0,
        top_p: float = 1.0,
        max_tokens: int = 1536,
    ) -> None:
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            from pipeline.llm_engine import LLMError
            raise LLMError("openai package not installed (required for NVIDIA NIM)") from exc

        if not api_key:
            from pipeline.llm_engine import LLMError
            raise LLMError(
                "NVIDIA NIM API key not configured. "
                "Set PLANNER_API_KEY / SQL_GENERATOR_API_KEY (or NVIDIA_API_KEY) in .env"
            )

        self._client = OpenAI(api_key=api_key, base_url=base_url or self.DEFAULT_BASE_URL)
        self.model_name = model_name
        self._temperature = temperature
        self._top_p = top_p
        self._max_tokens = max_tokens

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        from pipeline.llm_engine import LLMError

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self._temperature,
                top_p=self._top_p,
                max_tokens=self._max_tokens,
            )
            if not response.choices:
                raise LLMError("Empty response from NVIDIA NIM")
            text = response.choices[0].message.content
            if not text:
                raise LLMError("Empty response from NVIDIA NIM")
            return text
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"NVIDIA NIM API call failed: {exc}") from exc


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
