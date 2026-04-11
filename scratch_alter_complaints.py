import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

PG_URL = os.getenv("POSTGRESQL_DATABASE_URL_TELUGUWAP")

def alter_table():
    print("Connecting to PostgreSQL...")
    pg_conn = psycopg2.connect(PG_URL)
    pg_cur = pg_conn.cursor()

    print("Altering cust_feedback_complaints...")
    pg_cur.execute("""
        ALTER TABLE cust_feedback_complaints ADD COLUMN IF NOT EXISTS device_id TEXT;
        ALTER TABLE cust_feedback_complaints ADD COLUMN IF NOT EXISTS status VARCHAR(10) DEFAULT 'P';
        ALTER TABLE cust_feedback_complaints ADD COLUMN IF NOT EXISTS admin_response TEXT;
        ALTER TABLE cust_feedback_complaints ADD COLUMN IF NOT EXISTS replied_at TIMESTAMP;
    """)
    pg_conn.commit()

    pg_cur.close()
    pg_conn.close()
    print("Table altered successfully!")

if __name__ == "__main__":
    alter_table()
