"""
CSV data loader for QueryCraft (Automated).
Loads all 9 CSV files into their respective tables.
"""
import psycopg2
import os
import sys

# Configuration
POSTGRES_PASSWORD = "admin"  # Replace with your postgres superuser password

# CSV file to table mapping
CSV_MAPPING = {
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

def main():
    print("=" * 60)
    print("QueryCraft CSV Data Loader")
    print("=" * 60)
    
    # Get absolute path to data directory
    data_dir = os.path.abspath('data')
    
    if not os.path.exists(data_dir):
        print(f"✗ Error: Data directory not found: {data_dir}")
        sys.exit(1)
    
    # Connect as postgres
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='postgres',
            password=POSTGRES_PASSWORD,
            dbname='querycraft_db'
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        print(f"\n✓ Connected to database")
        print(f"✓ Data directory: {data_dir}\n")
        
        # Load each CSV file
        loaded_count = 0
        for csv_file, table_name in CSV_MAPPING.items():
            csv_path = os.path.join(data_dir, csv_file)
            
            if not os.path.exists(csv_path):
                print(f"✗ Warning: CSV file not found: {csv_path}")
                continue
            
            print(f"Loading {csv_file} → macht413.{table_name}...")
            
            # Use COPY command
            with open(csv_path, 'r', encoding='utf-8') as f:
                # Read first line to check if it's a header
                first_line = f.readline()
                f.seek(0)  # Reset to beginning
                
                # Skip header if present (check if first char is not a digit)
                has_header = not first_line[0].isdigit() if first_line else False
                
                try:
                    cur.copy_expert(
                        f"COPY macht413.{table_name} FROM STDIN WITH (FORMAT csv, HEADER {str(has_header).lower()}, NULL '', DELIMITER ',')",
                        f
                    )
                    
                    # Get row count
                    cur.execute(f"SELECT COUNT(*) FROM macht413.{table_name}")
                    row_count = cur.fetchone()[0]
                    
                    print(f"  ✓ Loaded {row_count:,} rows\n")
                    loaded_count += 1
                    
                except Exception as e:
                    print(f"  ✗ Error loading {csv_file}: {e}\n")
                    import traceback
                    traceback.print_exc()
        
        # Verify all tables
        print("=" * 60)
        print("Verification - Row counts per table:")
        print("=" * 60)
        
        total_rows = 0
        for table_name in CSV_MAPPING.values():
            cur.execute(f"SELECT COUNT(*) FROM macht413.{table_name}")
            count = cur.fetchone()[0]
            total_rows += count
            print(f"  {table_name:10s}: {count:,} rows")
        
        print(f"\n  Total rows: {total_rows:,}")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print(f"✓ Data loading complete! ({loaded_count}/9 tables loaded)")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
