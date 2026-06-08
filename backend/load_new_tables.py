import psycopg2
import os

try:
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        user='nonstop_measure',
        password='nonstop123',
        dbname='querycraft_db'
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    data_dir = r'c:\Users\surji\HPE_CPP49\backend\data\D2'
    
    for t in ['sqlp', 'sqls']:
        csv_path = os.path.join(data_dir, f"{t}csv")
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                cur.copy_expert(f"COPY macht413.{t} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '', DELIMITER ',')", f)
                cur.execute(f"SELECT COUNT(*) FROM macht413.{t}")
                print(f"Loaded {cur.fetchone()[0]} rows into {t}")
        else:
            print(f"File not found: {csv_path}")

except Exception as e:
    print(f"Error: {e}")
