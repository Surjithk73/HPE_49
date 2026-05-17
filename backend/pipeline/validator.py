"""
SQL Validator for QueryCraft
Validates and sanitizes SQL queries for security and correctness.
"""
from typing import Dict, Optional
import sqlglot
from sqlglot import exp
import re


class ValidationResult:
    """Result of SQL validation."""
    
    def __init__(self, valid: bool, sanitized_sql: Optional[str] = None, error: Optional[str] = None):
        self.valid = valid
        self.sanitized_sql = sanitized_sql
        self.error = error
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'valid': self.valid,
            'sanitized_sql': self.sanitized_sql,
            'error': self.error
        }


class SQLValidator:
    """Validates SQL queries for security and correctness."""
    
    # Forbidden keywords that indicate non-SELECT operations
    FORBIDDEN_KEYWORDS = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 
        'CREATE', 'TRUNCATE', 'EXEC', 'EXECUTE'
    ]
    
    # SQL injection patterns
    INJECTION_PATTERNS = [
        r'--',           # SQL comment
        r'/\*',          # Block comment start
        r'xp_',          # Extended stored procedures
        r';\s*\w',       # Semicolon followed by statement
    ]
    
    def __init__(self, schema: Dict):
        """
        Initialize the validator.
        
        Args:
            schema: Schema dictionary from SchemaLoader
        """
        self.schema = schema
    
    def validate(self, sql: str) -> ValidationResult:
        """
        Validate SQL query for security and correctness.
        
        Args:
            sql: SQL query string to validate
            
        Returns:
            ValidationResult with validation status and sanitized SQL or error
        """
        # Strip whitespace
        sql = sql.strip()
        
        if not sql:
            return ValidationResult(False, None, "SQL query is empty")
        
        # Check for SQL injection patterns BEFORE parsing
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, sql):
                return ValidationResult(False, None, f"Potential SQL injection pattern detected")
        
        # Check for forbidden keywords in raw SQL
        sql_upper = sql.upper()
        for keyword in self.FORBIDDEN_KEYWORDS:
            if keyword in sql_upper:
                return ValidationResult(False, None, f"Forbidden keyword detected: {keyword}")
        
        # Check 1: Syntax validation
        try:
            parsed = sqlglot.parse_one(sql, dialect="postgres")
        except sqlglot.errors.ParseError as e:
            return ValidationResult(False, None, f"SQL syntax error: {str(e)}")
        except Exception as e:
            return ValidationResult(False, None, f"Failed to parse SQL: {str(e)}")
        
        # Check 2: Statement type - must be SELECT
        if not isinstance(parsed, exp.Select):
            return ValidationResult(False, None, "Only SELECT statements are permitted")
        
        # Check 3 & 4 already done above before parsing
        
        # Check 5: Schema prefix - auto-prepend macht413 if missing
        sanitized_sql = self._add_schema_prefix(parsed)
        
        # Re-parse sanitized SQL
        try:
            parsed = sqlglot.parse_one(sanitized_sql, dialect="postgres")
        except Exception as e:
            return ValidationResult(False, None, f"Failed to parse sanitized SQL: {str(e)}")
        
        # Check 6: Table existence
        table_check = self._validate_tables(parsed)
        if not table_check['valid']:
            return ValidationResult(False, None, table_check['error'])
        
        # Check 7: Column existence
        column_check = self._validate_columns(parsed)
        if not column_check['valid']:
            return ValidationResult(False, None, column_check['error'])
        
        # All checks passed
        return ValidationResult(True, sanitized_sql, None)
    
    def _add_schema_prefix(self, parsed: exp.Expression) -> str:
        """
        Add macht413 schema prefix to table references if missing.
        
        Args:
            parsed: Parsed SQL expression
            
        Returns:
            SQL string with schema prefixes added
        """
        # Find all table references
        for table in parsed.find_all(exp.Table):
            # If no schema/database specified, add macht413
            if not table.db:
                table.set("db", exp.Identifier(this="macht413"))
        
        return parsed.sql(dialect="postgres")
    
    def _validate_tables(self, parsed: exp.Expression) -> Dict:
        """
        Validate that all referenced tables exist in schema.
        
        Args:
            parsed: Parsed SQL expression
            
        Returns:
            Dict with 'valid' bool and optional 'error' string
        """
        for table in parsed.find_all(exp.Table):
            table_name = table.name
            
            # Remove schema prefix if present for lookup
            if '.' in table_name:
                table_name = table_name.split('.')[-1]
            
            if table_name not in self.schema:
                return {
                    'valid': False,
                    'error': f"Table '{table_name}' does not exist in macht413 schema"
                }
        
        return {'valid': True}
    
    def _collect_derived_aliases(self, parsed: exp.Expression) -> set:
        """
        Collect all column aliases defined in subqueries, CTEs, and SELECT expressions.
        These are valid to reference in outer queries and should not be validated
        against the base table schema.

        Args:
            parsed: Parsed SQL expression

        Returns:
            Set of alias names (lowercase)
        """
        aliases = set()

        # Aliases from SELECT expressions (e.g. AVG(x) AS requests_per_sec)
        for alias in parsed.find_all(exp.Alias):
            aliases.add(alias.alias.lower())

        # CTE names (e.g. WITH cte AS (...) SELECT ... FROM cte)
        for cte in parsed.find_all(exp.CTE):
            aliases.add(cte.alias.lower())

        # Subquery aliases used as table references (e.g. FROM (...) AS sub)
        for subquery in parsed.find_all(exp.Subquery):
            if subquery.alias:
                aliases.add(subquery.alias.lower())

        return aliases

    def _validate_columns(self, parsed: exp.Expression) -> Dict:
        """
        Validate that all referenced columns exist in their tables.
        Skips validation for aliases defined within the query itself
        (subquery columns, CTE columns, SELECT expression aliases).

        Args:
            parsed: Parsed SQL expression

        Returns:
            Dict with 'valid' bool and optional 'error' string
        """
        # Collect all aliases defined anywhere in the query — these are valid
        # to reference in outer SELECTs and should not be checked against schema
        derived_aliases = self._collect_derived_aliases(parsed)

        # Build a map of table aliases to actual table names
        table_map = {}
        for table in parsed.find_all(exp.Table):
            table_name = table.name
            if '.' in table_name:
                table_name = table_name.split('.')[-1]

            alias = table.alias_or_name
            table_map[alias] = table_name

        # If only one real (non-subquery) table, use it as default
        default_table = None
        real_tables = {k: v for k, v in table_map.items() if v in self.schema}
        if len(real_tables) == 1:
            default_table = list(real_tables.values())[0]

        # Check all column references
        for column in parsed.find_all(exp.Column):
            col_name = column.name

            # Skip wildcards
            if col_name == '*':
                continue

            # Skip if this column name is a derived alias (subquery / CTE / expression alias)
            if col_name.lower() in derived_aliases:
                continue

            # Get table for this column
            table_ref = column.table
            if table_ref:
                table_name = table_map.get(table_ref, table_ref)
            elif default_table:
                table_name = default_table
            else:
                # Can't determine table — skip validation
                continue

            # Only validate against known base tables
            if table_name not in self.schema:
                continue

            table_def = self.schema[table_name]
            columns = table_def.get('columns', {})

            # Normalize column name (handle dots and special chars)
            normalized_col = col_name.replace('.', '_').lower()

            # Check if column exists (case-insensitive).
            # Schema keys may use {N} for repeating groups (e.g. c{N}.hits → c0_hits).
            # We match by replacing {N} with a digit pattern.
            import re as _re
            column_exists = False
            for schema_col in columns.keys():
                # Normalize schema key the same way the schema linker does
                schema_normalized = schema_col.replace('.', '_').lower()
                # Replace {N} placeholder with a digit so c{n}_hits matches c0_hits, c1_hits, etc.
                schema_pattern = schema_normalized.replace('{n}', r'\d+')
                if schema_normalized == normalized_col:
                    column_exists = True
                    break
                if '{n}' in schema_normalized and _re.fullmatch(schema_pattern, normalized_col):
                    column_exists = True
                    break

            if not column_exists:
                return {
                    'valid': False,
                    'error': f"Column '{col_name}' does not exist in macht413.{table_name}"
                }

        return {'valid': True}


# Test the validator
if __name__ == "__main__":
    print("Testing SQL Validator...")
    print("=" * 80)
    
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    
    from pipeline.schema_loader import load_schema
    
    try:
        # Load schema
        loader = load_schema('../schema_store/enriched_schema.yaml')
        schema = loader.get_schema()
        
        # Initialize validator
        validator = SQLValidator(schema)
        
        # Test cases
        test_cases = [
            {
                "name": "Valid SELECT with schema prefix",
                "sql": "SELECT cpu_num, AVG(cpu_busy_time) FROM macht413.cpu GROUP BY cpu_num LIMIT 10000;",
                "expected_valid": True
            },
            {
                "name": "Valid SELECT without schema prefix (should be added)",
                "sql": "SELECT cpu_num FROM cpu LIMIT 100;",
                "expected_valid": True
            },
            {
                "name": "DELETE statement (forbidden)",
                "sql": "DELETE FROM macht413.cpu WHERE cpu_num = 0;",
                "expected_valid": False,
                "expected_error": "Forbidden keyword"
            },
            {
                "name": "Fake column",
                "sql": "SELECT fake_column FROM macht413.cpu;",
                "expected_valid": False,
                "expected_error": "Column 'fake_column' does not exist"
            },
            {
                "name": "SQL injection attempt",
                "sql": "SELECT * FROM macht413.cpu; DROP TABLE macht413.cpu;",
                "expected_valid": False,
                "expected_error": "injection"
            },
            {
                "name": "Non-existent table",
                "sql": "SELECT * FROM macht413.fake_table;",
                "expected_valid": False,
                "expected_error": "does not exist"
            },
            {
                "name": "Valid JOIN query",
                "sql": "SELECT c.cpu_num, p.process_name FROM macht413.cpu c JOIN macht413.proc p ON c.cpu_num = p.cpu_num LIMIT 100;",
                "expected_valid": True
            },
        ]
        
        passed = 0
        failed = 0
        
        for i, test in enumerate(test_cases, 1):
            print(f"\n[Test {i}] {test['name']}")
            print("-" * 80)
            print(f"SQL: {test['sql'][:100]}...")
            
            result = validator.validate(test['sql'])
            
            print(f"Valid: {result.valid}")
            if result.error:
                print(f"Error: {result.error}")
            if result.sanitized_sql and result.sanitized_sql != test['sql']:
                print(f"Sanitized: {result.sanitized_sql[:100]}...")
            
            # Check expectations
            if result.valid == test['expected_valid']:
                if not test['expected_valid'] and 'expected_error' in test:
                    # Check if error message contains expected text
                    if test['expected_error'].lower() in result.error.lower():
                        print("✓ PASSED")
                        passed += 1
                    else:
                        print(f"✗ FAILED: Expected error containing '{test['expected_error']}', got '{result.error}'")
                        failed += 1
                else:
                    print("✓ PASSED")
                    passed += 1
            else:
                print(f"✗ FAILED: Expected valid={test['expected_valid']}, got valid={result.valid}")
                failed += 1
        
        print("\n" + "=" * 80)
        print(f"Test Results: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("✓ All SQL Validator tests passed!")
        else:
            print("✗ Some tests failed")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
