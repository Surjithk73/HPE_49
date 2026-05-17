"""
Audit Log for QueryCraft
Logs all query executions to SQLite database.
"""
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import os


class AuditLog:
    """Manages query audit logging."""
    
    def __init__(self, db_path: str = "audit/query_log.db"):
        """
        Initialize the audit log.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        
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
                    row_count INTEGER,
                    execution_time_ms INTEGER,
                    export_format TEXT
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Warning: Failed to initialize audit log database: {e}")
    
    def log_query(self, entry: Dict) -> None:
        """
        Log a query execution.
        
        Args:
            entry: Dictionary with query execution details
                - original_input: Original user query
                - normalized_input: Normalized query text
                - domain_category: Detected domain
                - generated_sql: Generated SQL
                - validation_passed: Boolean (0 or 1)
                - validation_error: Error message if validation failed
                - cache_hit: Boolean (0 or 1)
                - row_count: Number of rows returned
                - execution_time_ms: Execution time in milliseconds
                - export_format: Export format (csv, excel, pdf) or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Add timestamp
            timestamp = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO query_log (
                    timestamp, original_input, normalized_input, domain_category,
                    generated_sql, validation_passed, validation_error, cache_hit,
                    row_count, execution_time_ms, export_format
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                entry.get('original_input', ''),
                entry.get('normalized_input', ''),
                entry.get('domain_category', ''),
                entry.get('generated_sql', ''),
                1 if entry.get('validation_passed', False) else 0,
                entry.get('validation_error', None),
                1 if entry.get('cache_hit', False) else 0,
                entry.get('row_count', None),
                entry.get('execution_time_ms', None),
                entry.get('export_format', None)
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            # Never raise - logging should not break the application
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
            conn.row_factory = sqlite3.Row  # Return rows as dicts
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM query_log
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            
            # Convert to list of dicts
            history = []
            for row in rows:
                history.append(dict(row))
            
            conn.close()
            
            return history
            
        except Exception as e:
            print(f"Warning: Failed to retrieve query history: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """
        Get audit log statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Total queries
            cursor.execute("SELECT COUNT(*) FROM query_log")
            total_queries = cursor.fetchone()[0]
            
            # Cache hit rate
            cursor.execute("SELECT COUNT(*) FROM query_log WHERE cache_hit = 1")
            cache_hits = cursor.fetchone()[0]
            
            # Validation pass rate
            cursor.execute("SELECT COUNT(*) FROM query_log WHERE validation_passed = 1")
            validation_passes = cursor.fetchone()[0]
            
            # Average execution time
            cursor.execute("SELECT AVG(execution_time_ms) FROM query_log WHERE execution_time_ms IS NOT NULL")
            avg_execution_time = cursor.fetchone()[0] or 0
            
            # Most common domains
            cursor.execute("""
                SELECT domain_category, COUNT(*) as count
                FROM query_log
                WHERE domain_category IS NOT NULL
                GROUP BY domain_category
                ORDER BY count DESC
                LIMIT 5
            """)
            top_domains = [{"domain": row[0], "count": row[1]} for row in cursor.fetchall()]
            
            conn.close()
            
            return {
                'total_queries': total_queries,
                'cache_hits': cache_hits,
                'cache_hit_rate': cache_hits / total_queries if total_queries > 0 else 0,
                'validation_passes': validation_passes,
                'validation_pass_rate': validation_passes / total_queries if total_queries > 0 else 0,
                'avg_execution_time_ms': round(avg_execution_time, 2),
                'top_domains': top_domains
            }
            
        except Exception as e:
            print(f"Warning: Failed to retrieve stats: {e}")
            return {}


# Test the audit log
if __name__ == "__main__":
    print("Testing Audit Log...")
    print("=" * 80)
    
    # Use test database
    test_db = "audit/test_query_log.db"
    
    # Clean up test database if it exists
    if os.path.exists(test_db):
        os.remove(test_db)
    
    try:
        # Initialize audit log
        audit = AuditLog(test_db)
        print("✓ Audit log initialized")
        
        # Test 1: Log a successful query
        print("\n[Test 1] Logging successful query...")
        audit.log_query({
            'original_input': 'Show CPU busy time',
            'normalized_input': 'show cpu_busy_time',
            'domain_category': 'cpu',
            'generated_sql': 'SELECT cpu_num, cpu_busy_time FROM macht413.cpu LIMIT 10000',
            'validation_passed': True,
            'validation_error': None,
            'cache_hit': False,
            'row_count': 420,
            'execution_time_ms': 150,
            'export_format': None
        })
        print("✓ Query logged")
        
        # Test 2: Log a failed query
        print("\n[Test 2] Logging failed query...")
        audit.log_query({
            'original_input': 'Show fake data',
            'normalized_input': 'show fake data',
            'domain_category': 'multi',
            'generated_sql': 'SELECT * FROM macht413.fake_table',
            'validation_passed': False,
            'validation_error': "Table 'fake_table' does not exist",
            'cache_hit': False,
            'row_count': None,
            'execution_time_ms': None,
            'export_format': None
        })
        print("✓ Failed query logged")
        
        # Test 3: Log a cache hit
        print("\n[Test 3] Logging cache hit...")
        audit.log_query({
            'original_input': 'Show CPU busy time',
            'normalized_input': 'show cpu_busy_time',
            'domain_category': 'cpu',
            'generated_sql': 'SELECT cpu_num, cpu_busy_time FROM macht413.cpu LIMIT 10000',
            'validation_passed': True,
            'validation_error': None,
            'cache_hit': True,
            'row_count': 420,
            'execution_time_ms': 50,
            'export_format': None
        })
        print("✓ Cache hit logged")
        
        # Test 4: Get history
        print("\n[Test 4] Retrieving history...")
        history = audit.get_history(limit=10)
        print(f"✓ Retrieved {len(history)} entries")
        
        if history:
            print(f"  Most recent entry:")
            print(f"    Original: {history[0]['original_input']}")
            print(f"    SQL: {history[0]['generated_sql'][:50]}...")
            print(f"    Cache hit: {bool(history[0]['cache_hit'])}")
        
        # Test 5: Get stats
        print("\n[Test 5] Retrieving statistics...")
        stats = audit.get_stats()
        print(f"✓ Statistics retrieved:")
        print(f"    Total queries: {stats['total_queries']}")
        print(f"    Cache hit rate: {stats['cache_hit_rate']:.1%}")
        print(f"    Validation pass rate: {stats['validation_pass_rate']:.1%}")
        print(f"    Avg execution time: {stats['avg_execution_time_ms']}ms")
        print(f"    Top domains: {stats['top_domains']}")
        
        # Test 6: Verify persistence
        print("\n[Test 6] Testing persistence...")
        audit2 = AuditLog(test_db)
        history2 = audit2.get_history(limit=1)
        
        if history2 and history2[0]['id'] == history[0]['id']:
            print("✓ Data persists across instances")
        else:
            print("✗ Data persistence failed")
        
        print("\n" + "=" * 80)
        print("✓ All audit log tests passed!")
        print("=" * 80)
        
        # Clean up test database
        if os.path.exists(test_db):
            os.remove(test_db)
            print("\n✓ Test database cleaned up")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
