"""
Query Executor for QueryCraft
Executes validated SQL against PostgreSQL using read-only role.
"""
import time
from typing import Dict, List, Optional
import psycopg2
from psycopg2 import sql
import sys
import os

# Add parent directory to path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, MAX_ROWS, QUERY_TIMEOUT_SECONDS
except (ValueError, ImportError):
    # Fallback for testing
    DB_HOST = "localhost"
    DB_PORT = "5432"
    DB_NAME = "querycraft_db"
    DB_USER = "querycraft_user"
    DB_PASSWORD = "your_readonly_password"
    MAX_ROWS = 10000
    QUERY_TIMEOUT_SECONDS = 30


class ExecutionError(Exception):
    """Custom exception for execution errors."""
    pass


class ExecutionResult:
    """Result of SQL execution."""
    
    def __init__(self, columns: List[str], rows: List[Dict], row_count: int, execution_time_ms: int):
        self.columns = columns
        self.rows = rows
        self.row_count = row_count
        self.execution_time_ms = execution_time_ms
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'columns': self.columns,
            'rows': self.rows,
            'row_count': self.row_count,
            'execution_time_ms': self.execution_time_ms
        }


class QueryExecutor:
    """Executes SQL queries against PostgreSQL."""
    
    def __init__(self, host: str = None, port: str = None, database: str = None,
                 user: str = None, password: str = None, timeout: int = None):
        """
        Initialize the executor.
        
        Args:
            host: Database host (defaults to config)
            port: Database port (defaults to config)
            database: Database name (defaults to config)
            user: Database user (defaults to config)
            password: Database password (defaults to config)
            timeout: Query timeout in seconds (defaults to config)
        """
        self.host = host or DB_HOST
        self.port = port or DB_PORT
        self.database = database or DB_NAME
        self.user = user or DB_USER
        self.password = password or DB_PASSWORD
        self.timeout = timeout or QUERY_TIMEOUT_SECONDS
        
        # Enforce read-only user
        if self.user not in ['querycraft_user']:
            raise ExecutionError(f"Only read-only user 'querycraft_user' is permitted, got '{self.user}'")
    
    def execute(self, sql: str) -> ExecutionResult:
        """
        Execute SQL query and return results.
        
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
        cursor = None
        
        try:
            # Start timing
            start_time = time.time()
            
            # Connect with timeout
            connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                options=f"-c statement_timeout={self.timeout * 1000}"  # Convert to milliseconds
            )
            
            cursor = connection.cursor()
            
            # Execute query
            cursor.execute(sql)
            
            # Fetch results
            rows_data = cursor.fetchall()
            
            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Convert to list of dicts
            rows = []
            for row in rows_data:
                row_dict = {}
                for i, col_name in enumerate(columns):
                    value = row[i]
                    # Convert to JSON-serializable types
                    if hasattr(value, 'isoformat'):  # datetime objects
                        value = value.isoformat()
                    row_dict[col_name] = value
                rows.append(row_dict)
            
            # Calculate execution time
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            return ExecutionResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=execution_time_ms
            )
            
        except psycopg2.errors.QueryCanceled:
            raise ExecutionError(f"Query exceeded {self.timeout} second timeout")
        
        except psycopg2.Error as e:
            raise ExecutionError(f"Database error: {str(e)}")
        
        except Exception as e:
            raise ExecutionError(f"Execution failed: {str(e)}")
        
        finally:
            # Clean up
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    def _ensure_limit(self, sql: str) -> str:
        """
        Ensure SQL has a LIMIT clause.
        
        Args:
            sql: SQL query
            
        Returns:
            SQL with LIMIT clause
        """
        sql_upper = sql.upper()
        
        # Check if LIMIT already exists
        if 'LIMIT' in sql_upper:
            return sql
        
        # Append LIMIT
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
    
    # Check for timestamp columns → line chart
    for col in columns_lower:
        if 'timestamp' in col:
            return "line"
    
    # Check for categorical columns → bar chart
    categorical_columns = ['cpu_num', 'system_name', 'device_name', 'process_name', 'file_name']
    for col in columns_lower:
        if any(cat in col for cat in categorical_columns):
            return "bar"
    
    # Default to table
    return "table"


# Test the executor
if __name__ == "__main__":
    print("Testing Query Executor...")
    print("=" * 80)
    
    try:
        # Initialize executor
        executor = QueryExecutor()
        print(f"✓ Executor initialized")
        print(f"  Host: {executor.host}")
        print(f"  Database: {executor.database}")
        print(f"  User: {executor.user}")
        print(f"  Timeout: {executor.timeout}s")
        
        # Test queries
        test_queries = [
            {
                "name": "Simple COUNT",
                "sql": "SELECT COUNT(*) FROM macht413.cpu"
            },
            {
                "name": "Aggregation with GROUP BY",
                "sql": "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 5"
            },
            {
                "name": "Query without LIMIT (should be added)",
                "sql": "SELECT system_name FROM macht413.cpu"
            },
        ]
        
        for i, test in enumerate(test_queries, 1):
            print(f"\n[Test {i}] {test['name']}")
            print("-" * 80)
            print(f"SQL: {test['sql']}")
            
            try:
                result = executor.execute(test['sql'])
                
                print(f"✓ Executed successfully")
                print(f"  Columns: {result.columns}")
                print(f"  Row count: {result.row_count}")
                print(f"  Execution time: {result.execution_time_ms}ms")
                
                # Show first few rows
                if result.rows:
                    print(f"  First row: {result.rows[0]}")
                
                # Detect chart type
                chart_type = detect_chart_type(result.columns)
                print(f"  Chart type: {chart_type}")
                
            except ExecutionError as e:
                print(f"✗ Execution failed: {e}")
        
        # Test chart type detection
        print("\n" + "=" * 80)
        print("Testing Chart Type Detection")
        print("=" * 80)
        
        chart_tests = [
            (["cpu_num", "avg_busy_time"], "bar"),
            (["from_timestamp", "cpu_busy_time"], "line"),
            (["count"], "table"),
            (["system_name", "total"], "bar"),
        ]
        
        for columns, expected in chart_tests:
            result = detect_chart_type(columns)
            status = "✓" if result == expected else "✗"
            print(f"{status} {columns} → {result} (expected: {expected})")
        
        print("\n" + "=" * 80)
        print("✓ Query Executor tests complete!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
