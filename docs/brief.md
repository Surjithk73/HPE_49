# Build Brief: Natural-Language → SQL pipeline for HPE NonStop counter data

You are extending my existing prototype. Read this whole brief before writing code. Where I've left `«placeholders»`, ask me or use a clearly-marked stub — do not silently invent values. Prefer small, composable modules and write it so the model backends are swappable (see "Model roles").

## 1. What this system does

Users ask in plain English for information about performance counters collected from HPE NonStop servers (e.g. "show me the top 10 busy CPUs"). The system turns that into SQL, runs it against the counter database, and returns results. 

**Critical user assumption:** the user knows *what they want* but knows *nothing* about the database — no table names, no column names, no idea what any field means. Design every user-facing interaction around this. The system carries the entire burden of mapping business concepts to schema.

## 2. Current stack / migration path

- Prototype today: a single hosted model, **Gemini 3.1**, does everything.
- Later: migrate to local LLMs — a local general model for understanding, and a local **SQLCoder** model for SQL synthesis.
- I already have a **RAG retriever** that, given a query, returns the relevant schema plus column/table descriptions plus few-shot (question → SQL) examples. Integrate with it; treat it as an injectable dependency `«rag_retriever»`, don't rebuild it.

## 3. Model roles (make these swappable — important)

Define **two logical roles**, each mapped to a configurable backend:

- `PLANNER` — understands intent, runs the clarification loop, emits the intent spec.
- `SQL_GENERATOR` — compiles a completed intent spec into SQL.

Today both roles point at the same Gemini backend. The architecture must allow them to point at *different* backends later (PLANNER → local general model, SQL_GENERATOR → SQLCoder) by changing config only. Put all model calls behind a single `ModelProvider` interface (`generate(prompt, system_prompt) -> str`) with a `GeminiProvider` implementation now and a clear seam for `LocalProvider` later. No model-specific logic should leak outside the provider classes.

## 4. Architecture / flow

```
user question
   → PLANNER: clarification loop  →  Intent Spec (structured)
   → SQL_GENERATOR: compile spec  →  SQL
   → validate + retry loop        →  result rows
   → surface results + the assumptions that were made  →  user
```

## 5. The Intent Spec (the intermediate representation)

A structured object the planner fills. This is both the planner's output AND the confidence signal — its completeness IS the confidence measure (see §7). Define a domain-specific slot schema for NonStop counters. Starting slots (refine with me):

- `metric` — what is being measured (e.g. CPU busy %, queue length, memory). Critical.
- `entity_scope` — which entities (which CPUs / processes / systems / which subset). Critical.
- `aggregation` — avg / max / sum / raw, and over what grouping.
- `time_window` — time range. Has a default.
- `ranking_and_limit` — order by what, top/bottom N. Has a default.
- `filters` — any additional constraints.

Each slot has: a value, a `confidence`/`resolved` flag, and a `is_critical` flag. The spec is also what you hand to `SQL_GENERATOR`, so make it serialize to a clean prompt.

## 6. The clarification loop — schema-blind

The planner asks the user follow-up questions ONLY when needed. Hard rules:

- **Questions to the user contain zero schema identifiers** — no table or column names. Only business/domain language the user already has. If a real ambiguity is fundamentally a *schema* fork, translate it into a *conceptual* question. Example: not "do you want `CPU_BUSY_TIME` or `PROCESS_QUEUE_LEN`?" but "by 'busy', do you mean how hard the processors are working, or how much work is queued waiting?"
- Distinguish two kinds of uncertainty and route them differently:
  - **Intent ambiguity** (which 'busy', what window, ranked how) — only the user can resolve. May trigger a question.
  - **Schema-grounding ambiguity** (which tables/columns realize the intent) — the user CANNOT help. Resolve internally via the RAG context + defaults. Never ask the user about this.

## 7. Confidence gauge — do NOT use a self-reported scalar

A raw "rate your confidence 0–100" from the model is unreliable and overconfident. Instead derive confidence structurally:

1. **Slot completeness** — confidence is high when every *critical* slot is filled with a single confident interpretation. The loop's exit condition is "no critical slot is both unfilled and materially ambiguous," not a magic number.
2. **Ambiguity enumeration** — to decide whether a slot is ambiguous, have the planner *enumerate the distinct plausible interpretations* of the current request. One plausible interpretation → resolved. Several materially different ones → ambiguous, AND those alternatives become the multiple-choice question to ask the user (phrased in business terms per §6).

If I later want a numeric confidence for display, derive it from slot completeness — do not ask the model to introspect a number.

## 8. Loop exit conditions (any one ends the loop → hand off to SQL_GENERATOR)

- **Natural exit:** all critical slots filled with confident single interpretations.
- **Default-and-proceed:** remaining gaps are only on slots that have a sensible default and are low-stakes → fill default, continue.
- **Question budget:** a hard cap of `«MAX_QUESTIONS = 2-3»` questions, ever. Never interrogate past this even if ambiguity remains — long interrogation destroys the UX.
- **User force (escape hatch):** see §10.

## 9. Defaults (config, offline-defined domain knowledge)

A config file of sensible defaults the loop falls back to. These are what let it exit early and what it uses on a forced exit. Define with me; starting points: default `time_window` = «last 24h», default reading of "busy" = CPU utilization, default `limit` = 10. Make this a plain editable config, not hardcoded in logic.

## 10. User escape hatch + assumption surfacing (safety-critical)

- Expose a "good enough, just run it" affordance available at **every** clarification turn.
- **Whenever the system proceeds under uncertainty — by default, by hitting the budget, or because the user forced it — it must surface its assumptions, never guess silently.** The result is always returned with the assumptions stated: e.g. "Assumed CPU utilization, last 24h, top 10 by busy %. Results below — tell me if any assumption is wrong." This is what makes "force it" safe instead of a black box.

## 11. SQL generation + validation/retry loop

- `SQL_GENERATOR` compiles the completed Intent Spec (+ a hardcoded system prompt + RAG context) into SQL.
- Validate BEFORE declaring success — "it executed" is NOT success on its own:
  - schema-link check: every referenced table/column actually exists in the retrieved schema;
  - dry-run / `EXPLAIN` against the DB where possible.
- On execution failure, feed the **actual error message** back into regeneration, don't blind-retry. Cap retries at `«MAX_RETRIES»`.
- (Optional, if cheap) generate N candidates and select by agreement.

## 12. SQL dialect

The target dialect is **PostgreSQL** — standard `LIMIT n`, Postgres functions and casting. Set `SQL_DIALECT = postgres` in config and include it in the SQL_GENERATOR system prompt. No special dialect handling is needed. (Bonus: this also de-risks the later local swap, since SQLCoder is natively Postgres-oriented.)

## 13. Semantic layer (recommended, ask me before assuming)

Counter data is often cumulative and needs deltas/rates over a time window, and metrics like "busy %" are derived. Where possible, prefer querying **views** that pre-compute these (e.g. a `cpu_busy_pct` view) so the model writes simple SQL instead of re-deriving counter math each time. Flag where a view would simplify generation; don't create DB objects without asking me.

## 14. Eval + logging harness (build a minimal one now)

Add structured logging of every stage (question, questions asked, final spec, generated SQL, validation outcome, assumptions surfaced) and a small eval runner that scores a golden set of `(question, expected SQL, expected result)` pairs on **both** execution success and result-match — because result correctness, not "it ran," is the real metric. A stub with 5–10 cases is fine to start.

## 15. Build order

1. `ModelProvider` interface + `GeminiProvider`; wire both roles to it.
2. Intent Spec schema + the planner clarification loop (slot-filling, ambiguity enumeration, budget, escape hatch, assumption surfacing) — testable on its own with Gemini.
3. SQL_GENERATOR over the completed spec + integrate my existing RAG retriever.
4. Validation + retry loop (error feedback, schema-link check).
5. Logging + minimal eval harness.
6. Leave clear seams for the local-LLM swap.

## 16. Tell me / constraints

- My stack is `«language/framework — likely Python; confirm»`. Match it.
- Don't hardcode Gemini anywhere outside the provider.
- Keep PLANNER and SQL_GENERATOR as distinct roles even though they share a backend today.
- Ask me before: creating DB objects, changing the RAG retriever, or finalizing the slot schema and defaults.