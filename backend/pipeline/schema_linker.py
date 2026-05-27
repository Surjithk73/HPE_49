"""
Schema Linker for QueryCraft
Selects relevant tables and columns based on the query.

Retrieval strategy:
  1. BM25     — lexical search over per-table corpus documents
  2. BGE-large — dense vector search (BAAI/bge-large-en-v1.5 via shared embeddings)
  3. RRF      — Reciprocal Rank Fusion merges both ranked lists into a single score
"""
from typing import Dict, List, Optional, Tuple
import re
import numpy as np

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None  # type: ignore
    print("[SchemaLinker] Warning: rank_bm25 not installed — BM25 scoring disabled")

try:
    from pipeline import embeddings
except ImportError:
    import embeddings  # type: ignore


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    ranked_lists: List[List[str]],
    k: int = 60,
) -> List[Tuple[str, float]]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion (RRF).

    For each item, the RRF score is:
        score(d) = Σ  1 / (k + rank_i(d))

    where rank_i(d) is the 1-based position of d in list i, and k is a
    smoothing constant (default 60, from the original Cormack et al. paper).

    Args:
        ranked_lists: List of ranked lists, each containing item identifiers
                      ordered by decreasing relevance.
        k:           Smoothing constant; higher k reduces the influence of
                     high-ranking positions.

    Returns:
        List of (item, rrf_score) tuples sorted by descending RRF score.
    """
    scores: Dict[str, float] = {}
    for ranked in ranked_lists:
        for rank_0, item in enumerate(ranked):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank_0 + 1)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ── Tokeniser shared by BM25 index and query ─────────────────────────────────

_STOP_WORDS = frozenset([
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "about", "between",
    "through", "during", "after", "before", "above", "below", "up", "down",
    "out", "off", "over", "under", "and", "but", "or", "nor", "not", "no",
    "so", "if", "than", "too", "very", "just", "that", "this", "it", "its",
    "all", "each", "every", "both", "few", "more", "most", "other", "some",
    "such", "only", "own", "same", "then", "when", "what", "which", "who",
    "how", "where", "why", "me", "my", "i", "we", "our", "you", "your",
    "he", "him", "his", "she", "her", "they", "them", "their",
])

_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    """Lowercase, split on non-alphanum, drop stop words and single chars."""
    tokens = _SPLIT_RE.split(text.lower())
    return [t for t in tokens if t and len(t) > 1 and t not in _STOP_WORDS]


class SchemaLinker:
    """Links queries to relevant schema elements."""

    def __init__(self, schema: Dict):
        """
        Initialize the schema linker.

        Args:
            schema: Loaded schema dictionary from SchemaLoader
        """
        self.schema = schema

        # Lazy cache of per-table embeddings. Populated on the first call after
        # the shared embedding model is ready. Until then we fall back to BM25
        # only so startup queries still work.
        self._table_embeddings: Optional[np.ndarray] = None
        self._table_embedding_names: List[str] = []

        # Per-table column embeddings, populated lazily. Maps table_name to
        # (column_names, embedding_matrix) for the queryable, non-key columns.
        self._column_embeddings: Dict[str, Tuple[List[str], np.ndarray]] = {}

        self._load_precomputed_embeddings()

        # BM25 index — built lazily on first scoring call.
        self._bm25: Optional["BM25Okapi"] = None
        self._bm25_table_names: List[str] = []

        # Make sure the shared model is loading. Idempotent — safe to call from
        # multiple components.
        embeddings.start_loading()

    def _load_precomputed_embeddings(self):
        """Load precomputed embeddings from npz file if available."""
        import os
        npz_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema_store', 'schema_embeddings.npz')
        if os.path.exists(npz_path):
            try:
                data = np.load(npz_path, allow_pickle=True)
                self._table_embedding_names = data['table_names'].tolist()
                self._table_embeddings = data['table_embeddings']
                for t_name in self._table_embedding_names:
                    col_names_key = f"{t_name}_col_names"
                    col_emb_key = f"{t_name}_col_embeddings"
                    if col_names_key in data and col_emb_key in data:
                        self._column_embeddings[t_name] = (data[col_names_key].tolist(), data[col_emb_key])
                print(f"[SchemaLinker] Loaded precomputed embeddings from {npz_path}")
            except Exception as e:
                print(f"[SchemaLinker] Failed to load precomputed embeddings: {e}")

    # ── Public API ────────────────────────────────────────────────────────────

    def link_schema(self, normalized_text: str, domain_category: str) -> str:
        """
        Select relevant tables and columns for the query.

        For single-domain queries the domain classifier's choice is used
        directly.  For multi-domain queries hybrid retrieval selects the top
        tables.  In both cases a lightweight confidence check is applied: if
        the selected table produces an empty column set (e.g. the domain
        classifier fired on a keyword that doesn't actually match any column
        in the query), the linker falls back to hybrid retrieval so the query
        still gets a useful schema context rather than an empty one.

        Args:
            normalized_text: Normalized query text
            domain_category: Domain category from normalizer

        Returns:
            Filtered schema context as DDL string
        """
        # Step 1: Select relevant tables
        if domain_category != 'multi':
            selected_tables = [domain_category]
        else:
            # Multi-domain: select up to 4 tables (raised from 3 to handle
            # queries that genuinely span 4 tables, e.g. cpu+proc+disc+tmf)
            selected_tables = self._score_and_select_tables(normalized_text, top_n=4)

        # Step 2: Build filtered schema context
        schema_context = self._build_schema_context(selected_tables, normalized_text)

        # Step 3: Fallback — if single-domain produced a very thin context
        # (only key columns, no domain-specific columns), the classifier may
        # have fired on a generic keyword.  Re-run hybrid retrieval and use
        # whichever result is richer.
        if domain_category != 'multi' and len(selected_tables) == 1:
            # Count non-key, non-comment lines in the DDL as a proxy for
            # domain-specific column coverage
            domain_lines = [
                l for l in schema_context.split('\n')
                if l.strip() and not l.strip().startswith('--')
                and 'CREATE TABLE' not in l and l.strip() != ');'
            ]
            # If fewer than 4 domain-specific columns surfaced, try hybrid
            if len(domain_lines) < 4:
                hybrid_tables = self._score_and_select_tables(normalized_text, top_n=2)
                if hybrid_tables and hybrid_tables[0] != domain_category:
                    hybrid_context = self._build_schema_context(hybrid_tables, normalized_text)
                    hybrid_lines = [
                        l for l in hybrid_context.split('\n')
                        if l.strip() and not l.strip().startswith('--')
                        and 'CREATE TABLE' not in l and l.strip() != ');'
                    ]
                    if len(hybrid_lines) > len(domain_lines):
                        selected_tables = hybrid_tables
                        schema_context = hybrid_context

        # Step 4: Inject join hints when multiple tables are in play
        if len(selected_tables) > 1:
            join_section = self._build_join_hints(selected_tables)
            if join_section:
                schema_context += "\n" + join_section

        return schema_context

    # ── Table corpus ──────────────────────────────────────────────────────────

    def _build_table_corpus(self) -> Tuple[List[str], List[str]]:
        """Build the per-table document used for scoring (names + texts)."""
        table_names: List[str] = []
        table_texts: List[str] = []

        for table_name, table_def in self.schema.items():
            if not (isinstance(table_def, dict) and 'columns' in table_def):
                continue
            table_names.append(table_name)

            parts: List[str] = [table_name]
            if 'entity_type' in table_def:
                parts.append(str(table_def['entity_type']))
            if 'purpose' in table_def:
                parts.append(str(table_def['purpose']))
            for ident in table_def.get('identity_columns', []) or []:
                parts.append(str(ident))

            # Include both column names AND descriptions so literal token
            # matches (e.g. user types "cpu_busy_time") have something to hit.
            for col_name, col_def in table_def.get('columns', {}).items():
                if not isinstance(col_def, dict):
                    continue
                parts.append(col_name.replace('_', ' '))
                desc = col_def.get('description', '')
                if desc:
                    parts.append(desc)

            table_texts.append(' '.join(parts))

        return table_names, table_texts

    # ── BM25 lexical scoring ──────────────────────────────────────────────────

    def _ensure_bm25_index(self) -> bool:
        """Build the BM25 index on first use. Returns True on success."""
        if self._bm25 is not None:
            return True
        if BM25Okapi is None:
            return False

        names, texts = self._build_table_corpus()
        if not texts:
            return False

        tokenized_corpus = [_tokenize(t) for t in texts]
        self._bm25 = BM25Okapi(tokenized_corpus)
        self._bm25_table_names = names
        print(f"[SchemaLinker] BM25 index built — {len(names)} tables")
        return True

    def _bm25_rank(self, query_text: str) -> List[str]:
        """Return table names ranked by BM25 score (descending)."""
        if not self._ensure_bm25_index():
            return []
        assert self._bm25 is not None

        query_tokens = _tokenize(query_text)
        if not query_tokens:
            return list(self._bm25_table_names)

        scores = self._bm25.get_scores(query_tokens)
        order = np.argsort(scores)[::-1]
        return [self._bm25_table_names[i] for i in order]

    # ── Vector (embedding) scoring ────────────────────────────────────────────

    def _ensure_table_embeddings(self) -> bool:
        """Compute per-table embeddings on first use. Returns True on success."""
        if self._table_embeddings is not None:
            return True

        model = embeddings.get()
        if model is None:
            return False

        names, texts = self._build_table_corpus()
        if not texts:
            return False

        print(f"[SchemaLinker] Embedding {len(texts)} tables for semantic matching...")
        self._table_embeddings = np.asarray(model.encode(texts, normalize_embeddings=True))
        self._table_embedding_names = names
        return True

    def _vector_rank(self, query_text: str) -> List[str]:
        """Return table names ranked by dense vector similarity (descending)."""
        if not self._ensure_table_embeddings():
            return []
        assert self._table_embeddings is not None

        model = embeddings.get()
        if model is None:
            return []
        query_vec = np.asarray(model.encode([query_text], normalize_embeddings=True))[0]
        sims = self._table_embeddings @ query_vec  # rows already normalized
        order = np.argsort(sims)[::-1]
        return [self._table_embedding_names[i] for i in order]

    # ── Hybrid scoring (BM25 + Vector + RRF) ──────────────────────────────────

    def _score_and_select_tables(self, query_text: str, top_n: int = 4) -> List[str]:
        """
        Score tables against the query using hybrid retrieval and return the
        top N.

        Combines BM25 (lexical) and BAAI/bge-large-en-v1.5 (dense vector)
        rankings via Reciprocal Rank Fusion. Falls back gracefully when one
        or both retrieval paths are unavailable (e.g. cold start before the
        embedding model has finished loading).
        """
        ranked_lists: List[List[str]] = []

        # Lexical path — BM25
        bm25_ranked = self._bm25_rank(query_text)
        if bm25_ranked:
            ranked_lists.append(bm25_ranked)

        # Semantic path — dense embeddings
        vector_ranked = self._vector_rank(query_text)
        if vector_ranked:
            ranked_lists.append(vector_ranked)

        if not ranked_lists:
            # Neither retriever is available — return first table as fallback
            table_names = [
                name for name, defn in self.schema.items()
                if isinstance(defn, dict) and 'columns' in defn
            ]
            return table_names[:1]

        # Merge with RRF
        fused = reciprocal_rank_fusion(ranked_lists, k=60)

        # Take top_n; require a minimum RRF score to avoid noise.  With two
        # lists the theoretical max RRF score for rank-1 is 2/(60+1) ≈ 0.0328.
        # A threshold of 0.005 filters out items appearing only at the very
        # bottom of a single list.
        min_score = 0.005
        selected = [name for name, score in fused[:top_n] if score >= min_score]

        if not selected:
            # Safety net — always return at least the top-ranked table
            selected = [fused[0][0]]

        return selected
    
    # ── Counter-type formula hints ────────────────────────────────────────────

    # Maps counter_type → the correct SQL formula fragment to append as a
    # comment in the DDL.  These are universal across ALL tables because
    # delta_time is a shared header column with identical semantics everywhere.
    #
    # The hint is intentionally terse so it fits on one comment line without
    # blowing up the context window.  The prompt rules reinforce the same
    # formulas at a higher level.
    _COUNTER_FORMULA: Dict[str, str] = {
        # Busy counters: value is microseconds busy → divide by delta_time for %
        "Busy":          "% = col*100.0/NULLIF(delta_time,0); use MAX(delta_time) when grouping",
        # Queue counters: value is cumulative queue time → divide by delta_time for AQL
        "Queue":         "AQL = col*1.0/NULLIF(delta_time,0); use MAX(delta_time) when grouping",
        # Queue-Busy: time queue was non-empty → divide by delta_time for %
        "Queue-Busy":    "% = col*100.0/NULLIF(delta_time,0); use MAX(delta_time) when grouping",
        # Incrementing: event count → divide by delta_time (µs) for per-second rate
        "Incrementing":  "rate/s = col*1000000.0/NULLIF(delta_time,0); use MAX(delta_time) when grouping",
        # Accumulating: byte/block count → divide by delta_time for throughput/s
        "Accumulating":  "throughput/s = col*1000000.0/NULLIF(delta_time,0); use MAX(delta_time) when grouping",
        # Response-time: cumulative time → divide by transaction count for avg
        "Response-time": "avg = col/NULLIF(transaction_count,0)",
        # Lockwait: cumulative lock wait → divide by requests_blocked for avg
        "Lockwait":      "avg_us = col/NULLIF(requests_blocked,0)",
        # Snapshot: point-in-time value — no formula needed, use directly
        "Snapshot":      "point-in-time value; use directly, no rate conversion",
    }

    @staticmethod
    def _build_col_comment(col_def: Dict) -> str:
        """
        Build the full inline comment for a column in the DDL output.

        Combines description, unit, and a formula hint derived from
        counter_type so the LLM always knows how to use the column correctly.
        """
        parts = []

        desc = (col_def.get('description') or '').strip()
        if desc:
            parts.append(desc[:120])

        unit = col_def.get('unit')
        if unit:
            parts.append(f"unit={unit}")

        counter_type = (col_def.get('counter_type') or '').strip()
        if counter_type:
            formula = SchemaLinker._COUNTER_FORMULA.get(counter_type, '')
            if formula:
                parts.append(f"[{counter_type}] {formula}")
            else:
                parts.append(f"[{counter_type}]")

        return ' | '.join(parts) if parts else ''

    # ── Related-table injection ───────────────────────────────────────────────

    # When a single-domain query targets one of these tables, automatically
    # include a minimal reference block from the companion table so the LLM
    # has the correct denominator columns available.
    #
    # Key   = primary table selected by the domain classifier
    # Value = companion table to inject (key columns + delta_time only)
    _COMPANION_TABLES: Dict[str, str] = {
        'proc':  'cpu',    # proc % calculations need cpu.delta_time as reference
        'dfile': 'disc',   # dfile physical I/O context needs disc device info
        'dopen': 'dfile',  # dopen opener context needs dfile file-level stats
        'file':  'dfile',  # file logical I/O pairs with dfile physical I/O
        'ossns': 'proc',   # ossns process stats pair with proc for CPU context
        'tmf':   'proc',   # tmf transaction stats pair with proc for process context
    }

    def _inject_companion_table(self, primary_table: str, query_text: str) -> str:
        """
        Return a minimal DDL block for the companion table of primary_table.

        Only includes identity columns, time columns, and delta_time so the
        LLM has the correct denominator without flooding the context window.
        Returns empty string if no companion is defined or companion is already
        in the selected tables.
        """
        companion = self._COMPANION_TABLES.get(primary_table)
        if not companion or companion not in self.schema:
            return ''

        table_def = self.schema[companion]
        identity_cols = set(table_def.get('identity_columns', []) or [])
        time_cols = set(table_def.get('time_columns', []) or [])
        always_include = identity_cols | time_cols | {'delta_time'}

        col_lines = []
        for col_name, col_def in table_def.get('columns', {}).items():
            if not isinstance(col_def, dict):
                continue
            if not col_def.get('queryable', True):
                continue
            if col_name not in always_include:
                continue

            sanitized = col_name.replace('.', '_').replace('{N}', '0')
            col_type = self._map_type(col_def.get('type', 'string'))
            comment = self._build_col_comment(col_def)
            line = f"    {sanitized} {col_type}"
            if comment:
                line += f"  -- {comment}"
            col_lines.append(line)

        if not col_lines:
            return ''

        ddl = (
            f"-- Reference table: macht413.{companion} "
            f"(included for correct denominator columns)\n"
            f"CREATE TABLE macht413.{companion} (\n"
            + ',\n'.join(col_lines)
            + "\n);\n"
        )
        return ddl

    # ── Schema context builder ────────────────────────────────────────────────

    def _build_schema_context(self, table_names: List[str], query_text: str) -> str:
        """
        Build filtered schema context with relevant columns.

        Each column comment now includes:
          - description (truncated)
          - unit (if present)
          - counter_type + correct formula hint

        For single-domain queries, a minimal companion table block is appended
        so the LLM always has the correct denominator columns available.

        Args:
            table_names: List of table names to include
            query_text: Query text for column relevance scoring

        Returns:
            DDL-style schema context string
        """
        context_parts = []

        for table_name in table_names:
            if table_name not in self.schema:
                continue

            table_def = self.schema[table_name]

            # Get relevant columns
            columns = self._select_relevant_columns(table_name, table_def, query_text)

            if not columns:
                continue

            # Build CREATE TABLE DDL
            ddl = f"-- Table: macht413.{table_name}\n"

            if 'purpose' in table_def:
                ddl += f"-- Purpose: {table_def['purpose'][:200]}...\n"

            ddl += f"CREATE TABLE macht413.{table_name} (\n"

            col_lines = []
            for col_name, col_def in columns:
                col_type = self._map_type(col_def.get('type', 'string'))

                # Sanitize column name
                sanitized_name = col_name.replace('.', '_').replace('{N}', '0')

                # Build rich comment: description + unit + counter formula
                comment = self._build_col_comment(col_def)

                col_line = f"    {sanitized_name} {col_type}"
                if comment:
                    col_line += f"  -- {comment}"

                col_lines.append(col_line)

            ddl += ',\n'.join(col_lines)
            ddl += "\n);\n"

            context_parts.append(ddl)

        schema_str = '\n'.join(context_parts)

        # For single-domain queries, inject the companion table reference block
        # so the LLM has the correct denominator columns without needing to
        # guess or join to a table it wasn't told about.
        if len(table_names) == 1:
            companion_ddl = self._inject_companion_table(table_names[0], query_text)
            if companion_ddl:
                schema_str += '\n' + companion_ddl

        return schema_str
    
    def _select_relevant_columns(self, table_name: str, table_def: Dict,
                                  query_text: str, max_cols: int = 20) -> List[Tuple[str, Dict]]:
        """
        Select the most relevant columns for the query.

        Selection priority (highest → lowest):
          1. Structural key columns — always included (system_name, cpu_num,
             from_timestamp, to_timestamp, delta_time, identity columns).
          2. Exact-name matches — any column whose name (with underscores
             replaced by spaces) appears verbatim in the query text.  These
             are guaranteed to be included before semantic ranking runs,
             regardless of how the embedding model scores them.
          3. Semantic / BM25 ranking — remaining slots filled by the hybrid
             column ranker.

        The max_cols cap is applied after all three tiers so that exact-name
        matches are never displaced by lower-priority columns.
        """
        columns = table_def.get('columns', {})

        # Tier 1: structural key columns — always include
        key_columns = {'system_name', 'cpu_num', 'from_timestamp', 'to_timestamp',
                       'delta_time', 'device_name', 'process_name', 'file_name'}

        # Also treat identity_columns from the schema as keys
        for ident in table_def.get('identity_columns', []) or []:
            key_columns.add(ident.lower())

        # Tier 2: exact-name matches — column name (normalised) appears in query
        query_lower = query_text.lower()
        # Build a set of query tokens for fast lookup
        query_tokens = set(re.split(r'[^a-z0-9_]+', query_lower))

        selected_keys: List[Tuple[str, Dict]] = []
        exact_matches: List[Tuple[str, Dict]] = []
        remaining: List[Tuple[str, Dict]] = []

        for col_name, col_def in columns.items():
            if not isinstance(col_def, dict):
                continue
            if not col_def.get('queryable', True):
                continue

            col_lower = col_name.lower()

            # Tier 1 check
            is_key = any(key in col_lower for key in key_columns)
            if is_key:
                selected_keys.append((col_name, col_def))
                continue

            # Tier 2 check: exact token match (handles both "cpu_busy_time" and
            # "cpu busy time" phrasings in the query)
            col_token = col_lower.replace('.', '_')
            col_spaced = col_lower.replace('_', ' ').replace('.', ' ')
            is_exact = (
                col_token in query_tokens
                or col_spaced in query_lower
                or col_lower in query_lower
            )
            if is_exact:
                exact_matches.append((col_name, col_def))
            else:
                remaining.append((col_name, col_def))

        # Fill remaining slots with semantic / BM25 ranking
        used = len(selected_keys) + len(exact_matches)
        remaining_slots = max(0, max_cols - used)
        ranked_remaining: List[Tuple[str, Dict]] = []
        if remaining and remaining_slots > 0:
            ranked_remaining = self._rank_columns_by_relevance(
                table_name, remaining, query_text
            )[:remaining_slots]

        # Combine: keys first, then exact matches, then ranked remainder
        result = selected_keys + exact_matches + ranked_remaining
        return result[:max_cols]

    def _rank_columns_by_relevance(
        self,
        table_name: str,
        candidates: List[Tuple[str, Dict]],
        query_text: str,
    ) -> List[Tuple[str, Dict]]:
        """Rank candidate columns by relevance to the query.

        Uses hybrid retrieval — BM25 (lexical) + BGE-large (dense vector) —
        merged with Reciprocal Rank Fusion, mirroring the table-level strategy.

        BM25 catches exact column name / description token matches (e.g. the
        user typed "cpu_busy_time" verbatim).  Dense embeddings handle semantic
        paraphrases (e.g. "processor utilization" → cpu_busy_time).  RRF
        combines both without needing to tune relative weights.

        Falls back to keyword overlap when neither retriever is available
        (cold start before the embedding model has loaded).
        """
        if not candidates:
            return []

        ranked_lists: List[List[str]] = []
        col_names = [name for name, _ in candidates]
        by_name = {name: defn for name, defn in candidates}

        # ── BM25 lexical path ─────────────────────────────────────────────────
        if BM25Okapi is not None:
            # Build a tiny per-column corpus: "col_name_with_spaces description unit"
            col_docs = []
            for col_name, col_def in candidates:
                parts = [col_name.replace('_', ' ').replace('.', ' ')]
                desc = col_def.get('description', '')
                if desc:
                    parts.append(desc)
                unit = col_def.get('unit')
                if unit:
                    parts.append(str(unit))
                col_docs.append(' '.join(parts))

            tokenized_corpus = [_tokenize(doc) for doc in col_docs]
            query_tokens = _tokenize(query_text)

            if query_tokens and any(tokenized_corpus):
                try:
                    bm25_col = BM25Okapi(tokenized_corpus)
                    scores = bm25_col.get_scores(query_tokens)
                    order = np.argsort(scores)[::-1]
                    ranked_lists.append([col_names[i] for i in order])
                except Exception:
                    pass  # BM25 failure is non-fatal — dense path still runs

        # ── Dense vector path ─────────────────────────────────────────────────
        model = embeddings.get()
        if model is not None:
            names, matrix = self._ensure_column_embeddings(table_name, candidates, model)
            if matrix is not None and matrix.size:
                qv = np.asarray(model.encode([query_text], normalize_embeddings=True))[0]
                sims = matrix @ qv
                order = np.argsort(sims)[::-1]
                ranked_lists.append([names[i] for i in order if names[i] in by_name])

        # ── Merge with RRF ────────────────────────────────────────────────────
        if len(ranked_lists) >= 2:
            fused = reciprocal_rank_fusion(ranked_lists, k=60)
            return [(name, by_name[name]) for name, _ in fused if name in by_name]

        if len(ranked_lists) == 1:
            # Only one retriever available — use it directly
            return [(name, by_name[name]) for name in ranked_lists[0] if name in by_name]

        # ── Fallback: keyword overlap ─────────────────────────────────────────
        # Reached only when both BM25 and the embedding model are unavailable.
        query_words = set(query_text.lower().split())
        scored = []
        for col_name, col_def in candidates:
            score = 0
            col_words = set(col_name.lower().replace('_', ' ').split())
            score += len(query_words & col_words) * 2
            desc = col_def.get('description', '').lower()
            for word in query_words:
                if len(word) > 3 and word in desc:
                    score += 1
            scored.append((score, col_name, col_def))
        scored.sort(reverse=True, key=lambda x: x[0])
        return [(name, defn) for _, name, defn in scored]

    def _ensure_column_embeddings(
        self,
        table_name: str,
        candidates: List[Tuple[str, Dict]],
        model,
    ) -> Tuple[List[str], Optional[np.ndarray]]:
        """Return (names, matrix) for the candidate columns, computing once and caching."""
        cached = self._column_embeddings.get(table_name)
        candidate_names = [name for name, _ in candidates]
        if cached is not None and cached[0] == candidate_names:
            return cached

        docs = []
        for col_name, col_def in candidates:
            parts = [col_name.replace('_', ' ').replace('.', ' ')]
            desc = col_def.get('description', '')
            if desc:
                parts.append(desc)
            unit = col_def.get('unit')
            if unit:
                parts.append(str(unit))
            docs.append(' '.join(parts))

        if not docs:
            return candidate_names, None

        matrix = np.asarray(model.encode(docs, normalize_embeddings=True))
        self._column_embeddings[table_name] = (candidate_names, matrix)
        return candidate_names, matrix
    
    def _build_join_hints(self, table_names: List[str]) -> str:
        """
        Build a JOIN HINTS block for the selected tables.

        Pulls per-table `join_hints` from the schema and keeps only those that
        reference another selected table. Falls back to the intersection of
        `identity_columns` for pairs without an explicit hint.
        """
        import re as _re

        selected = set(table_names)
        lines: List[str] = []
        seen_pairs = set()

        for table_name in table_names:
            table_def = self.schema.get(table_name)
            if not isinstance(table_def, dict):
                continue

            for hint in table_def.get('join_hints', []) or []:
                match = _re.search(r'JOIN\s+(\w+)', hint)
                if not match:
                    continue
                other = match.group(1)
                if other not in selected or other == table_name:
                    continue
                pair = tuple(sorted((table_name, other)))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                lines.append(f"-- {table_name} <-> {other}: {hint}")

        # Fallback: any selected pair without a hint gets an identity-column
        # intersection so the LLM still has explicit keys to use.
        for i, a in enumerate(table_names):
            for b in table_names[i + 1:]:
                pair = tuple(sorted((a, b)))
                if pair in seen_pairs:
                    continue
                a_ids = set(self.schema.get(a, {}).get('identity_columns', []) or [])
                b_ids = set(self.schema.get(b, {}).get('identity_columns', []) or [])
                shared = a_ids & b_ids
                if not shared:
                    continue
                keys = ', '.join(sorted(shared))
                lines.append(f"-- {a} <-> {b}: JOIN on ({keys}) [from shared identity columns]")
                seen_pairs.add(pair)

        if not lines:
            return ""

        header = (
            "-- JOIN HINTS (use these keys instead of guessing):\n"
            "-- Reminder: from_timestamp is microsecond-precision across tables; "
            "either pre-aggregate per table or bucket via date_trunc('second', from_timestamp) before joining.\n"
            "-- When aggregating across joined tables, ALWAYS pre-aggregate each side "
            "in its own CTE first, then join the CTEs. Joining raw rows then aggregating "
            "multiplies rows by the other table's cardinality and produces weighted/incorrect averages."
        )
        return header + "\n" + "\n".join(lines) + "\n"

    def _map_type(self, yaml_type: str) -> str:
        """Map YAML type to SQL type."""
        type_map = {
            'string': 'TEXT',
            'integer': 'BIGINT',
            'datetime': 'TIMESTAMP',
            'bitmask': 'INTEGER',
        }
        return type_map.get(yaml_type, 'TEXT')


# Test the schema linker
if __name__ == "__main__":
    print("Testing Schema Linker...")
    print("=" * 60)
    
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    
    from pipeline.schema_loader import load_schema
    from pipeline.normalizer import QueryNormalizer
    
    try:
        # Load schema
        loader = load_schema('schema_store/enriched_schema.yaml')
        schema = loader.get_schema()
        
        # Initialize components
        normalizer = QueryNormalizer()
        linker = SchemaLinker(schema)
        
        # Wait for embedding model (needed for full hybrid scoring)
        print("\n[Setup] Waiting for embedding model to load...")
        embeddings.wait(timeout=120)
        if embeddings.is_ready():
            print("[Setup] Model ready.\n")
        else:
            print("[Setup] Model not ready — will use BM25-only fallback.\n")
        
        # Test cases
        test_queries = [
            "Show CPU busy time per CPU",
            "List disk reads and writes",
            "Compare CPU and process utilization",
        ]
        
        for query in test_queries:
            print(f"\nQuery: '{query}'")
            print("-" * 60)
            
            # Normalize
            result = normalizer.normalize(query)
            normalized = result['normalized_text']
            domain = result['domain_category']
            
            print(f"Domain: {domain}")
            
            # Link schema
            context = linker.link_schema(normalized, domain)
            
            # Show first 500 chars of context
            print(f"Schema Context ({len(context)} chars):")
            print(context[:500] + "..." if len(context) > 500 else context)
        
        print("\n" + "=" * 60)
        print("✓ Schema Linker test complete!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
