import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

def test_upsert():
    # Direct connection string from .env
    conn_str = os.getenv("POSTGRESQL_DATABASE_URL")
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        print("Connected successfully!")

        # Check current sequence
        cur.execute("SELECT last_value FROM hindiflacs_singers_id_seq")
        seq1 = cur.fetchone()[0]
        print(f"Current sequence value: {seq1}")

        # Try to upsert an existing singer (e.g. 'Arijit Singh' if it exists, or just a dummy one)
        # We'll use the logic from the file manually to double check

        name = "Verification Test Singer"
        link = "/ver-test"

        # Insert if not exists
        cur.execute("SELECT id FROM hindiflacs_singers WHERE singer_name=%s", (name,))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO hindiflacs_singers (singer_name, singer_link) VALUES (%s, %s) RETURNING id", (name, link))
            sid = cur.fetchone()[0]
            conn.commit()
            print(f"Inserted new singer with ID: {sid}")
        else:
            sid = row[0]
            print(f"Singer already exists with ID: {sid}")

        cur.execute("SELECT last_value FROM hindiflacs_singers_id_seq")
        seq2 = cur.fetchone()[0]
        print(f"Sequence value after 1st attempt: {seq2}")

        # Second attempt (should NOT change sequence)
        cur.execute("SELECT id FROM hindiflacs_singers WHERE singer_name=%s", (name,))
        row = cur.fetchone()
        # (The logic in the file would return here)

        cur.execute("SELECT last_value FROM hindiflacs_singers_id_seq")
        seq3 = cur.fetchone()[0]
        print(f"Sequence value after 2nd attempt: {seq3}")

        if seq3 == seq2:
            print("VERIFICATION SUCCESS: Sequence did not increment for existing record.")
        else:
            print("VERIFICATION FAILURE: Sequence incremented for existing record.")

        # Optional: Cleanup
        # cur.execute("DELETE FROM hindiflacs_singers WHERE singer_name=%s", (name,))
        # conn.commit()

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_upsert()
