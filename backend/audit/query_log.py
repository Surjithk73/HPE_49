"""
Audit Log for QueryCraft
Logs all query executions to SQLite database.

Improvements:
- get_stats() returns full analytics: total queries, cache hit rate,
  avg execution time, top 10 domains, validation failure rate, retry rate.
- pipeline_stages JSON column captures per-stage data for the clarification
  pipeline: questions asked, final spec, assumptions surfaced, SQL attempts.
"""
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import os


class AuditLog:
    """Manages query audit logging."""

    # Stats are cached in memory for this many seconds to avoid running
    # 6 SQLite queries on every /api/stats poll.
    _STATS_CACHE_TTL = 60

    def __init__(self, db_path: str = "audit/query_log.db"):
        """
        Initialize the audit log.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._stats_cache: dict = {}
        self._stats_cache_ts: float = 0.0

        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Initialize database
        self._init_database()

    def _init_database(self):
        """Create the query_log table if it doesn't exist."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS query_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    original_input TEXT NOT NULL,
                    normalized_input TEXT NOT NULL,
                    domain_category TEXT,
                    generated_sql TEXT,
                    validation_passed INTEGER,
                    validation_error TEXT,
                    cache_hit INTEGER,
                    cache_confidence REAL,
                    row_count INTEGER,
                    execution_time_ms INTEGER,
                    export_format TEXT,
                    llm_retries INTEGER DEFAULT 0
                )
            """)

            # Add llm_retries column to existing databases that pre-date this column
            try:
                cursor.execute("ALTER TABLE query_log ADD COLUMN llm_retries INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Column already exists — safe to ignore

            # Add cache_confidence column to existing databases that pre-date this column
            try:
                cursor.execute("ALTER TABLE query_log ADD COLUMN cache_confidence REAL")
            except sqlite3.OperationalError:
                pass  # Column already exists — safe to ignore

            # pipeline_stages: JSON blob capturing per-stage data from the
            # clarification pipeline (questions asked, spec, assumptions, SQL attempts).
            try:
                cursor.execute("ALTER TABLE query_log ADD COLUMN pipeline_stages TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists — safe to ignore

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Warning: Failed to initialize audit log database: {e}")

    def log_query(self, entry: Dict) -> None:
        """
        Log a query execution.

        Args:
            entry: Dictionary with query execution details
                - original_input:    Original user query
                - normalized_input:  Normalized query text
                - domain_category:   Detected domain
                - generated_sql:     Generated SQL
                - validation_passed: Boolean (0 or 1)
                - validation_error:  Error message if validation failed
                - cache_hit:         Boolean (0 or 1)
                - row_count:         Number of rows returned
                - execution_time_ms: Execution time in milliseconds
                - export_format:     Export format (csv, excel, pdf) or None
                - llm_retries:       Number of LLM retry attempts (0 = first try succeeded)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            timestamp = datetime.now().isoformat()

            # pipeline_stages is optional; serialise dict/list to JSON if provided.
            stages_raw = entry.get('pipeline_stages')
            stages_json = json.dumps(stages_raw) if stages_raw is not None else None

            cursor.execute("""
                INSERT INTO query_log (
                    timestamp, original_input, normalized_input, domain_category,
                    generated_sql, validation_passed, validation_error, cache_hit,
                    cache_confidence, row_count, execution_time_ms, export_format,
                    llm_retries, pipeline_stages
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                entry.get('original_input', ''),
                entry.get('normalized_input', ''),
                entry.get('domain_category', ''),
                entry.get('generated_sql', ''),
                1 if entry.get('validation_passed', False) else 0,
                entry.get('validation_error', None),
                1 if entry.get('cache_hit', False) else 0,
                entry.get('cache_confidence', None),
                entry.get('row_count', None),
                entry.get('execution_time_ms', None),
                entry.get('export_format', None),
                entry.get('llm_retries', 0),
                stages_json,
            ))

            conn.commit()
            conn.close()
            # Invalidate the stats cache so the next /api/stats call reflects
            # the new entry without waiting for the TTL to expire.
            self._stats_cache = {}
            self._stats_cache_ts = 0.0

        except Exception as e:
            # Never raise — logging must not break the application
            print(f"Warning: Failed to log query: {e}")

    def get_history(self, limit: int = 50) -> List[Dict]:
        """
        Get recent query history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of query log entries (most recent first)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM query_log
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            history = [dict(row) for row in rows]
            conn.close()
            return history

        except Exception as e:
            print(f"Warning: Failed to retrieve query history: {e}")
            return []

    def get_stats(self) -> Dict:
        """
        Compute analytics over the full audit log.

        Results are cached in memory for _STATS_CACHE_TTL seconds so that
        frequent polling (e.g. a dashboard that refreshes every few seconds)
        doesn't hammer SQLite with repeated full-table scans.

        Returns a dict with:
            total_queries          — total rows in the log
            cache_hit_rate         — fraction of queries served from cache
            avg_execution_time_ms  — mean execution time (cache hits included)
            top_domains            — top 10 domains by query count
            validation_failure_rate — fraction of queries that failed validation
            retry_rate             — fraction of queries that needed at least one LLM retry
        """
        import time
        now = time.monotonic()
        if self._stats_cache and (now - self._stats_cache_ts) < self._STATS_CACHE_TTL:
            return self._stats_cache

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # ── Total queries ─────────────────────────────────────────────────
            cursor.execute("SELECT COUNT(*) FROM query_log")
            total_queries: int = cursor.fetchone()[0]

            if total_queries == 0:
                conn.close()
                return {
                    "total_queries":           0,
                    "cache_hit_rate":          0.0,
                    "avg_execution_time_ms":   0.0,
                    "top_domains":             [],
                    "validation_failure_rate": 0.0,
                    "retry_rate":              0.0,
                }

            # ── Cache hits ────────────────────────────────────────────────────
            cursor.execute("SELECT COUNT(*) FROM query_log WHERE cache_hit = 1")
            cache_hits: int = cursor.fetchone()[0]

            # ── Average execution time (all queries that have a time recorded) ─
            cursor.execute(
                "SELECT AVG(execution_time_ms) FROM query_log WHERE execution_time_ms IS NOT NULL"
            )
            avg_exec_raw = cursor.fetchone()[0]
            avg_execution_time_ms: float = round(avg_exec_raw, 2) if avg_exec_raw is not None else 0.0

            # ── Top 10 domains ────────────────────────────────────────────────
            cursor.execute("""
                SELECT domain_category, COUNT(*) AS cnt
                FROM query_log
                WHERE domain_category IS NOT NULL AND domain_category != ''
                GROUP BY domain_category
                ORDER BY cnt DESC
                LIMIT 10
            """)
            top_domains = [
                {"domain": row[0], "count": row[1]}
                for row in cursor.fetchall()
            ]

            # ── Validation failures ───────────────────────────────────────────
            cursor.execute("SELECT COUNT(*) FROM query_log WHERE validation_passed = 0")
            validation_failures: int = cursor.fetchone()[0]

            # ── Retry rate ────────────────────────────────────────────────────
            # llm_retries > 0 means the LLM needed at least one retry.
            # Cache hits never touch the LLM so we exclude them from the
            # denominator (only non-cache-hit queries can have retries).
            cursor.execute(
                "SELECT COUNT(*) FROM query_log WHERE cache_hit = 0 AND llm_retries > 0"
            )
            retried_queries: int = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM query_log WHERE cache_hit = 0")
            non_cache_queries: int = cursor.fetchone()[0]

            conn.close()

            result = {
                "total_queries":           total_queries,
                "cache_hit_rate":          round(cache_hits / total_queries, 4),
                "avg_execution_time_ms":   avg_execution_time_ms,
                "top_domains":             top_domains,
                "validation_failure_rate": round(validation_failures / total_queries, 4),
                "retry_rate":              round(retried_queries / non_cache_queries, 4)
                                           if non_cache_queries > 0 else 0.0,
            }
            # Write to in-memory cache
            self._stats_cache = result
            self._stats_cache_ts = now
            return result

        except Exception as e:
            print(f"Warning: Failed to retrieve stats: {e}")
            return {}


# ── Self-test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Audit Log...")
    print("=" * 80)

    test_db = "audit/test_query_log.db"

    if os.path.exists(test_db):
        os.remove(test_db)

    try:
        audit = AuditLog(test_db)
        print("✓ Audit log initialized")

        # Seed with varied entries
        entries = [
            # (domain, validation_passed, cache_hit, exec_ms, retries)
            ("cpu",   True,  False, 150, 0),
            ("cpu",   True,  True,  45,  0),
            ("disc",  True,  False, 200, 1),
            ("proc",  False, False, None, 0),
            ("tmf",   True,  False, 180, 2),
            ("cpu",   True,  True,  40,  0),
            ("multi", True,  False, 320, 0),
            ("disc",  False, False, None, 0),
        ]

        for domain, passed, hit, ms, retries in entries:
            audit.log_query({
                'original_input':    f'query about {domain}',
                'normalized_input':  f'query about {domain}',
                'domain_category':   domain,
                'generated_sql':     f'SELECT * FROM macht413.{domain} LIMIT 10',
                'validation_passed': passed,
                'validation_error':  None if passed else 'Column does not exist',
                'cache_hit':         hit,
                'row_count':         100 if passed else None,
                'execution_time_ms': ms,
                'export_format':     None,
                'llm_retries':       retries,
            })

        print(f"✓ Seeded {len(entries)} log entries")

        # Retrieve and verify stats
        stats = audit.get_stats()
        print("\n── Stats ──────────────────────────────────────────────────────")
        print(f"  total_queries:           {stats['total_queries']}")
        print(f"  cache_hit_rate:          {stats['cache_hit_rate']:.2%}")
        print(f"  avg_execution_time_ms:   {stats['avg_execution_time_ms']} ms")
        print(f"  validation_failure_rate: {stats['validation_failure_rate']:.2%}")
        print(f"  retry_rate:              {stats['retry_rate']:.2%}")
        print(f"  top_domains:")
        for d in stats['top_domains']:
            print(f"    {d['domain']:10s} → {d['count']} queries")

        assert stats['total_queries'] == 8,                    "✗ total_queries"
        assert stats['cache_hit_rate'] == round(2/8, 4),       "✗ cache_hit_rate"
        assert stats['validation_failure_rate'] == round(2/8, 4), "✗ validation_failure_rate"
        # 2 retried out of 6 non-cache queries
        assert stats['retry_rate'] == round(2/6, 4),           "✗ retry_rate"
        assert len(stats['top_domains']) <= 10,                "✗ top_domains length"

        print("\n✓ All assertions passed!")

        # Cleanup
        if os.path.exists(test_db):
            os.remove(test_db)
        print("✓ Test database cleaned up")

        print("\n" + "=" * 80)
        print("✓ All Audit Log tests passed!")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
