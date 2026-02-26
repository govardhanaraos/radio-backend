from bs4 import BeautifulSoup
import psycopg2
import requests
from fastapi import APIRouter
from db.db import POSTGRESQL_DATABASE_URL

router = APIRouter(
    prefix="/telugump3home",
    tags=["telugump3home"],
)


# ---------------------------------------
# PostgreSQL connection
# ---------------------------------------
def get_connection():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL)
    cur = conn.cursor()
    return conn, cur


# ---------------------------------------
# Insert header with ON CONFLICT protection
# ---------------------------------------
def insert_header(cur, conn, name):
    cur.execute("""
        INSERT INTO collection_type_header (header_name)
        VALUES (%s)
        ON CONFLICT (header_name) DO NOTHING
        RETURNING id
    """, (name,))

    row = cur.fetchone()

    if row is None:
        cur.execute("SELECT id FROM collection_type_header WHERE header_name = %s", (name,))
        row = cur.fetchone()

    conn.commit()
    return row[0]


# ---------------------------------------
# Main parsing function (runs only when called)
# ---------------------------------------
def parse_telugump3_home():
    conn, cur = get_connection()

    # Create tables if not exist
    cur.execute("""
    CREATE TABLE IF NOT EXISTS collection_type_header (
        id SERIAL PRIMARY KEY,
        header_name VARCHAR(100) NOT NULL UNIQUE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS collection_type_details (
        id SERIAL PRIMARY KEY,
        header_id INTEGER NOT NULL REFERENCES collection_type_header(id) ON DELETE CASCADE,
        option_value VARCHAR(255) NOT NULL,
        option_text VARCHAR(255) NOT NULL,
        language VARCHAR(50) DEFAULT 'Telugu',
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (header_id, option_value)
    )
    """)

    conn.commit()

    # Fetch HTML
    URL = "https://mp3.teluguwap.in/"
    response = requests.get(URL, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    nav_items = soup.find_all("div", class_="nav-item")
    LANG = "Telugu"

    for nav in nav_items:
        strong = nav.find("strong")
        if not strong:
            continue

        header_name = strong.text.strip().replace(":", "")

        if header_name not in ["A-Z List", "Year List", "Decade List"]:
            continue

        header_id = insert_header(cur, conn, header_name)

        select_tag = nav.find("select")
        if not select_tag:
            continue

        for opt in select_tag.find_all("option"):
            value = opt.get("value")
            text = opt.text.strip()

            if value == "select":
                continue

            cur.execute("""
                INSERT INTO collection_type_details (header_id, option_value, option_text, language)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (header_id, option_value)
                DO UPDATE SET option_text = EXCLUDED.option_text
            """, (header_id, value, text, LANG))

    conn.commit()
    conn.close()

    return {"status": "success", "message": "Data parsed and stored successfully"}


# ---------------------------------------
# FastAPI route to trigger parsing
# ---------------------------------------
@router.get("/parse")
def run_parse():
    return parse_telugump3_home()