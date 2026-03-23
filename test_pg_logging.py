import sys
import os
import asyncio
import psycopg2
from psycopg2.extras import Json

# Add current directory to sys.path
sys.path.append(os.getcwd())

# Import the URL directly or from db.db
from db.db import POSTGRESQL_DATABASE_URL

def test_pg_logging():
    print(f"Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(POSTGRESQL_DATABASE_URL)
        cur = conn.cursor()
        
        # Ensure table exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_actions_logs (
                id SERIAL PRIMARY KEY,
                device_id TEXT NOT NULL,
                event TEXT NOT NULL,
                details JSONB,
                client_timestamp TEXT,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Test Insertion
        device_id = "TEST_DEVICE_AG"
        event = "Test Event"
        details = {"action": "testing", "status": "success"}
        client_timestamp = "2026-03-23T18:00:00Z"
        
        cur.execute(
            "INSERT INTO user_actions_logs (device_id, event, details, client_timestamp) VALUES (%s, %s, %s, %s) RETURNING id",
            (device_id, event, Json(details), client_timestamp)
        )
        log_id = cur.fetchone()[0]
        conn.commit()
        print(f"Successfully inserted log with ID: {log_id}")
        
        # Verify Retrieval
        cur.execute("SELECT * FROM user_actions_logs WHERE id = %s", (log_id,))
        row = cur.fetchone()
        print(f"Retrieved log: {row}")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Verification failed: {e}")
        return False

if __name__ == "__main__":
    test_pg_logging()
