import requests
import uuid
import time
import psycopg2
from db.db import POSTGRESQL_DATABASE_URL_TELUGUWAP, BLOMP_USER, BLOMP_PASS

def get_db_connection():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL_TELUGUWAP)
    return conn, conn.cursor()

def save_to_neon(email, email_pass, blomp_pass):
    try:
        conn, cur = get_db_connection()


        insert_query = """
        INSERT INTO user_mail_accounts (email, email_password, blomp_password)
        VALUES (%s, %s, %s);
        """
        cur.execute(insert_query, (email, email_pass, blomp_pass))

        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Database Error: {e}")
        return False


def create_bulk_accounts(count=50):
    blomp_pass = "Retail@505Anb"
    created = 0

    while created < count:
        # 1. Get Domain from Mail.tm
        domain_res = requests.get("https://api.mail.tm/domains").json()
        domain = domain_res['hydra:member'][0]['domain']

        # 2. Generate Account
        email = f"user_ref_{uuid.uuid4().hex[:6]}@{domain}"
        email_pass = "MailPass123!"

        # 3. Register with Mail.tm
        payload = {"address": email, "password": email_pass}
        reg_res = requests.post("https://api.mail.tm/accounts", json=payload)

        if reg_res.status_code == 201:
            # 4. Save to Neon
            if save_to_neon(email, email_pass, blomp_pass):
                created += 1
                print(f"[{created}/{count}] Saved to DB: {email}")

            time.sleep(5)  # Delay to respect rate limits
        else:
            print("Rate limit or error. Waiting 60s...")
            time.sleep(60)


if __name__ == "__main__":
    create_bulk_accounts(10)  # Start with 10 to test