import os
import psycopg2
import sys
import csv

POSTGRES_PASSWORD = "371773"

def sanitize(col):
    return col.strip().lower().replace('-', '_').replace(' ', '_').replace('.', '_')

def get_col_type(col_name):
    if 'timestamp' in col_name:
        return 'TIMESTAMP'
    if col_name in ['system_name', 'process_name', 'device_name', 'object_uid', 'run_unit', 'ip_ip_addr', 'gmom_sysname', 'gmom_process_name', 'ancestor_sysname', 'ancestor_process_name']:
        return 'TEXT'
    if 'name' in col_name or 'letter' in col_name or 'u_loadid' in col_name or 'format_version' in col_name or 'data_version' in col_name or 'os_version' in col_name:
        return 'TEXT'
    # Any other specific text fields based on schema
    if col_name in ['u_gmom_gmom_gmom_node', 'u_gmom_gmom_gmom_cpu', 'u_gmom_gmom_gmom_pin', 'u_gmom_gmom_gmom_jobid']:
        return 'TEXT' # sometimes these contain hex or weird chars
    
    # Catch-all numeric
    return 'BIGINT'

def main():
    print("=" * 60)
    print("QueryCraft Dynamic CSV Loader")
    print("=" * 60)
    
    data_dir = r"c:\Users\surji\HPE_CPP49\backend\data"
    
    try:
        conn = psycopg2.connect(
            host='localhost', port=5432,
            user='postgres', password=POSTGRES_PASSWORD,
            dbname='querycraft_db'
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # We process D1 and D2
        schemas = [
            ('macht413', os.path.join(data_dir, 'D1')),
            ('machd500', os.path.join(data_dir, 'D2'))
        ]
        
        for schema_name, d_dir in schemas:
            print(f"\n--- Processing Schema {schema_name} ---")
            
            # Create schema
            cur.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE;")
            cur.execute(f"CREATE SCHEMA {schema_name};")
            
            # Find all CSV files in this directory
            if not os.path.exists(d_dir):
                print(f"Directory {d_dir} does not exist. Skipping.")
                continue
                
            csv_files = [f for f in os.listdir(d_dir) if f.endswith('csv')]
            
            for csv_file in csv_files:
                table_name = csv_file.replace('csv', '').lower()
                csv_path = os.path.join(d_dir, csv_file)
                
                # Read header
                with open(csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    try:
                        header = next(reader)
                    except StopIteration:
                        print(f"File {csv_file} is empty. Skipping.")
                        continue
                        
                # Build CREATE TABLE
                columns_ddl = []
                for col in header:
                    clean_col = sanitize(col)
                    ctype = get_col_type(clean_col)
                    columns_ddl.append(f'"{clean_col}" {ctype}')
                    
                create_stmt = f"CREATE TABLE {schema_name}.{table_name} (\n  " + ",\n  ".join(columns_ddl) + "\n);"
                
                try:
                    cur.execute(create_stmt)
                    
                    # Load data using COPY
                    with open(csv_path, 'r', encoding='utf-8-sig') as f:
                        cur.copy_expert(
                            f"COPY {schema_name}.{table_name} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '', DELIMITER ',')",
                            f
                        )
                        
                    # Get row count
                    cur.execute(f"SELECT COUNT(*) FROM {schema_name}.{table_name}")
                    row_count = cur.fetchone()[0]
                    print(f"  + Loaded {row_count:,} rows into {schema_name}.{table_name}")
                    
                except Exception as e:
                    print(f"  [X] Failed to load {table_name}: {e}")
                    # Keep going for other tables

    except Exception as e:
        print(f"Database connection failed: {e}")

if __name__ == '__main__':
    main()
