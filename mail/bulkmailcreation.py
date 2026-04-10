import requests
import random
import string
import time
import psycopg2
from fastapi import APIRouter, Query

from db.db import POSTGRESQL_DATABASE_URL_TELUGUWAP


router = APIRouter(prefix="/blomp-mails", tags=["blomp-mails"])


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
        random_string = ''.join(random.choices(string.ascii_lowercase, k=15))
        email = f"userref{random_string}@{domain}"

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

@router.get("/trigger-mail-creation")
async def trigger_login(limit: int = Query(2)):
    create_bulk_accounts(limit)
    return {"status": "Bulk mails creation started"}

