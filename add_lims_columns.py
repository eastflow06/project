import sqlite3
import os

DB_PATH = '/home/ubuntu/project/db/lims.db'

def add_columns():
    if not os.path.exists(DB_PATH):
        print(f"DB file not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    columns_to_add = [
        ('test_summary', 'TEXT'),
        ('formulation_info', 'TEXT'),
        ('image_urls', 'TEXT'),
        ('reference_links', 'TEXT'),
        ('start_month', 'TEXT'),
        ('end_month', 'TEXT')
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE test_results ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print(f"Column already exists: {col_name}")
            else:
                print(f"Error adding column {col_name}: {e}")

    conn.commit()
    conn.close()
    print("Database schema update completed.")

if __name__ == '__main__':
    add_columns()
