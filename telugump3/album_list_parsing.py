import logging
import re
from urllib.parse import urljoin
import psycopg2
import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter
from db.db import POSTGRESQL_DATABASE_URL

router = APIRouter(prefix="/telugump3albums", tags=["telugump3albums"])

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("pymongo.topology").setLevel(logging.WARNING)
logging.getLogger("pymongo.connection").setLevel(logging.WARNING)
logger = logging.getLogger("telugump3_albums")


def get_connection():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL)
    return conn, conn.cursor()


def clean_text(text):
    if not text:
        return None
    text = text.encode("ascii", "ignore").decode()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def ensure_albums_table(cur, conn):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS albums_list (
        id SERIAL PRIMARY KEY,
        album_name TEXT NOT NULL,
        album_link TEXT NOT NULL UNIQUE,
        album_cover TEXT,
        actors TEXT,
        director_name TEXT,
        music_director TEXT,
        total_files TEXT,
        year INT,
        decade TEXT,
        rating TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """)
    conn.commit()


def get_one_option_value(cur):
    cur.execute("SELECT option_value FROM collection_type_details where id='8'")
    row = cur.fetchone()
    return row[0] if row else None

def get_all_option_values(cur):
    cur.execute("SELECT option_value FROM collection_type_details ORDER BY id")
    rows = cur.fetchall()
    return [row[0] for row in rows] if rows else []

def upsert_album(cur, conn, album):
    cur.execute("""
        INSERT INTO albums_list (
            album_name, album_link, album_cover,
            actors, director_name, music_director, total_files
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (album_link) DO NOTHING
        RETURNING id
    """, (
        album["album_name"],
        album["album_link"],
        album["album_cover"],
        album["actors"],
        album["director_name"],
        album["music_director"],
        album["total_files"],
    ))

    row = cur.fetchone()
    if row is None:
        logger.debug(f"Duplicate album skipped: {album['album_name']}")
    else:
        logger.debug(f"Inserted new album: {album['album_name']}")

    conn.commit()


# ⭐⭐⭐ CORRECTED ALBUM PARSER FOR YOUR HTML ⭐⭐⭐
def parse_album_block(bg_div, base_url):
    table = bg_div.find("table")
    if not table:
        return None

    tds = table.find_all("td")
    if len(tds) < 2:
        return None

    # Cover image
    img = tds[0].find("img")
    if img:
        album_cover = img["src"]
    else:
        album_cover = None  # folder icon → no image

    # Album name + link
    a_tag = tds[1].find("a")
    if not a_tag:
        return None

    strong = a_tag.find("strong")
    album_name = clean_text(strong.get_text(strip=True)) if strong else None
    album_link = a_tag["href"]

    # Default values
    actors = director_name = music_director = total_files = None

    # Parse p tags (actors, director, music)
    for p in tds[1].find_all("p"):
        text = p.get_text(strip=True)
        if text.startswith("🕺"):
            actors = text.replace("🕺:", "").strip()
        elif text.startswith("🎥"):
            director_name = text.replace("🎥:", "").strip()
        elif text.startswith("🎹"):
            music_director = text.replace("🎹:", "").strip()

    # Parse total files (always outside <p>)
    for b in tds[1].find_all("b"):
        if b.get_text(strip=True).startswith("♬"):
            if b.next_sibling:
                total_files = clean_text(b.next_sibling.strip())

    if not album_name or not album_link:
        return None

    return {
        "album_name": album_name,
        "album_link": album_link,
        "album_cover": album_cover,
        "actors": actors,
        "director_name": director_name,
        "music_director": music_director,
        "total_files": total_files,
    }


# ⭐⭐⭐ PAGINATION HANDLER ⭐⭐⭐
def find_next_page_url(soup, current_url):
    nav = soup.find("div", class_="pagination-nav")
    if not nav:
        return None

    anchors = nav.find_all("a")
    active_index = None

    for i, a in enumerate(anchors):
        if "active" in (a.get("class") or []):
            active_index = i
            break

    if active_index is None:
        return None

    if active_index + 1 >= len(anchors):
        return None

    next_href = anchors[active_index + 1].get("href")
    return urljoin(current_url, next_href) if next_href else None


# ⭐⭐⭐ MAIN CRAWLER ⭐⭐⭐
def crawl_albums_for_option(option_value):
    base_url = "https://mp3.teluguwap.in/"
    start_url = urljoin(base_url, option_value.lstrip("/"))

    conn, cur = get_connection()
    ensure_albums_table(cur, conn)

    url = start_url
    page_num = 1

    while url:
        logger.debug(f"Fetching page {page_num}: {url}")
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        container = soup.find("div", class_="container")
        if not container:
            break

        bg_divs = container.find_all("div", class_="bg")
        logger.debug(f"Found {len(bg_divs)} albums on page {page_num}")

        for bg in bg_divs:
            album = parse_album_block(bg, base_url)
            if album:
                logger.debug(f"Saving album: {album['album_name']}")
                upsert_album(cur, conn, album)

        next_url = find_next_page_url(soup, url)
        if not next_url:
            logger.debug("Reached last page.")
            break

        url = next_url
        page_num += 1

    conn.close()
    return {"status": "success", "message": f"Crawled all pages for {option_value}"}


@router.get("/crawl-one")
def crawl_one_option():
    conn, cur = get_connection()
    option_value = get_one_option_value(cur)
    conn.close()

    if not option_value:
        return {"status": "error", "message": "No option_value found"}

    logger.debug(f"Starting crawl for: {option_value}")
    return crawl_albums_for_option(option_value)

@router.get("/crawl-all")
def crawl_all_options():
    conn, cur = get_connection()
    option_values = get_all_option_values(cur)
    conn.close()

    if not option_values:
        return {"status": "error", "message": "No option values found"}

    results = []

    for option_value in option_values:
        logger.debug(f"Starting crawl for: {option_value}")
        result = crawl_albums_for_option(option_value)
        results.append(result)

    return {
        "status": "success",
        "message": "Crawled all album list pages",
        "count": len(option_values),
        "details": results
    }