"""
Ollama engine for QueryCraft.

Talks to a local Ollama server (https://ollama.com) over its HTTP API to
generate SQL fully offline. Implements the same generate_sql(prompt) contract
as pipeline/llm_engine.LLMEngine so the rest of the pipeline is unchanged.

Configuration (backend/.env):
  LLM_PROVIDER=ollama
  OLLAMA_MODEL=llama3.1            # any pulled model; e.g. llama3.1, codellama
  OLLAMA_URL=http://localhost:11434  # default
  OLLAMA_TIMEOUT_SECONDS=120       # default

Uses only the Python stdlib (urllib + json) to avoid adding new dependencies.
"""
from __future__ import annotations

import json
import os
import sys
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

# Add parent directory to path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS
except (ValueError, ImportError):
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
    OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))

from pipeline.llm_engine import BaseLLMEngine, LLMError


class OllamaEngine(BaseLLMEngine):
    """SQL generation against a local Ollama server."""

    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ):
        self.url = (url or OLLAMA_URL or "http://localhost:11434").rstrip("/")
        self.model_name = model or OLLAMA_MODEL
        self.timeout = timeout or OLLAMA_TIMEOUT_SECONDS

        if not self.model_name:
            raise LLMError(
                "Ollama model not configured. Set OLLAMA_MODEL in .env "
                "(e.g. OLLAMA_MODEL=llama3.1)."
            )

    def generate_sql(self, prompt: str) -> tuple[str, str]:
        """
        Generate SQL by calling Ollama's /api/generate endpoint.

        Args:
            prompt: Complete prompt string

        Returns:
            Tuple of (Cleaned SQL string, Raw LLM response string)

        Raises:
            LLMError: If the call fails or returns no text
        """
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            # Deterministic-ish settings suited to SQL generation. Ollama
            # silently ignores unknown options, so this stays safe across
            # model backends (llama.cpp, etc.).
            "options": {
                "temperature": 0.0,
                "top_p": 0.9,
            },
        }

        body = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            f"{self.url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlrequest.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except HTTPError as e:
            # 404 typically means the model isn't pulled.
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
            raise LLMError(
                f"Ollama HTTP {e.code} from {self.url}/api/generate "
                f"(model={self.model_name}). {detail}"
            )
        except URLError as e:
            raise LLMError(
                f"Could not reach Ollama at {self.url}: {e.reason}. "
                f"Is the server running? (`ollama serve`)"
            )
        except Exception as e:
            raise LLMError(f"Ollama request failed: {e}")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise LLMError(f"Ollama returned non-JSON response: {e}")

        text = data.get("response")
        if not text:
            err = data.get("error") or "empty response"
            raise LLMError(f"Ollama returned no text: {err}")

        return self._extract_sql(text), text

    def generate_text(self, prompt: str) -> str:
        """
        Generate conversational/analytical text by calling Ollama's /api/generate endpoint.

        Args:
            prompt: Complete prompt string

        Returns:
            Generated text response

        Raises:
            LLMError: If the call fails or returns no text
        """
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
            },
        }

        body = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            f"{self.url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlrequest.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
            raise LLMError(
                f"Ollama HTTP {e.code} from {self.url}/api/generate "
                f"(model={self.model_name}). {detail}"
            )
        except URLError as e:
            raise LLMError(
                f"Could not reach Ollama at {self.url}: {e.reason}. "
                f"Is the server running? (`ollama serve`)"
            )
        except Exception as e:
            raise LLMError(f"Ollama request failed: {e}")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise LLMError(f"Ollama returned non-JSON response: {e}")

        text = data.get("response")
        if not text:
            err = data.get("error") or "empty response"
            raise LLMError(f"Ollama returned no text: {err}")

        return text.strip()


# Standalone smoke test — requires a running Ollama server with the configured
# model pulled. Won't run during normal test suites.
if __name__ == "__main__":  # pragma: no cover
    print("Testing Ollama Engine...")
    print("=" * 80)

    try:
        engine = OllamaEngine()
        print(f"✓ OllamaEngine initialized — url={engine.url}, model={engine.model_name}")

        test_prompt = (
            "You are a SQL expert. Generate ONE PostgreSQL SELECT for schema macht413.\n"
            "Output only the raw SQL, no markdown, no commentary.\n"
            "Schema: CREATE TABLE macht413.cpu (cpu_num BIGINT, cpu_busy_time BIGINT);\n"
            "Request: average cpu_busy_time per cpu\n"
            "SQL:"
        )

        sql, raw = engine.generate_sql(test_prompt)
        print("\nGenerated SQL:\n" + sql)

        if "SELECT" in sql.upper() and "FROM" in sql.upper():
            print("\n✓ Looks like SQL")
        else:
            print("\n✗ Output doesn't look like SQL")
    except LLMError as e:
        print(f"\n✗ {e}")
