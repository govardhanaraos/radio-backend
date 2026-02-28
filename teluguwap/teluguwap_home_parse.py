import re
from bs4 import BeautifulSoup
import psycopg2
import requests
from fastapi import APIRouter
from db.db import POSTGRESQL_DATABASE_URL_TELUGUWAP

router = APIRouter(
    prefix="/teluguwaproot",
    tags=["teluguwaproot"],
)

def get_connection():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL_TELUGUWAP)
    cur = conn.cursor()
    return conn, cur


def insert_header(cur, conn, name):
    cur.execute("""
        INSERT INTO teluguwap_collection_type_header (header_name)
        VALUES (%s)
        ON CONFLICT (header_name) DO NOTHING
        RETURNING id
    """, (name,))

    row = cur.fetchone()

    if row is None:
        cur.execute("SELECT id FROM teluguwap_collection_type_header WHERE header_name = %s", (name,))
        row = cur.fetchone()

    conn.commit()
    return row[0]


def extract_text_and_count(text):
    """
    Input:  "2026 [71]"
    Output: ("2026", 71)
    """
    match = re.search(r"\[(\d+)\]", text)
    count = int(match.group(1)) if match else 0

    clean_text = re.sub(r"\s*\[\d+\]\s*", "", text).strip()
    return clean_text, count


def parse_teluguwap_root():
    conn, cur = get_connection()

    URL = "https://teluguwap.in/"

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://google.com",
    }

    response = requests.get(URL, headers=headers, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    print(response.text)
    year_block = None
    for div in soup.find_all("div", class_="bg"):
        if "Year List" in div.text:
            year_block = div
            break

    if not year_block:
        conn.close()
        return {"status": "error", "message": "Year List block not found"}

    header_id = insert_header(cur, conn, "Year List")

    select_tag = year_block.find("select")
    if not select_tag:
        conn.close()
        return {"status": "error", "message": "Year List <select> not found"}

    LANG = "Telugu"

    for opt in select_tag.find_all("option"):
        value = opt.get("value")
        text = opt.text.strip()

        if not value or value.lower() == "select":
            continue

        clean_text, count = extract_text_and_count(text)

        cur.execute("""
            INSERT INTO teluguwap_collection_type_details 
                (header_id, option_value, option_text, count, language)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (header_id, option_value)
            DO UPDATE SET 
                option_text = EXCLUDED.option_text,
                count = EXCLUDED.count
        """, (header_id, value, clean_text, count, LANG))

    conn.commit()
    conn.close()

    return {"status": "success", "message": "Year List parsed with count successfully"}


@router.get("/parse")
def run_parse():
    return parse_teluguwap_root()