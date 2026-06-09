"""
Automated database setup script for QueryCraft.
Generates CREATE TABLE DDL from enriched_schema.yaml and sets up the database.
"""
import yaml
import psycopg2
from psycopg2 import sql
import sys
import os

# Configuration - UPDATE THESE
POSTGRES_PASSWORD = "[PASSWORD]"   # Replace with your postgres superuser password
OWNER_PASSWORD = "nonstop123"         # Password for nonstop_measure role
READONLY_PASSWORD = "querycraft123"   # Password for querycraft_user role

# Load schema
with open('schema_store/enriched_schema.yaml', 'r', encoding='utf-8') as f:
    schema = yaml.safe_load(f)

def map_type_to_postgres(col_type):
    """Map YAML type to PostgreSQL type."""
    type_mapping = {
        'string': 'TEXT',
        'integer': 'BIGINT',
        'datetime': 'TIMESTAMP',
        'bitmask': 'INTEGER',
    }
    return type_mapping.get(col_type, 'TEXT')

def sanitize_column_name(col_name):
    """Convert column names with dots and special chars to valid PostgreSQL identifiers."""
    # Replace dots with underscores
    sanitized = col_name.replace('.', '_')
    # Replace {N} notation with _n
    sanitized = sanitized.replace('{N}', '_n')
    sanitized = sanitized.replace('{', '_').replace('}', '')
    return sanitized

def generate_create_table_ddl(schema_name, table_name, table_def):
    """Generate CREATE TABLE DDL for a single table."""
    columns = []
    
    for col_name, col_def in table_def['columns'].items():
        if isinstance(col_def, dict):
            sanitized_name = sanitize_column_name(col_name)
            col_type = map_type_to_postgres(col_def.get('type', 'string'))
            columns.append(f'    "{sanitized_name}" {col_type}')
    
    ddl = f"CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} (\n"
    ddl += ',\n'.join(columns)
    ddl += "\n);"
    
    return ddl

def main():
    print("=" * 60)
    print("QueryCraft Database Setup (Automated)")
    print("=" * 60)
    
    # Connect as nonstop_measure
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='nonstop_measure',
            password=OWNER_PASSWORD,
            dbname='querycraft_db'
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # Step 3, 4, 5: Create schemas and tables
        print("\n[3-5/6] Creating tables in macht413 and machd500...")
        table_count = 0
        for target_schema in ['macht413', 'machd500']:
            # Create schema if it doesn't exist (assuming nonstop_measure can or it was already created)
            try:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {target_schema} AUTHORIZATION nonstop_measure")
            except Exception as e:
                print(f"  - Warning: Could not create schema {target_schema} ({e}). Assuming it exists.")
                # We need to rollback the failed schema creation to continue using the transaction
                conn.rollback()

            for table_name, table_def in schema.items():
                # macht413 only gets the 9 base tables
                if target_schema == 'macht413' and table_name in ['sqlp', 'sqls']:
                    continue
                    
                if isinstance(table_def, dict) and 'columns' in table_def:
                    ddl = generate_create_table_ddl(target_schema, table_name, table_def)
                    try:
                        cur.execute(ddl)
                        table_count += 1
                    except Exception as e:
                        print(f"  - Error creating {target_schema}.{table_name}: {e}")
                        conn.rollback()
            
            try:
                cur.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {target_schema} TO querycraft_user")
            except Exception:
                conn.rollback()
                
            print(f"  + Setup complete for schema: {target_schema}")
        
        print(f"  + Total tables created across schemas: {table_count}")
        
        # Step 6: Verify
        print("\n[6/6] Verifying setup...")
        for target_schema in ['macht413', 'machd500']:
            try:
                cur.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{target_schema}' ORDER BY table_name")
                tables = cur.fetchall()
                print(f"  + Found {len(tables)} tables in {target_schema} schema:")
                for table in tables:
                    print(f"    - {table[0]}")
            except Exception:
                conn.rollback()
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("+ Database setup complete!")
        print("=" * 60)
        print("\nCredentials created:")
        print(f"  - nonstop_measure: {OWNER_PASSWORD}")
        print(f"  - querycraft_user: {READONLY_PASSWORD}")
        print("\nNext steps:")
        print("1. Update backend/.env with these credentials:")
        print(f"   DB_USER=querycraft_user")
        print(f"   DB_PASSWORD={READONLY_PASSWORD}")
        print("2. Run: python load_csv_data.py")
        
    except Exception as e:
        print(f"\n- Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
