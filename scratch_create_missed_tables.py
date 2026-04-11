import os
import psycopg2
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URL")
MONGO_DB_NAME = os.getenv("DB_NAME") or "GRRadio"
PG_URL = os.getenv("POSTGRESQL_DATABASE_URL_TELUGUWAP")

def setup_missed_tables():
    print("Connecting to PostgreSQL...")
    pg_conn = psycopg2.connect(PG_URL)
    pg_cur = pg_conn.cursor()

    print("Creating admin_users and user_actions_logs tables...")
    pg_cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_actions_logs (
            id SERIAL PRIMARY KEY,
            device_id TEXT NOT NULL,
            event TEXT NOT NULL,
            details JSONB,
            client_timestamp TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
    """)
    pg_conn.commit()

    print("Migrating admin_users data from MongoDB...")
    try:
        mongo_client = MongoClient(MONGO_URI)
        mongo_db = mongo_client[MONGO_DB_NAME]
        admin_users = list(mongo_db['admin_users'].find())
        
        for user in admin_users:
            username = user.get("username")
            password = user.get("password")
            
            # Use ON CONFLICT DO NOTHING to prevent errors if running multiple times
            pg_cur.execute("""
                INSERT INTO admin_users (username, password)
                VALUES (%s, %s)
                ON CONFLICT (username) DO NOTHING;
            """, (username, password))
            
        pg_conn.commit()
        print(f"Migrated {len(admin_users)} admin users.")
    except Exception as e:
        print(f"Error accessing MongoDB: {e}")
        print("Continuing without migrating admin data (will use default admin setup).")

    pg_cur.close()
    pg_conn.close()
    print("Missed tables successfully created/updated in PostgreSQL!")

if __name__ == "__main__":
    setup_missed_tables()
