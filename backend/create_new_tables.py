import os
import psycopg2

data_dir = r'c:\Users\surji\HPE_CPP49\backend\data\D2'

def sanitize(col):
    sanitized = col.replace('.', '_').replace('{N}', '_n').replace('{', '_').replace('}', '')
    return sanitized

def get_col_type(col_name):
    if 'time' in col_name and not 'delta' in col_name and 'elapsed' not in col_name and 'qtime' not in col_name:
        if 'timestamp' in col_name: return 'TIMESTAMP'
    
    if col_name in ['system_name', 'process_name', 'device_name', 'object_uid', 'run_unit', 'ip_ip_addr']:
        return 'TEXT'
    if 'name' in col_name or 'letter' in col_name or 'u_loadid' in col_name:
        return 'TEXT'
        
    return 'BIGINT'

try:
    conn = psycopg2.connect(
        host='localhost', port=5432,
        user='nonstop_measure', password='nonstop123',
        dbname='querycraft_db'
    )
    conn.autocommit = True
    cur = conn.cursor()

    tables = ['cpu', 'disc', 'dfile', 'dopen', 'file', 'ossns', 'proc', 'tmf', 'udef', 'sqlp', 'sqls']
    for t in tables:
        csv_path = os.path.join(data_dir, f"{t}csv")
        with open(csv_path, 'r', encoding='utf-8') as f:
            header = f.readline().strip().split(',')
            
        columns = []
        for col in header:
            clean_col = sanitize(col)
            ctype = get_col_type(clean_col)
            columns.append(f'"{clean_col}" {ctype}')
            
        ddl = f"DROP TABLE IF EXISTS machd500.{t};\n"
        ddl += f"CREATE TABLE machd500.{t} (\n" + ",\n".join(columns) + "\n);"
        
        cur.execute(ddl)
        print(f"Created table machd500.{t}")

    print("Success")
except Exception as e:
    print(f"Error: {e}")
