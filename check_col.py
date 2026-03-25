import psycopg2, os
from dotenv import load_dotenv

load_dotenv('.env')
conn = psycopg2.connect(os.environ.get('POSTGRESQL_DATABASE_URL_TELUGUWAP'))
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE hindiflacs_albums_list ADD COLUMN collection_id INTEGER REFERENCES hindiflacs_collection_type_details(id) ON DELETE SET NULL;")
    conn.commit()
    print("Column added successfully.")
except psycopg2.errors.DuplicateColumn:
    print("Column already exists.")
    conn.rollback()
except Exception as e:
    print(f"Error: {e}")
    conn.rollback()

try:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='hindiflacs_albums_list';")
    print([row[0] for row in cur.fetchall()])
except Exception as e:
    print(f"Error reading cols: {e}")

conn.close()
