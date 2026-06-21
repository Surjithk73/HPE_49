"""
Planner — runs the schema-blind clarification loop that fills an IntentSpec.

The loop asks the user at most max_questions questions (in plain business language,
never using table or column names). It exits when:
  1. All critical slots are resolved (natural exit)
  2. Remaining gaps are optional and have defaults (default-and-proceed)
  3. The question budget is exhausted (budget exit)
  4. The user triggers force_proceed() (escape hatch)

On any non-natural exit the system records its assumptions — see IntentSpec.assumptions.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

from pipeline.intent_spec import IntentSpec, Slot
from pipeline.model_provider import ModelProvider


# ── Session state ─────────────────────────────────────────────────────────────

@dataclass
class PlannerSession:
    session_id: str
    spec: IntentSpec
    questions_asked: int = 0
    history: list[dict] = field(default_factory=list)  # [{role, content}, ...]
    target_db: str = "macht413"  # node/schema chosen at start, held across all turns


@dataclass
class PlannerTurn:
    """Return value of Planner.start() and Planner.answer()."""
    status: str              # "clarifying" | "ready"
    question: Optional[str]  # Present when status=="clarifying"
    session_id: str
    spec: IntentSpec
    session: PlannerSession = field(repr=False)  # caller stores this for continuations
    debug_prompt: Optional[str] = None           # full conversation sent to LLM (for debugging)


# ── System prompt for the Planner role ───────────────────────────────────────

_PLANNER_SYSTEM = """You are the PLANNER for a natural-language query system that queries
HPE NonStop server performance data. Your job is to understand what the user wants
and fill in a structured Intent Spec — NOT to write SQL.

HARD RULES:
1. Questions to the user must use plain business/domain language only.
   Never mention table names, column names, or any database schema.
2. Distinguish intent ambiguity (ask the user) from schema-grounding ambiguity
   (resolve internally — never ask the user about this).
3. You may ask at most {max_questions} questions total for any query.
4. When you have enough information (or have hit the question limit),
   output the filled spec — do not keep asking.
5. Do NOT invent a time range. If the user does not mention any time period,
   leave time_window unresolved (resolved=false) — the system will default it
   to "all time". Never assume "last 24 hours" or any other window on your own.


AVAILABLE SLOTS to fill:
- metric: what is being measured (e.g. "CPU busy percentage", "disk read throughput")
- entity_scope: which entities (e.g. "all CPUs", "top 5 processes", "a specific node")
- aggregation: avg / max / sum / raw
- time_window: time range
- ranking_and_limit: order by what, top/bottom N
- filters: any extra constraints the user specified

OUTPUT FORMAT — always respond with a JSON object:
{
  "action": "ask" | "fill",
  "question": "<business-language question to ask user, only when action=ask>",
  "slots": {
    "metric":           {"value": ..., "resolved": true/false, "interpretations": [...]},
    "entity_scope":     {"value": ..., "resolved": true/false, "interpretations": [...]},
    "aggregation":      {"value": ..., "resolved": true/false, "interpretations": [...]},
    "time_window":      {"value": ..., "resolved": true/false, "interpretations": [...]},
    "ranking_and_limit":{"value": ..., "resolved": true/false, "interpretations": [...]},
    "filters":          {"value": ..., "resolved": true/false, "interpretations": [...]}
  },
  "assumptions": ["<assumption text if defaulting>", ...]
}

When action=ask, also include the current state of all slots (partially filled is fine).
When action=fill, all critical slots (metric, entity_scope) must be resolved=true.
"""


class Planner:
    """Stateless planner — session state lives in PlannerSession."""

    def __init__(self, provider: ModelProvider, defaults: dict) -> None:
        self._provider = provider
        self._defaults = defaults
        self._max_questions: int = int(defaults.get("max_questions", 2))
        self._slot_defaults: dict = defaults.get("defaults", {})

    def _system_prompt(self) -> str:
        """
        Build the system prompt. We use str.replace (not str.format) because the
        template embeds a literal JSON example full of { } braces that str.format
        would misinterpret as format fields.
        """
        return _PLANNER_SYSTEM.replace("{max_questions}", str(self._max_questions))

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self, user_query: str) -> PlannerTurn:
        """Begin the clarification loop for a new user query."""
        spec = IntentSpec()
        session = PlannerSession(
            session_id=str(uuid.uuid4()),
            spec=spec,
        )

        system_prompt = self._system_prompt()
        user_msg = f"User query: {user_query}"
        session.history.append({"role": "user", "content": user_msg})

        return self._advance(session, system_prompt)

    def answer(self, session: PlannerSession, user_answer: str) -> PlannerTurn:
        """Continue the loop with the user's answer to the last question."""
        session.history.append({"role": "user", "content": user_answer})
        system_prompt = self._system_prompt()
        return self._advance(session, system_prompt)

    def revise_on_error(
        self,
        session: PlannerSession,
        error: str,
        failed_sql: str,
    ) -> PlannerTurn:
        """
        Internal revision step — NOT a user-facing question.

        Called when SQL generation, validation, or execution fails.
        The planner receives the error as system feedback and revises
        its IntentSpec slots to fix the root cause without asking the user.
        Does NOT count against the question budget.
        """
        feedback = (
            "SYSTEM FEEDBACK (not from user):\n"
            "The SQL compiled from the current intent spec failed.\n"
            f"Error: {error}\n"
            f"Failed SQL:\n{failed_sql}\n\n"
            "Please revise the spec slots to fix the root cause. "
            "Do NOT ask the user — update slot values internally based on the error. "
            "Output action=fill with corrected slot values."
        )
        session.history.append({"role": "user", "content": feedback})
        system_prompt = self._system_prompt()
        return self._advance(session, system_prompt, force_fill=True)

    def force_proceed(self, session: PlannerSession) -> IntentSpec:
        """
        Escape hatch — fill unfilled slots with defaults and record assumptions.
        The caller is responsible for surfacing spec.assumptions to the user.
        """
        self._apply_defaults(session.spec, force=True)
        return session.spec

    # ── Internal ──────────────────────────────────────────────────────────────

    def _advance(
        self,
        session: PlannerSession,
        system_prompt: str,
        force_fill: bool = False,
    ) -> PlannerTurn:
        """
        Call the LLM, parse the response, update the spec, decide next step.

        force_fill=True: never ask the user, always proceed to fill.
        Used by revise_on_error() so error-driven revisions stay internal.
        """
        conversation = "\n\n".join(
            f"{'User' if m['role'] == 'user' else 'Planner'}: {m['content']}"
            for m in session.history
        )

        # Build the full debug string before calling the LLM so it's available
        # even if generation fails.
        debug_prompt = (
            f"=== PLANNER SYSTEM PROMPT ===\n{system_prompt}\n\n"
            f"=== CONVERSATION ===\n{conversation}"
        )
        print(f"[Planner Debug] Prompt sent to LLM:\n{debug_prompt}\n{'='*60}")

        raw = self._provider.generate(conversation, system_prompt=system_prompt)
        session.history.append({"role": "assistant", "content": raw})

        parsed = _parse_planner_response(raw)
        self._update_spec(session.spec, parsed)

        if parsed.get("assumptions"):
            for a in parsed["assumptions"]:
                if a and a not in session.spec.assumptions:
                    session.spec.assumptions.append(a)

        action = parsed.get("action", "fill")

        # Budget check: if we've hit the cap, force fill regardless of action.
        # force_fill also prevents asking during error-driven revisions.
        budget_exhausted = session.questions_asked >= self._max_questions
        should_ask = (
            (action == "ask")
            and not budget_exhausted
            and not session.spec.is_ready()
            and not force_fill
        )

        if should_ask:
            session.questions_asked += 1
            question = parsed.get("question", "Could you give me more details?")
            session.history.append({"role": "assistant", "content": question})
            return PlannerTurn(
                status="clarifying",
                question=question,
                session_id=session.session_id,
                spec=session.spec,
                session=session,
                debug_prompt=debug_prompt,
            )

        # Natural exit, default-and-proceed, or budget exhausted
        self._apply_defaults(session.spec, force=False)

        if budget_exhausted and not session.spec.is_ready():
            session.spec.assumptions.append(
                f"Question limit reached ({self._max_questions}); "
                "remaining gaps filled with defaults."
            )

        return PlannerTurn(
            status="ready",
            question=None,
            session_id=session.session_id,
            spec=session.spec,
            session=session,
            debug_prompt=debug_prompt,
        )

    def _update_spec(self, spec: IntentSpec, parsed: dict) -> None:
        """Write LLM-parsed slot values into the IntentSpec."""
        slot_map = {
            "metric": spec.metric,
            "entity_scope": spec.entity_scope,
            "aggregation": spec.aggregation,
            "time_window": spec.time_window,
            "ranking_and_limit": spec.ranking_and_limit,
            "filters": spec.filters,
        }
        for name, data in parsed.get("slots", {}).items():
            slot = slot_map.get(name)
            if slot is None:
                continue
            interpretations = data.get("interpretations", [])
            slot.ambiguous_interpretations = interpretations
            if data.get("resolved") and data.get("value") is not None:
                slot.fill(data["value"])

    def _apply_defaults(self, spec: IntentSpec, force: bool) -> None:
        """Fill unresolved optional (and critical if force=True) slots with defaults."""
        d = self._slot_defaults
        candidates = spec.unresolved_optional()
        if force:
            candidates += spec.unresolved_critical()

        for slot in candidates:
            default_val = self._default_for(slot.name, d)
            if default_val is not None:
                slot.fill(default_val)
                assumption = f"Assumed {slot.name.replace('_', ' ')}: {default_val}"
                if assumption not in spec.assumptions:
                    spec.assumptions.append(assumption)

    def _default_for(self, name: str, d: dict) -> object | None:
        mapping = {
            "time_window": d.get("time_window"),
            "ranking_and_limit": f"top {d.get('limit', 10)}",
            "aggregation": d.get("aggregation"),
            "filters": "none",
        }
        return mapping.get(name)


# ── Response parser ───────────────────────────────────────────────────────────

def _parse_planner_response(raw: str) -> dict:
    """
    Extract JSON from the planner's raw text response.
    Falls back to a minimal "fill" action if parsing fails.
    """
    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", raw, flags=re.IGNORECASE).strip()
    text = text.replace("```", "").strip()

    # Find first JSON object in the response
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: treat as a "fill" with no slots resolved yet
    return {"action": "fill", "slots": {}, "assumptions": []}
