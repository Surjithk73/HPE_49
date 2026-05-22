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

        # BM25 index — built lazily on first scoring call.
        self._bm25: Optional["BM25Okapi"] = None
        self._bm25_table_names: List[str] = []

        # Make sure the shared model is loading. Idempotent — safe to call from
        # multiple components.
        embeddings.start_loading()

    # ── Public API ────────────────────────────────────────────────────────────

    def link_schema(self, normalized_text: str, domain_category: str) -> str:
        """
        Select relevant tables and columns for the query.
        
        Args:
            normalized_text: Normalized query text
            domain_category: Domain category from normalizer
            
        Returns:
            Filtered schema context as DDL string
        """
        # Step 1: Select relevant tables
        if domain_category != 'multi':
            # Single domain - use that table only
            selected_tables = [domain_category]
        else:
            # Multi-domain - score all tables
            selected_tables = self._score_and_select_tables(normalized_text)
        
        # Step 2: Build filtered schema context
        schema_context = self._build_schema_context(selected_tables, normalized_text)

        # Step 3: Inject join hints when multiple tables are in play, so the
        # LLM doesn't have to guess the join keys.
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
        assert model is not None
        query_vec = np.asarray(model.encode([query_text], normalize_embeddings=True))[0]
        sims = self._table_embeddings @ query_vec  # rows already normalized
        order = np.argsort(sims)[::-1]
        return [self._table_embedding_names[i] for i in order]

    # ── Hybrid scoring (BM25 + Vector + RRF) ──────────────────────────────────

    def _score_and_select_tables(self, query_text: str, top_n: int = 3) -> List[str]:
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
    
    # ── Schema context builder ────────────────────────────────────────────────

    def _build_schema_context(self, table_names: List[str], query_text: str) -> str:
        """
        Build filtered schema context with relevant columns.
        
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
                desc = col_def.get('description', '')
                
                # Sanitize column name
                sanitized_name = col_name.replace('.', '_').replace('{N}', '0')
                
                col_line = f"    {sanitized_name} {col_type}"
                if desc:
                    col_line += f"  -- {desc[:100]}"
                
                col_lines.append(col_line)
            
            ddl += ',\n'.join(col_lines)
            ddl += "\n);\n"
            
            context_parts.append(ddl)
        
        return '\n'.join(context_parts)
    
    def _select_relevant_columns(self, table_name: str, table_def: Dict, 
                                  query_text: str, max_cols: int = 20) -> List[Tuple[str, Dict]]:
        """
        Select most relevant columns for the query.
        
        Args:
            table_name: Name of the table
            table_def: Table definition
            query_text: Query text
            max_cols: Maximum columns to return
            
        Returns:
            List of (column_name, column_def) tuples
        """
        columns = table_def.get('columns', {})
        
        # Always include these key columns if present
        key_columns = ['system_name', 'cpu_num', 'from_timestamp', 'to_timestamp', 
                       'delta_time', 'device_name', 'process_name', 'file_name']
        
        selected = []
        remaining = []
        
        for col_name, col_def in columns.items():
            if not isinstance(col_def, dict):
                continue
            
            # Skip non-queryable columns
            if not col_def.get('queryable', True):
                continue
            
            # Check if it's a key column
            is_key = any(key in col_name.lower() for key in key_columns)
            
            if is_key:
                selected.append((col_name, col_def))
            else:
                remaining.append((col_name, col_def))
        
        # Score remaining columns by relevance
        if remaining:
            remaining_slots = max(0, max_cols - len(selected))
            if remaining_slots:
                ranked = self._rank_columns_by_relevance(table_name, remaining, query_text)
                for col_name, col_def in ranked[:remaining_slots]:
                    selected.append((col_name, col_def))

        return selected[:max_cols]

    def _rank_columns_by_relevance(
        self,
        table_name: str,
        candidates: List[Tuple[str, Dict]],
        query_text: str,
    ) -> List[Tuple[str, Dict]]:
        """Rank candidate columns by semantic relevance to the query.

        Uses cached BGE-large embeddings of `col_name + description` when the
        shared model is ready; falls back to keyword overlap on cold start.
        """
        if not candidates:
            return []

        model = embeddings.get()
        if model is not None:
            names, matrix = self._ensure_column_embeddings(table_name, candidates, model)
            if matrix is not None and matrix.size:
                qv = np.asarray(model.encode([query_text], normalize_embeddings=True))[0]
                sims = matrix @ qv
                order = np.argsort(sims)[::-1]
                by_name = {name: defn for name, defn in candidates}
                return [(names[i], by_name[names[i]]) for i in order if names[i] in by_name]

        # Fallback: keyword overlap (original behavior)
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
