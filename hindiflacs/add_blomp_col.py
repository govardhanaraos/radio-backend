import psycopg2
import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
POSTGRESQL_DATABASE_URL_TELUGUWAP = os.environ.get("POSTGRESQL_DATABASE_URL_TELUGUWAP")

def setup_mail_accounts():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL_TELUGUWAP)
    cur = conn.cursor()

    commands = [
        """
        CREATE TABLE IF NOT EXISTS user_mail_accounts (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            email_password VARCHAR(100),
            blomp_password VARCHAR(100),
            referral_status VARCHAR(100),
            last_login_date date ,created_at date default now(),
            default_account CHAR(1) DEFAULT 'N',
            sort_order INTEGER DEFAULT 0
        )
        """,
        """
        ALTER TABLE hindiflacs_songs ADD COLUMN IF NOT EXISTS blomp_user_id INTEGER;
        """
    ]

    for command in commands:
        cur.execute(command)

    conn.commit()
    cur.close()
    conn.close()
    print("user_mail_accounts and blomp_user_id set up successfully.")

if __name__ == '__main__':
    setup_mail_accounts()
