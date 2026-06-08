import yaml
import os
import csv
import glob

schema_path = r'c:\Users\surji\HPE_CPP49\backend\schema_store\enriched_schema.yaml'
bounds_path = r'c:\Users\surji\HPE_CPP49\backend\schema_store\database_bounds.yaml'

with open(schema_path, 'r', encoding='utf-8') as f:
    schema = yaml.safe_load(f)

with open(bounds_path, 'r', encoding='utf-8') as f:
    bounds = yaml.safe_load(f)['database_bounds']

def expand_columns(table_name, columns_dict, db_bounds):
    expanded_cols = set()
    for col_name in columns_dict.keys():
        if '[n]' in col_name:
            array_prefix = col_name.split('[n]')[0] + '[n]'
            col_bounds = db_bounds.get(table_name, {}).get(array_prefix)
            if col_bounds:
                start, end = col_bounds
                for i in range(start, end + 1):
                    expanded_cols.add(col_name.replace('[n]', str(i)))
            else:
                expanded_cols.add(col_name) # fallback
        else:
            expanded_cols.add(col_name)
    return expanded_cols

def normalize_csv_col(col):
    col = col.strip().lower()
    col = col.replace('-', '_').replace(' ', '_')
    return col

# Mapping: (Folder Path, Schema Mapping Key)
folders = [
    (r'c:\Users\surji\HPE_CPP49\backend\data\D1', 'macht413'),
    (r'c:\Users\surji\HPE_CPP49\backend\data\D2', 'machd500')
]

for db_path, db_key in folders:
    print(f"\nVerifying {db_path}...")
    db_bounds = bounds.get(db_key, {})
    
    csv_files = glob.glob(os.path.join(db_path, '*csv'))
    
    for csv_file in csv_files:
        filename = os.path.basename(csv_file)
        table_name = filename.replace('csv', '').lower()
        
        # Check if table is in schema
        if table_name not in schema:
            print(f"  [!] Table {table_name} missing from schema entirely!")
            continue
            
        # Get schema columns
        schema_cols = expand_columns(table_name, schema[table_name].get('columns', {}), db_bounds)
        schema_cols = {normalize_csv_col(c) for c in schema_cols}
        
        # Read CSV headers
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            headers = next(reader)
        
        csv_cols = {normalize_csv_col(c) for c in headers}
        
        # Compare
        missing_in_schema = csv_cols - schema_cols
        
        if missing_in_schema:
            print(f"  [X] Table {table_name}: {len(missing_in_schema)} columns in CSV are NOT in schema:")
            for c in list(missing_in_schema)[:10]:
                print(f"      - {c}")
            if len(missing_in_schema) > 10:
                print(f"      - ... and {len(missing_in_schema)-10} more.")
        else:
            print(f"  [OK] Table {table_name}: All {len(csv_cols)} CSV columns covered in schema.")

print("\nDone.")
