"""
Intent Classifier for QueryCraft.

Runs a fast pre-pass before the main SQL generation to:
  1. Classify the query intent (single_metric, ranking, time_series, comparison, correlation).
  2. Detect ambiguity and emit up to MAX_QUESTIONS clarification questions.

This runs in the same request as SQL generation -- the SQL is always generated
as a best-guess in parallel, and the questions are surfaced as advisory hints
in the UI, not as blockers.
"""
import json
import re
from typing import Optional

MAX_QUESTIONS = 4

_INTENT_PROMPT = """\
You are a query intent classifier for HPE NonStop performance monitoring SQL systems.

Analyse the user query and return a JSON object with exactly these fields:
- "intent": one of ["single_metric", "ranking", "time_series", "comparison", "aggregation", "correlation"]
- "ambiguous": true or false -- is key information missing that would change the SQL significantly?
- "clarification_questions": a list of up to {max_q} short, specific questions to ask the user IF ambiguous is true. Return [] if ambiguous is false.

Intent definitions:
- single_metric:   User wants one specific metric for a set of entities (e.g. "CPU busy time per CPU").
- ranking:         User wants top/bottom N entities (e.g. "Top 5 processes by memory").
- time_series:     User wants data over time / trend (e.g. "CPU utilization over last hour").
- comparison:      User wants to compare two or more dimensions (e.g. "CPU vs disk activity").
- aggregation:     User wants a summary / total / average (e.g. "Total transactions").
- correlation:     User wants to find relationships between metrics (e.g. "Does disk I/O affect CPU?").

Common reasons to set ambiguous=true (be judicious -- do NOT ask if the schema makes the answer obvious):
- Time range is missing for a time_series query.
- "Top N" ranking has no N specified.
- Multiple tables could satisfy the request and one is clearly needed.
- The user used a vague term like "performance" or "health" with no specific metric.

STRICT OUTPUT RULES:
- Output ONLY valid JSON. No explanation, no markdown fences.
- "clarification_questions" must be an empty list [] when ambiguous is false.
- Each question must be concise and answerable with a short phrase.

USER QUERY: {query}

JSON:"""


def classify_intent(query_text: str, llm_engine) -> dict:
    """
    Run a fast LLM pre-pass to classify query intent and detect ambiguity.

    Args:
        query_text: The normalized user query.
        llm_engine: An active BaseLLMEngine instance.

    Returns:
        dict with keys:
            intent                  (str)       -- query intent category
            ambiguous               (bool)      -- whether the query is ambiguous
            clarification_questions (list[str]) -- up to MAX_QUESTIONS questions
    """
    _default = {
        "intent": "single_metric",
        "ambiguous": False,
        "clarification_questions": []
    }

    if llm_engine is None:
        return _default

    prompt = _INTENT_PROMPT.format(query=query_text.strip(), max_q=MAX_QUESTIONS)

    try:
        raw = llm_engine.generate_text(prompt)
    except Exception as e:
        print(f"[IntentClassifier] LLM call failed: {e}")
        return _default

    # Strip markdown fences if the model adds them despite instructions
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                print(f"[IntentClassifier] Failed to parse JSON: {raw[:200]}")
                return _default
        else:
            print(f"[IntentClassifier] No JSON found in response: {raw[:200]}")
            return _default

    valid_intents = {"single_metric", "ranking", "time_series", "comparison", "aggregation", "correlation"}
    intent = result.get("intent", "single_metric")
    if intent not in valid_intents:
        intent = "single_metric"

    ambiguous = bool(result.get("ambiguous", False))
    questions = result.get("clarification_questions", [])
    if not isinstance(questions, list):
        questions = []

    questions = [str(q).strip() for q in questions if q][:MAX_QUESTIONS]

    if not ambiguous:
        questions = []

    return {
        "intent": intent,
        "ambiguous": ambiguous,
        "clarification_questions": questions
    }
