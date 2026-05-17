"""
Schema Loader for QueryCraft
Loads and validates the enriched_schema.yaml file.
"""
import yaml
import os
from typing import Dict, Any

class SchemaLoader:
    """Loads and provides access to the database schema."""
    
    def __init__(self, schema_path: str):
        """
        Initialize the schema loader.
        
        Args:
            schema_path: Path to enriched_schema.yaml
        """
        self.schema_path = schema_path
        self.schema: Dict[str, Any] = {}
        self._load_schema()
        self._validate_schema()
    
    def _load_schema(self):
        """Load the YAML schema file."""
        if not os.path.exists(self.schema_path):
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")
        
        with open(self.schema_path, 'r', encoding='utf-8') as f:
            self.schema = yaml.safe_load(f)
        
        if not self.schema:
            raise ValueError("Schema file is empty")
    
    def _validate_schema(self):
        """Validate that all required tables are present."""
        required_tables = ['cpu', 'disc', 'dfile', 'dopen', 'file', 'ossns', 'proc', 'tmf', 'udef']
        
        missing_tables = []
        for table in required_tables:
            if table not in self.schema:
                missing_tables.append(table)
        
        if missing_tables:
            raise ValueError(f"Missing required tables in schema: {', '.join(missing_tables)}")
        
        # Validate each table has columns
        for table_name, table_def in self.schema.items():
            if isinstance(table_def, dict):
                if 'columns' not in table_def:
                    raise ValueError(f"Table '{table_name}' missing 'columns' definition")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the complete schema."""
        return self.schema
    
    def get_table(self, table_name: str) -> Dict[str, Any]:
        """
        Get schema definition for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Table definition dictionary
            
        Raises:
            KeyError: If table doesn't exist
        """
        if table_name not in self.schema:
            raise KeyError(f"Table '{table_name}' not found in schema")
        return self.schema[table_name]
    
    def get_table_names(self) -> list:
        """Get list of all table names."""
        return [name for name, defn in self.schema.items() if isinstance(defn, dict) and 'columns' in defn]
    
    def get_columns(self, table_name: str) -> Dict[str, Any]:
        """
        Get column definitions for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary of column definitions
        """
        table = self.get_table(table_name)
        return table.get('columns', {})
    
    def get_queryable_columns(self, table_name: str) -> Dict[str, Any]:
        """
        Get only queryable columns for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary of queryable column definitions
        """
        columns = self.get_columns(table_name)
        return {
            col_name: col_def 
            for col_name, col_def in columns.items() 
            if isinstance(col_def, dict) and col_def.get('queryable', True)
        }
    
    def column_exists(self, table_name: str, column_name: str) -> bool:
        """
        Check if a column exists in a table.
        
        Args:
            table_name: Name of the table
            column_name: Name of the column
            
        Returns:
            True if column exists, False otherwise
        """
        try:
            columns = self.get_columns(table_name)
            return column_name in columns
        except KeyError:
            return False
    
    def get_table_description(self, table_name: str) -> str:
        """
        Get the purpose/description of a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Table description string
        """
        table = self.get_table(table_name)
        return table.get('purpose', '')


def load_schema(schema_path: str = None) -> SchemaLoader:
    """
    Convenience function to load schema.
    
    Args:
        schema_path: Path to schema file. If None, uses default from config.
        
    Returns:
        SchemaLoader instance
    """
    if schema_path is None:
        # Import here to avoid circular dependency
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        import config
        schema_path = config.SCHEMA_YAML_PATH
    
    return SchemaLoader(schema_path)


# Test the schema loader
if __name__ == "__main__":
    print("Testing Schema Loader...")
    print("=" * 60)
    
    try:
        loader = load_schema('schema_store/enriched_schema.yaml')
        
        print(f"✓ Schema loaded successfully")
        print(f"✓ Found {len(loader.get_table_names())} tables")
        print(f"\nTables:")
        for table in loader.get_table_names():
            col_count = len(loader.get_columns(table))
            queryable_count = len(loader.get_queryable_columns(table))
            print(f"  - {table:10s}: {col_count:3d} columns ({queryable_count} queryable)")
        
        # Test specific table access
        print(f"\n✓ Testing table access:")
        cpu_cols = loader.get_queryable_columns('cpu')
        print(f"  - CPU table has {len(cpu_cols)} queryable columns")
        
        # Test column existence
        print(f"\n✓ Testing column existence:")
        print(f"  - cpu.cpu_num exists: {loader.column_exists('cpu', 'cpu_num')}")
        print(f"  - cpu.fake_column exists: {loader.column_exists('cpu', 'fake_column')}")
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
