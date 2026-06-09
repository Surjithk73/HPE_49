import os
import psycopg2
import sys
import csv

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

def load_schema_from_csv(schema_name: str, d_dir: str, append: bool = False):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from config import DB_HOST, DB_PORT, DB_NAME
    
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        user='postgres', password='371773',
        dbname=DB_NAME
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    results = {"schema": schema_name, "tables": {}}
    
    try:
        # Create schema
        if not append:
            cur.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE;")
            cur.execute(f"CREATE SCHEMA {schema_name};")
        else:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name};")
            
        cur.execute(f"GRANT USAGE ON SCHEMA {schema_name} TO querycraft_user;")
        
        # Find all CSV files in this directory
        if not os.path.exists(d_dir):
            raise Exception(f"Directory {d_dir} does not exist.")
            
        csv_files = [f for f in os.listdir(d_dir) if f.endswith('csv')]
        
        for csv_file in csv_files:
            table_name = csv_file.lower()
            if table_name.endswith('.csv'):
                table_name = table_name[:-4]
            if table_name.endswith('csv'):
                table_name = table_name[:-3]
                
            csv_path = os.path.join(d_dir, csv_file)
            
            # Read header
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    continue
                    
            # Build CREATE TABLE
            columns_ddl = []
            for col in header:
                clean_col = sanitize(col)
                ctype = get_col_type(clean_col)
                columns_ddl.append(f'"{clean_col}" {ctype}')
                
            create_stmt = f"CREATE TABLE {schema_name}.{table_name} (\n  " + ",\n  ".join(columns_ddl) + "\n);"
            
            try:
                # If appending, we might be replacing a specific table
                if append:
                    cur.execute(f"DROP TABLE IF EXISTS {schema_name}.{table_name} CASCADE;")
                    
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
                results["tables"][table_name] = row_count
                
            except Exception as e:
                results["tables"][table_name] = f"Error: {e}"

        # Grant read access to the application user
        try:
            cur.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema_name} TO querycraft_user;")
        except Exception as e:
            results["grant_error"] = str(e)

    finally:
        cur.close()
        conn.close()
        
    return results

def main():
    print("=" * 60)
    print("QueryCraft Dynamic CSV Loader")
    print("=" * 60)
    
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    
    schemas = [
        ('macht413', os.path.join(data_dir, 'D1')),
        ('machd500', os.path.join(data_dir, 'D2'))
    ]
    
    for schema_name, d_dir in schemas:
        print(f"\n--- Processing Schema {schema_name} ---")
        try:
            results = load_schema_from_csv(schema_name, d_dir)
            for table, count in results["tables"].items():
                if isinstance(count, int):
                    print(f"  + Loaded {count:,} rows into {schema_name}.{table}")
                else:
                    print(f"  [X] Failed to load {table}: {count}")
        except Exception as e:
            print(f"Failed to process schema {schema_name}: {e}")

if __name__ == '__main__':
    main()
