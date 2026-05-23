"""
Query Executor for QueryCraft
Executes validated SQL against PostgreSQL using read-only role.

Improvements:
- ThreadedConnectionPool replaces per-query connect/close.
  Connections are borrowed from the pool, used, then returned — no TCP
  handshake cost on every query.  Pool size: min=2, max=10.
"""
import time
import re
from typing import Dict, List, Optional
import psycopg2
from psycopg2 import pool as psycopg2_pool
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, MAX_ROWS, QUERY_TIMEOUT_SECONDS, ALLOWED_DB_USERS
except (ValueError, ImportError):
    # Fallback for standalone testing
    DB_HOST              = "localhost"
    DB_PORT              = "5432"
    DB_NAME              = "querycraft_db"
    DB_USER              = "querycraft_user"
    DB_PASSWORD          = "your_readonly_password"
    MAX_ROWS             = 10000
    QUERY_TIMEOUT_SECONDS = 30
    ALLOWED_DB_USERS     = ["querycraft_user"]


# Pool size constants — tune here if needed
_POOL_MIN_CONN = 2
_POOL_MAX_CONN = 10


class ExecutionError(Exception):
    """Custom exception for execution errors."""
    pass


class ExecutionResult:
    """Result of SQL execution."""

    def __init__(self, columns: List[str], rows: List[Dict], row_count: int, execution_time_ms: int):
        self.columns          = columns
        self.rows             = rows
        self.row_count        = row_count
        self.execution_time_ms = execution_time_ms

    def to_dict(self) -> Dict:
        return {
            'columns':           self.columns,
            'rows':              self.rows,
            'row_count':         self.row_count,
            'execution_time_ms': self.execution_time_ms,
        }


class QueryExecutor:
    """
    Executes SQL queries against PostgreSQL using a connection pool.

    A ThreadedConnectionPool is created once at __init__ time.  Each call
    to execute() borrows a connection, runs the query, then returns the
    connection to the pool — no TCP handshake per query.
    """

    def __init__(
        self,
        host:     str = None,
        port:     str = None,
        database: str = None,
        user:     str = None,
        password: str = None,
        timeout:  int = None,
        min_conn: int = _POOL_MIN_CONN,
        max_conn: int = _POOL_MAX_CONN,
        allowed_users: List[str] = None,
        max_query_cost: float = None,
    ):
        """
        Initialize the executor and create the connection pool.

        Args:
            host:     Database host (defaults to config)
            port:     Database port (defaults to config)
            database: Database name (defaults to config)
            user:     Database user (defaults to config)
            password: Database password (defaults to config)
            timeout:  Query timeout in seconds (defaults to config)
            min_conn: Minimum pool connections (default 2)
            max_conn: Maximum pool connections (default 10)
            allowed_users: List of allowed database users (defaults to config)
        """
        self.host     = host     or DB_HOST
        self.port     = port     or DB_PORT
        self.database = database or DB_NAME
        self.user     = user     or DB_USER
        self.password = password or DB_PASSWORD
        self.timeout  = timeout  or QUERY_TIMEOUT_SECONDS
        self.allowed_users = allowed_users or ALLOWED_DB_USERS
        self.max_query_cost = max_query_cost or float(os.getenv("MAX_QUERY_COST", "25000.0"))

        # Enforce read-only user checks dynamically
        if self.user not in self.allowed_users:
            raise ExecutionError(
                f"Only read-only users {self.allowed_users} are permitted, got '{self.user}'"
            )


        # Build the DSN options string — sets statement_timeout for every
        # connection in the pool so it is enforced even if the caller forgets.
        self._options = f"-c statement_timeout={self.timeout * 1000}"

        # Create the threaded connection pool
        try:
            self._pool = psycopg2_pool.ThreadedConnectionPool(
                minconn=min_conn,
                maxconn=max_conn,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                options=self._options,
            )
            print(
                f"[Executor] Connection pool ready "
                f"(min={min_conn}, max={max_conn}, db={self.database})"
            )
        except psycopg2.Error as e:
            raise ExecutionError(f"Failed to create connection pool: {e}")

    def _estimate_cost(self, cursor, sql: str) -> float:
        """Run EXPLAIN and extract the total start-up + run cost of the query."""
        try:
            cursor.execute(f"EXPLAIN {sql}")
            explain_rows = cursor.fetchall()
            if not explain_rows:
                return 0.0
            first_line = explain_rows[0][0]
            match = re.search(r'cost=\d+(?:\.\d+)?\.\.(\d+(?:\.\d+)?)', first_line)
            if match:
                return float(match.group(1))
            return 0.0
        except Exception as e:
            print(f"[Executor] Warning: Cost estimation failed: {e}")
            return 0.0

    def close(self) -> None:
        """Close all connections in the pool.  Call on application shutdown."""
        if self._pool:
            self._pool.closeall()
            print("[Executor] Connection pool closed.")

    def execute(self, sql: str) -> ExecutionResult:
        """
        Execute SQL query and return results.

        Borrows a connection from the pool, executes the query, returns the
        connection.  The pool handles thread-safety internally.

        Args:
            sql: Validated SQL query

        Returns:
            ExecutionResult with columns, rows, and metadata

        Raises:
            ExecutionError: If execution fails
        """
        # Enforce LIMIT clause
        sql = self._ensure_limit(sql)

        connection = None
        cursor     = None

        try:
            start_time = time.time()

            # Borrow a connection from the pool
            connection = self._pool.getconn()

            # Ensure autocommit so read-only queries don't hold transactions open
            connection.autocommit = True

            cursor = connection.cursor()

            # Cost Estimation Check
            if self.max_query_cost is not None:
                cost = self._estimate_cost(cursor, sql)
                if cost > self.max_query_cost:
                    raise ExecutionError(
                        f"Query cost estimation ({cost}) exceeds the maximum query cost limit ({self.max_query_cost}). Query rejected."
                    )

            cursor.execute(sql)


            rows_data = cursor.fetchall()
            columns   = [desc[0] for desc in cursor.description] if cursor.description else []

            # Convert to list of JSON-serialisable dicts
            rows = []
            for row in rows_data:
                row_dict = {}
                for i, col_name in enumerate(columns):
                    value = row[i]
                    if hasattr(value, 'isoformat'):        # datetime → ISO string
                        value = value.isoformat()
                    elif hasattr(value, '__class__') and value.__class__.__name__ == 'Decimal':
                        # SUM/AVG on BIGINT returns Decimal — convert to int or float
                        value = int(value) if value == int(value) else float(value)
                    row_dict[col_name] = value
                rows.append(row_dict)

            execution_time_ms = max(1, int((time.time() - start_time) * 1000))

            return ExecutionResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=execution_time_ms,
            )

        except psycopg2.errors.QueryCanceled:
            raise ExecutionError(f"Query exceeded {self.timeout} second timeout")

        except psycopg2.Error as e:
            raise ExecutionError(f"Database error: {str(e)}")

        except Exception as e:
            raise ExecutionError(f"Execution failed: {str(e)}")

        finally:
            # Always return the connection to the pool, even on error.
            # putconn(close=True) discards a broken connection; the pool
            # will open a fresh one next time it is needed.
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if connection:
                try:
                    self._pool.putconn(connection)
                except Exception:
                    pass

    def _ensure_limit(self, sql: str) -> str:
        """Append LIMIT {MAX_ROWS} if the query has no LIMIT clause."""
        if 'LIMIT' in sql.upper():
            return sql
        return f"{sql.rstrip(';')} LIMIT {MAX_ROWS}"


def detect_chart_type(columns: List[str]) -> str:
    """
    Detect appropriate chart type based on result columns.

    Args:
        columns: List of column names

    Returns:
        Chart type: "line", "bar", or "table"
    """
    columns_lower = [col.lower() for col in columns]

    # Timestamp columns → line chart
    for col in columns_lower:
        if 'timestamp' in col:
            return "line"

    # Categorical columns → bar chart
    categorical = ['cpu_num', 'system_name', 'device_name', 'process_name', 'file_name']
    for col in columns_lower:
        if any(cat in col for cat in categorical):
            return "bar"

    return "table"


# ── Self-test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Query Executor (connection pool)...")
    print("=" * 80)

    try:
        executor = QueryExecutor()
        print(f"✓ Executor initialized with pool")
        print(f"  Host:     {executor.host}")
        print(f"  Database: {executor.database}")
        print(f"  User:     {executor.user}")
        print(f"  Timeout:  {executor.timeout}s")

        test_queries = [
            ("Simple COUNT",                    "SELECT COUNT(*) FROM macht413.cpu"),
            ("Aggregation with GROUP BY",        "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 5"),
            ("Query without LIMIT (auto-added)", "SELECT system_name FROM macht413.cpu"),
        ]

        for name, sql in test_queries:
            print(f"\n[Test] {name}")
            print(f"  SQL: {sql}")
            try:
                result = executor.execute(sql)
                print(f"  ✓ Rows: {result.row_count}  |  Time: {result.execution_time_ms}ms")
                print(f"  Columns: {result.columns}")
                if result.rows:
                    print(f"  First row: {result.rows[0]}")
                print(f"  Chart type: {detect_chart_type(result.columns)}")
            except ExecutionError as e:
                print(f"  ✗ {e}")

        # Chart type detection
        print("\n── Chart type detection ──────────────────────────────────────")
        chart_tests = [
            (["cpu_num", "avg_busy_time"],       "bar"),
            (["from_timestamp", "cpu_busy_time"], "line"),
            (["count"],                           "table"),
            (["system_name", "total"],            "bar"),
        ]
        for cols, expected in chart_tests:
            got    = detect_chart_type(cols)
            status = "✓" if got == expected else "✗"
            print(f"  {status} {cols} → {got} (expected: {expected})")

        executor.close()
        print("\n✓ Query Executor tests complete!")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
