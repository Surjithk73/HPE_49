"""
IntentSpec — structured intermediate representation between Planner and SQL_GENERATOR.

The Planner fills these slots through the clarification loop. When is_ready() is True
(all critical slots resolved), the spec is handed to SQLGenerator.

Confidence is derived from slot completeness — never a self-reported scalar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Slot:
    """A single intent dimension the Planner fills."""

    name: str
    value: Any = None
    is_critical: bool = False
    resolved: bool = False
    # Populated during ambiguity enumeration; cleared once the slot is resolved.
    ambiguous_interpretations: list[str] = field(default_factory=list)

    def fill(self, value: Any, assumed: bool = False) -> None:
        """Mark slot as filled. assumed=True means a default was used."""
        self.value = value
        self.resolved = True
        self.ambiguous_interpretations = []


@dataclass
class IntentSpec:
    """
    Fully describes what the user wants in business-domain terms.
    No schema identifiers (table names, column names) live here — those
    are resolved by SQLGenerator via the RAG retriever.
    """

    metric: Slot = field(
        default_factory=lambda: Slot("metric", is_critical=True)
    )
    entity_scope: Slot = field(
        default_factory=lambda: Slot("entity_scope", is_critical=True)
    )
    aggregation: Slot = field(
        default_factory=lambda: Slot("aggregation", is_critical=False)
    )
    time_window: Slot = field(
        default_factory=lambda: Slot("time_window", is_critical=False)
    )
    ranking_and_limit: Slot = field(
        default_factory=lambda: Slot("ranking_and_limit", is_critical=False)
    )
    filters: Slot = field(
        default_factory=lambda: Slot("filters", is_critical=False)
    )
    # Populated whenever the system proceeds under uncertainty (default-fill,
    # budget exhausted, or user-forced). Always surfaced to the user.
    assumptions: list[str] = field(default_factory=list)

    # ── Predicates ────────────────────────────────────────────────────────────

    def is_ready(self) -> bool:
        """True when every critical slot is filled with a confident single value."""
        return all(s.resolved for s in self._critical_slots())

    def unresolved_critical(self) -> list[Slot]:
        return [s for s in self._critical_slots() if not s.resolved]

    def unresolved_optional(self) -> list[Slot]:
        return [
            s for s in self._all_slots()
            if not s.is_critical and not s.resolved
        ]

    def numeric_confidence(self) -> float:
        """
        Derived confidence for display only — do not use as loop exit condition.
        Critical slots are worth 70% of the score; optional fill the remaining 30%.
        """
        critical = self._critical_slots()
        optional = self._optional_slots()
        if not critical:
            return 1.0

        c_weight = 0.70
        o_weight = 0.30

        c_score = sum(1 for s in critical if s.resolved) / len(critical)
        o_score = (
            sum(1 for s in optional if s.resolved) / len(optional)
            if optional else 1.0
        )
        return round(c_weight * c_score + o_weight * o_score, 2)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_prompt_block(self) -> str:
        """
        Serialises the spec for the SQL_GENERATOR prompt.
        Produces a concise plain-language block the model can follow.
        """
        lines = ["## USER INTENT"]
        for slot in self._all_slots():
            label = slot.name.replace("_", " ").title()
            val = slot.value if slot.resolved else "(not specified)"
            lines.append(f"- {label}: {val}")
        if self.assumptions:
            lines.append("")
            lines.append("## ASSUMPTIONS MADE")
            for a in self.assumptions:
                lines.append(f"- {a}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """For JSON serialisation in API responses."""
        return {
            "slots": {
                s.name: {
                    "value": s.value,
                    "resolved": s.resolved,
                    "is_critical": s.is_critical,
                }
                for s in self._all_slots()
            },
            "assumptions": self.assumptions,
            "confidence": self.numeric_confidence(),
            "ready": self.is_ready(),
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _all_slots(self) -> list[Slot]:
        return [
            self.metric, self.entity_scope, self.aggregation,
            self.time_window, self.ranking_and_limit, self.filters,
        ]

    def _critical_slots(self) -> list[Slot]:
        return [s for s in self._all_slots() if s.is_critical]

    def _optional_slots(self) -> list[Slot]:
        return [s for s in self._all_slots() if not s.is_critical]
