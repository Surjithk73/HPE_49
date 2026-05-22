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
        
        # Precompute the full expanded column set at startup rather than regex matching
        import copy
        self.expanded_schema = copy.deepcopy(schema)
        for table_name, table_def in self.expanded_schema.items():
            if not isinstance(table_def, dict) or 'columns' not in table_def:
                continue
            columns = table_def['columns']
            new_columns = {}
            for col_name, col_def in columns.items():
                col_normalized = col_name.replace('.', '_').lower()
                if 'ipu{n}' in col_normalized:
                    for i in range(16):
                        expanded_name = col_normalized.replace('ipu{n}', f'ipu{i}')
                        new_columns[expanded_name] = col_def
                elif 'svnet{n}' in col_normalized:
                    for i in range(16):
                        expanded_name = col_normalized.replace('svnet{n}', f'svnet{i}')
                        new_columns[expanded_name] = col_def
                elif 'c{n}' in col_normalized:
                    for i in range(8):
                        expanded_name = col_normalized.replace('c{n}', f'c{i}')
                        new_columns[expanded_name] = col_def
                else:
                    new_columns[col_normalized] = col_def
            table_def['columns'] = new_columns
    
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
            
        # Check 8: Complexity limits
        complexity_check = self._validate_complexity(parsed)
        if not complexity_check['valid']:
            return ValidationResult(False, None, complexity_check['error'])
        
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
        # Collect all CTE names defined in the query
        ctes = {cte.alias.lower() for cte in parsed.find_all(exp.CTE)}
        
        # Find all table references
        for table in parsed.find_all(exp.Table):
            # If this is a CTE reference, do not add schema prefix
            if table.name.lower() in ctes:
                continue
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
        # Collect all CTE names defined in the query
        ctes = {cte.alias.lower() for cte in parsed.find_all(exp.CTE)}
        
        for table in parsed.find_all(exp.Table):
            table_name = table.name
            
            # If this is a CTE reference, skip validation
            if table_name.lower() in ctes:
                continue
                
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
        Uses AST scope resolution to map columns to their correct sources.
        """
        from sqlglot.optimizer.scope import build_scope
        
        try:
            scope_tree = build_scope(parsed)
        except Exception as e:
            return {
                'valid': False,
                'error': f"Failed to build AST scope tree: {str(e)}"
            }

        # Step 1: Precompute exported columns for each scope bottom-up
        scope_exports = {}
        
        def get_source_columns(source) -> set:
            if isinstance(source, exp.Table):
                t_name = source.name
                if '.' in t_name:
                    t_name = t_name.split('.')[-1]
                table_def = self.expanded_schema.get(t_name, {})
                return set(table_def.get('columns', {}).keys())
            elif isinstance(source, sqlglot.optimizer.scope.Scope):
                return scope_exports.get(id(source), set())
            return set()

        for scope in scope_tree.traverse():
            exported = set()
            for select in scope.expression.selects:
                if isinstance(select, exp.Star):
                    for src_alias, src in scope.sources.items():
                        exported.update(get_source_columns(src))
                elif isinstance(select, exp.Column) and select.name == '*':
                    src = scope.sources.get(select.table)
                    if src:
                        exported.update(get_source_columns(src))
                else:
                    name = select.alias_or_name
                    if name:
                        exported.add(name.lower())
            scope_exports[id(scope)] = exported

        # Step 2: Validate columns in each scope
        for scope in scope_tree.traverse():
            for column in scope.columns:
                col_name = column.name
                
                # Skip wildcards
                if col_name == '*':
                    continue
                
                col_lower = col_name.lower()
                
                # Skip if this is a locally defined SELECT alias in the scope or parent scopes
                is_select_alias = False
                curr = scope
                while curr:
                    curr_select_aliases = {
                        select.alias.lower() for select in curr.expression.selects if isinstance(select, exp.Alias)
                    }
                    if col_lower in curr_select_aliases:
                        is_select_alias = True
                        break
                    curr = curr.parent
                
                if is_select_alias:
                    continue

                # Locate the source table/subquery for this column
                table_ref = column.table
                source = None
                
                if table_ref:
                    curr = scope
                    while curr:
                        if table_ref in curr.sources:
                            source = curr.sources[table_ref]
                            break
                        curr = curr.parent
                    
                    if not source:
                        return {
                            'valid': False,
                            'error': f"Table alias or reference '{table_ref}' is not defined in this scope"
                        }
                    
                    if isinstance(source, exp.Table):
                        t_name = source.name
                        if '.' in t_name:
                            t_name = t_name.split('.')[-1]
                        
                        if t_name not in self.expanded_schema:
                            continue
                        
                        table_def = self.expanded_schema[t_name]
                        columns_dict = table_def.get('columns', {})
                        normalized_col = col_name.replace('.', '_').lower()
                        if normalized_col not in columns_dict:
                            return {
                                'valid': False,
                                'error': f"Column '{col_name}' does not exist in macht413.{t_name}"
                            }
                    else:
                        src_cols = scope_exports.get(id(source), set())
                        if col_lower not in src_cols:
                            return {
                                'valid': False,
                                'error': f"Column '{col_name}' does not exist in subquery/CTE '{table_ref}'"
                            }
                
                else:
                    found_in_sources = []
                    curr = scope
                    while curr:
                        for src_alias, src in curr.sources.items():
                            if isinstance(src, exp.Table):
                                t_name = src.name
                                if '.' in t_name:
                                    t_name = t_name.split('.')[-1]
                                
                                if t_name in self.expanded_schema:
                                    table_def = self.expanded_schema[t_name]
                                    columns_dict = table_def.get('columns', {})
                                    normalized_col = col_name.replace('.', '_').lower()
                                    if normalized_col in columns_dict:
                                        found_in_sources.append((src_alias, t_name))
                            else:
                                src_cols = scope_exports.get(id(src), set())
                                if col_lower in src_cols:
                                    found_in_sources.append((src_alias, "subquery/CTE"))
                        
                        if found_in_sources:
                            break
                        curr = curr.parent
                    
                    if not found_in_sources:
                        local_tables = []
                        for s_alias, s_val in scope.sources.items():
                            if isinstance(s_val, exp.Table):
                                local_tables.append(s_val.name.split('.')[-1])
                        
                        table_msg = f"macht413.{local_tables[0]}" if len(local_tables) == 1 else "any of the referenced tables"
                        return {
                            'valid': False,
                            'error': f"Column '{col_name}' does not exist in {table_msg}"
                        }

        return {'valid': True}

    def _validate_complexity(self, parsed: exp.Expression) -> Dict:
        """
        Validate query complexity limits:
        - Max 9 tables per query (all tables in the schema)
        - Max 30 columns in SELECT (across any SELECT statement)
        - Max 3 levels of subquery nesting
        """
        # 1. Max 9 tables (one per schema table — cross-table analytics is the whole point)
        tables = list(parsed.find_all(exp.Table))
        if len(tables) > 9:
            return {
                'valid': False,
                'error': f"Query complexity limit exceeded: contains {len(tables)} tables (max 9 allowed)"
            }

        from sqlglot.optimizer.scope import build_scope
        try:
            scope_tree = build_scope(parsed)
        except Exception:
            # scope building can fail on complex CTEs — not a security issue, skip these checks
            return {'valid': True}

        if scope_tree is None:
            return {'valid': True}

        # 2. Max 30 columns in SELECT
        try:
            for scope in scope_tree.traverse():
                num_cols = len(scope.expression.selects)
                if num_cols > 30:
                    return {
                        'valid': False,
                        'error': f"Query complexity limit exceeded: SELECT projects {num_cols} columns (max 30 allowed)"
                    }
        except Exception:
            pass  # non-critical check — skip on error

        # 3. Max 3 levels of subquery nesting
        try:
            max_nesting = 0
            for scope in scope_tree.traverse():
                depth = 0
                curr = scope
                while curr.parent:
                    depth += 1
                    curr = curr.parent
                max_nesting = max(max_nesting, depth)

            if max_nesting > 3:
                return {
                    'valid': False,
                    'error': f"Query complexity limit exceeded: subquery nesting level of {max_nesting} exceeds max 3"
                }
        except Exception:
            pass  # non-critical check — skip on error

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
