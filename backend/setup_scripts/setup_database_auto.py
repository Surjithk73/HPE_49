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
POSTGRES_PASSWORD = "your_postgres_password"   # Replace with your postgres superuser password
OWNER_PASSWORD = "your_owner_password"         # Password for nonstop_measure role
READONLY_PASSWORD = "your_readonly_password"   # Password for querycraft_user role

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

def generate_create_table_ddl(table_name, table_def):
    """Generate CREATE TABLE DDL for a single table."""
    columns = []
    
    for col_name, col_def in table_def['columns'].items():
        if isinstance(col_def, dict):
            sanitized_name = sanitize_column_name(col_name)
            col_type = map_type_to_postgres(col_def.get('type', 'string'))
            columns.append(f'    "{sanitized_name}" {col_type}')
    
    ddl = f"CREATE TABLE IF NOT EXISTS macht413.{table_name} (\n"
    ddl += ',\n'.join(columns)
    ddl += "\n);"
    
    return ddl

def main():
    print("=" * 60)
    print("QueryCraft Database Setup (Automated)")
    print("=" * 60)
    
    # Connect as postgres superuser
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='postgres',
            password=POSTGRES_PASSWORD,
            dbname='postgres'
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # Step 1: Create database
        print("\n[1/6] Creating database 'querycraft_db'...")
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'querycraft_db'")
        if cur.fetchone():
            print("  ✓ Database already exists")
        else:
            cur.execute("CREATE DATABASE querycraft_db")
            print("  ✓ Database created")
        
        # Step 2: Create owner role
        print("\n[2/6] Creating role 'nonstop_measure'...")
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'nonstop_measure'")
        if cur.fetchone():
            print("  ✓ Role already exists")
        else:
            cur.execute(sql.SQL("CREATE ROLE nonstop_measure WITH LOGIN PASSWORD {}").format(
                sql.Literal(OWNER_PASSWORD)
            ))
            print("  ✓ Role created")
        
        cur.close()
        conn.close()
        
        # Connect to querycraft_db
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='postgres',
            password=POSTGRES_PASSWORD,
            dbname='querycraft_db'
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # Step 3: Create schema
        print("\n[3/6] Creating schema 'macht413'...")
        cur.execute("CREATE SCHEMA IF NOT EXISTS macht413 AUTHORIZATION nonstop_measure")
        print("  ✓ Schema created")
        
        # Step 4: Create tables
        print("\n[4/6] Creating 9 tables...")
        table_count = 0
        for table_name, table_def in schema.items():
            if isinstance(table_def, dict) and 'columns' in table_def:
                ddl = generate_create_table_ddl(table_name, table_def)
                cur.execute(ddl)
                table_count += 1
                print(f"  ✓ Created table: macht413.{table_name}")
        
        print(f"  ✓ Total tables created: {table_count}")
        
        # Step 5: Create read-only role
        print("\n[5/6] Creating read-only role 'querycraft_user'...")
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'querycraft_user'")
        if cur.fetchone():
            print("  ✓ Role already exists")
        else:
            cur.execute(sql.SQL("CREATE ROLE querycraft_user WITH LOGIN PASSWORD {}").format(
                sql.Literal(READONLY_PASSWORD)
            ))
            print("  ✓ Role created")
        
        # Grant permissions
        cur.execute("GRANT CONNECT ON DATABASE querycraft_db TO querycraft_user")
        cur.execute("GRANT USAGE ON SCHEMA macht413 TO querycraft_user")
        cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA macht413 TO querycraft_user")
        cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA macht413 GRANT SELECT ON TABLES TO querycraft_user")
        
        # Set timeouts
        cur.execute("ALTER ROLE querycraft_user SET statement_timeout = '30s'")
        cur.execute("ALTER ROLE querycraft_user SET idle_in_transaction_session_timeout = '60s'")
        print("  ✓ Permissions granted and timeouts set")
        
        # Step 6: Verify
        print("\n[6/6] Verifying setup...")
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'macht413' ORDER BY table_name")
        tables = cur.fetchall()
        print(f"  ✓ Found {len(tables)} tables in macht413 schema:")
        for table in tables:
            print(f"    - {table[0]}")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✓ Database setup complete!")
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
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
