"""
SQLGenerator — compiles a completed IntentSpec into SQL.

Injects the spec as a structured prompt block, retrieves schema context and
few-shot examples via the existing RAG retriever, then calls the SQL_GENERATOR
model role. Retries on validation failure (up to max_retries).

The schema_linker and few_shot_retriever are injected as-is — they are the
«rag_retriever» referenced in docs/brief.md. Do not modify them here.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from config import SQL_DIALECT, MAX_ROWS
except (ValueError, ImportError):
    SQL_DIALECT = "postgres"
    MAX_ROWS = 10000

from pipeline.intent_spec import IntentSpec
from pipeline.model_provider import ModelProvider
from pipeline.llm_engine import LLMError

_DIALECT_NOTES = {
    "postgres": "Use standard PostgreSQL syntax. LIMIT n is correct.",
    "sqlmx":    "Use HPE NonStop SQL/MX syntax. Use [FIRST n] instead of LIMIT n.",
    "sqlmp":    "Use HPE NonStop SQL/MP syntax. Use [FIRST n] instead of LIMIT n.",
}


class SQLGenerator:
    """
    Wraps the SQL_GENERATOR model role.
    Takes a completed IntentSpec and returns validated SQL.
    """

    def __init__(
        self,
        provider: ModelProvider,
        schema_linker,
        few_shot_retriever,
        prompt_builder,
        validator=None,
        max_retries: int = 2,
        dialect: str = SQL_DIALECT,
    ) -> None:
        self._provider = provider
        self._linker = schema_linker
        self._few_shot_retriever = few_shot_retriever
        self._builder = prompt_builder
        self._validator = validator
        self._max_retries = max_retries
        self._dialect = dialect

    def generate(self, spec: IntentSpec, target_db: str = "macht413") -> tuple[str, str, str]:
        """
        Compile a completed IntentSpec into SQL — single shot, no internal retry.

        Retry logic (with planner re-planning) lives in the orchestrator
        (_execute_from_spec in main.py). This method raises LLMError immediately
        on validation failure so the orchestrator can route the error to the planner.

        Returns:
            (validated_sql, raw_llm_output, prompt)

        Raises:
            LLMError: on generation failure or validation failure
        """
        query_signal = self._spec_to_query_signal(spec)

        schema_context = self._linker.link_schema(query_signal, "multi", target_db)
        top_few_shots = self._few_shot_retriever.get_top_k(query_signal, k=3)

        prompt = self._builder.build_spec_prompt(
            spec=spec,
            schema_context=schema_context,
            few_shots=top_few_shots,
            target_db=target_db,
            dialect=self._dialect,
        )

        raw = self._provider.generate(prompt)
        sql = self._extract_sql(raw)

        if self._validator:
            result = self._validator.validate(sql)
            if not result.valid:
                raise LLMError(f"Validation failed: {result.error}")
            return result.sanitized_sql, raw, prompt

        return sql, raw, prompt

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _spec_to_query_signal(self, spec: IntentSpec) -> str:
        """Convert spec to a short text string suitable for schema/few-shot retrieval."""
        parts = []
        if spec.metrics.resolved:
            parts.append(str(spec.metrics.value))
        if spec.entity_scope.resolved:
            parts.append(str(spec.entity_scope.value))
        if spec.aggregation.resolved:
            parts.append(str(spec.aggregation.value))
        if not parts:
            return "performance metrics"
        return " ".join(parts)

    @staticmethod
    def _extract_sql(text: str) -> str:
        """Strip markdown fences from LLM response."""
        import re
        match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()
