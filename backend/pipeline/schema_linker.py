"""
Schema Linker for QueryCraft
Selects relevant tables and columns based on the query.
"""
from typing import Dict, List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class SchemaLinker:
    """Links queries to relevant schema elements."""
    
    def __init__(self, schema: Dict):
        """
        Initialize the schema linker.
        
        Args:
            schema: Loaded schema dictionary from SchemaLoader
        """
        self.schema = schema
        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=100)
    
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
    
    def _score_and_select_tables(self, query_text: str, top_n: int = 3) -> List[str]:
        """
        Score tables using TF-IDF and select top N.
        
        Args:
            query_text: Query text to match against
            top_n: Number of tables to select
            
        Returns:
            List of selected table names
        """
        # Build corpus of table descriptions
        table_names = []
        table_texts = []
        
        for table_name, table_def in self.schema.items():
            if isinstance(table_def, dict) and 'columns' in table_def:
                table_names.append(table_name)
                
                # Combine table purpose and column descriptions
                text_parts = []
                
                # Add table purpose
                if 'purpose' in table_def:
                    text_parts.append(table_def['purpose'])
                
                # Add column descriptions
                for col_name, col_def in table_def.get('columns', {}).items():
                    if isinstance(col_def, dict):
                        desc = col_def.get('description', '')
                        if desc:
                            text_parts.append(desc)
                
                table_texts.append(' '.join(text_parts))
        
        if not table_texts:
            return []
        
        # Compute TF-IDF similarity
        try:
            # Fit vectorizer on table texts + query
            all_texts = table_texts + [query_text]
            tfidf_matrix = self.vectorizer.fit_transform(all_texts)
            
            # Query vector is the last one
            query_vector = tfidf_matrix[-1]
            table_vectors = tfidf_matrix[:-1]
            
            # Compute cosine similarity
            similarities = cosine_similarity(query_vector, table_vectors)[0]
            
            # Get top N tables
            top_indices = np.argsort(similarities)[::-1][:top_n]
            
            # Filter out tables with very low scores (< 0.1)
            selected = [table_names[i] for i in top_indices if similarities[i] > 0.1]
            
            # If no tables scored well, return top 1
            if not selected and table_names:
                selected = [table_names[top_indices[0]]]
            
            return selected
            
        except Exception as e:
            # Fallback: return first table
            print(f"Warning: TF-IDF scoring failed: {e}")
            return [table_names[0]] if table_names else []
    
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
            scored = []
            query_words = set(query_text.lower().split())
            
            for col_name, col_def in remaining:
                score = 0
                
                # Score based on column name match
                col_words = set(col_name.lower().replace('_', ' ').split())
                score += len(query_words & col_words) * 2
                
                # Score based on description match
                desc = col_def.get('description', '').lower()
                for word in query_words:
                    if len(word) > 3 and word in desc:
                        score += 1
                
                scored.append((score, col_name, col_def))
            
            # Sort by score and take top columns
            scored.sort(reverse=True, key=lambda x: x[0])
            
            # Add top scored columns
            remaining_slots = max_cols - len(selected)
            for score, col_name, col_def in scored[:remaining_slots]:
                selected.append((col_name, col_def))
        
        return selected[:max_cols]
    
    def _build_join_hints(self, table_names: List[str]) -> str:
        """
        Build a JOIN HINTS block for the selected tables.

        Pulls per-table `join_hints` from the schema and keeps only those that
        reference another selected table. Falls back to the intersection of
        `identity_columns` for pairs without an explicit hint.
        """
        import re

        selected = set(table_names)
        lines: List[str] = []
        seen_pairs = set()

        for table_name in table_names:
            table_def = self.schema.get(table_name)
            if not isinstance(table_def, dict):
                continue

            for hint in table_def.get('join_hints', []) or []:
                match = re.search(r'JOIN\s+(\w+)', hint)
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
            "either pre-aggregate per table or bucket via date_trunc('second', from_timestamp) before joining."
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
