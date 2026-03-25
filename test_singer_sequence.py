import psycopg2
import os
import sys

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
POSTGRESQL_DATABASE_URL_TELUGUWAP = os.environ.get("POSTGRESQL_DATABASE_URL_TELUGUWAP")

def get_seq_val(cur):
    cur.execute("SELECT last_value FROM hindiflacs_singers_id_seq")
    return cur.fetchone()[0]

def test_upsert():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL_TELUGUWAP)
    cur = conn.cursor()

    name = "Test Singer " + os.urandom(4).hex()
    link = "/test-link"

    print(f"Testing with singer: {name}")

    # 1. First upsert (should increment sequence)
    from hindiflacs.hindiflacs_album_details_parsing import upsert_singer
    
    seq_before = get_seq_val(cur)
    sid1 = upsert_singer(cur, conn, name, link)
    seq_after = get_seq_val(cur)
    
    print(f"First upsert: ID={sid1}, Seq before={seq_before}, Seq after={seq_after}")

    # 2. Second upsert (should NOT increment sequence)
    seq_before2 = get_seq_val(cur)
    sid2 = upsert_singer(cur, conn, name, link)
    seq_after2 = get_seq_val(cur)

    print(f"Second upsert: ID={sid2}, Seq before={seq_before2}, Seq after={seq_after2}")

    if seq_after2 == seq_after:
        print("Success: Sequence did not increment for existing singer.")
    else:
        print("Failure: Sequence incremented even for existing singer.")

    # Cleanup
    cur.execute("DELETE FROM hindiflacs_singers WHERE id=%s", (sid1,))
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    test_upsert()
