"""
fix_all_column_types.py
=======================
Converts TEXT columns that should be BIGINT across all macht413 tables.

The CSV loader imports every column as TEXT by default. Columns that are
genuine strings (names, labels, version letters) stay as TEXT. Everything
else — counters, IDs, flags, sizes — gets cast to BIGINT so aggregate
functions (SUM, AVG, MAX, etc.) work correctly.

Safe to re-run: ALTER COLUMN is skipped if the column is already BIGINT.

Usage:
    python backend/setup_scripts/fix_all_column_types.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import DB_HOST, DB_PORT, DB_NAME, DB_PASSWORD
import psycopg2

# Connect as superuser (postgres) — needed for ALTER TABLE
SUPERUSER = "postgres"

# Columns that are legitimately TEXT and must NOT be cast
GENUINE_TEXT_COLS = {
    'system_name', 'device_name', 'process_name', 'file_name',
    'config_name', 'adapter_name', 'sac_name', 'storage_pool',
    'name', 'gmom_sysname', 'gmom_process_name',
    'ancestor_sysname', 'ancestor_process_name',
    # program file name parts
    'program_file_name_volume', 'program_file_name_subvol', 'program_file_name_filename',
    # file name parts
    'file_name_volume', 'file_name_subvol', 'file_name_filename',
}

# Substrings in a column name that indicate it is a genuine string field
TEXT_KEYWORDS = ('name', 'letter', 'uid', 'pool', 'config', 'adapter', 'sac', 'storage')


def should_cast_to_bigint(col: str) -> bool:
    """Return True if this TEXT column should be cast to BIGINT."""
    if col in GENUINE_TEXT_COLS:
        return False
    if any(kw in col.lower() for kw in TEXT_KEYWORDS):
        return False
    return True


def fix_table(cur, table: str) -> int:
    """
    Cast all eligible TEXT columns in `table` to BIGINT.
    Returns the number of columns altered.
    """
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'macht413' AND table_name = %s
        ORDER BY ordinal_position
    """, (table,))
    cols = cur.fetchall()

    altered = 0
    for col, dtype in cols:
        if dtype != 'text':
            continue
        if not should_cast_to_bigint(col):
            continue

        try:
            cur.execute(f"""
                ALTER TABLE macht413.{table}
                ALTER COLUMN {col} TYPE BIGINT USING {col}::BIGINT
            """)
            print(f"    ✓ {col}  TEXT → BIGINT")
            altered += 1
        except Exception as e:
            print(f"    ✗ {col}  FAILED: {e}")
            cur.connection.rollback()

    return altered


def main():
    pg_password = input(
        f"Enter password for PostgreSQL superuser '{SUPERUSER}': "
    ).strip()

    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=SUPERUSER,
            password=pg_password,
        )
        conn.autocommit = True
        cur = conn.cursor()
        print(f"\nConnected to {DB_NAME} as {SUPERUSER}\n")
    except psycopg2.Error as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    # Get all tables in macht413
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'macht413'
        ORDER BY table_name
    """)
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tables found: {tables}\n")

    total_altered = 0
    for table in tables:
        print(f"── {table} ──────────────────────────────────────────")
        n = fix_table(cur, table)
        total_altered += n
        if n == 0:
            print("    (no changes needed)")
        print()

    conn.close()
    print(f"Done. {total_altered} column(s) converted to BIGINT across {len(tables)} tables.")


if __name__ == "__main__":
    main()
