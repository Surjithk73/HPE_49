"""
Complete database setup - recreate tables and load CSV data
"""
import psycopg2
import os

POSTGRES_PASSWORD = "admin"  # Replace with your postgres superuser password

def main():
    print("=" * 60)
    print("QueryCraft - Complete Database Setup")
    print("=" * 60)
    
    try:
        # Connect
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='postgres',
            password=POSTGRES_PASSWORD,
            dbname='querycraft_db'
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        print("\n✓ Connected to database\n")
        
        # Step 1: Drop existing tables
        print("[1/3] Dropping existing tables...")
        tables = ['cpu', 'disc', 'dfile', 'dopen', 'file', 'ossns', 'proc', 'tmf', 'udef']
        for table in tables:
            cur.execute(f"DROP TABLE IF EXISTS macht413.{table} CASCADE")
            print(f"  ✓ Dropped {table}")
        
        # Step 2: Create tables from SQL file
        print("\n[2/3] Creating tables...")
        with open('create_tables.sql', 'r', encoding='utf-8') as f:
            sql = f.read()
            # Execute each CREATE TABLE statement
            for statement in sql.split(';'):
                if statement.strip() and 'CREATE TABLE' in statement:
                    cur.execute(statement + ';')
        print("  ✓ All tables created")
        
        # Step 3: Load CSV data
        print("\n[3/3] Loading CSV data...")
        csv_mapping = {
            'cpucsv': 'cpu',
            'disccsv': 'disc',
            'dfilecsv': 'dfile',
            'dopencsv': 'dopen',
            'filecsv': 'file',
            'ossnscsv': 'ossns',
            'proccsv': 'proc',
            'tmfcsv': 'tmf',
            'udefcsv': 'udef',
        }
        
        data_dir = os.path.abspath('../../measurefiles')
        total_rows = 0
        
        for csv_file, table_name in csv_mapping.items():
            csv_path = os.path.join(data_dir, csv_file)
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                cur.copy_expert(
                    f"COPY macht413.{table_name} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '', DELIMITER ',')",
                    f
                )
            
            cur.execute(f"SELECT COUNT(*) FROM macht413.{table_name}")
            count = cur.fetchone()[0]
            total_rows += count
            print(f"  ✓ {table_name:10s}: {count:,} rows")
        
        print(f"\n  Total rows loaded: {total_rows:,}")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✓ Setup complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
