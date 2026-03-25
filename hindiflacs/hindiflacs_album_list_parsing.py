import logging
import re
from urllib.parse import urljoin
import psycopg2
import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter
from db.db import POSTGRESQL_DATABASE_URL
from db.db import POSTGRESQL_DATABASE_URL_TELUGUWAP

router = APIRouter(prefix="/hindiflacs-albums", tags=["hindiflacs-albums"])

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("hindiflacs_albums")

def get_connection():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL_TELUGUWAP)
    return conn, conn.cursor()

def clean(text):
    if not text:
        return None
    text = text.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip()

def get_all_option_values(cur, limit=5):
    cur.execute("""
        SELECT id, option_value 
        FROM hindiflacs_collection_type_details
        WHERE details_status != 'completed' OR details_status IS NULL
        ORDER BY id
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    return [(row[0], row[1]) for row in rows] if rows else []

def detect_album_type(img_src, text_block):
    if img_src:
        src = img_src.lower()
        if "dig" in src:
            return "digital"
        if "cd" in src:
            return "Audio CD"
        if "vinyl" in src:
            return "vinyl"
        if "atmos" in src:
            return "atmos"
        if "flac" in src:
            return "flac"
        if "music" in src:
            return "bgm"
        if "m4a" in src:
            return "Digital (Apple)"

    if text_block:
        text = text_block.lower()
        if "audio cd" in text or "cd rip" in text or "original cd" in text:
            return "Audio CD"
        if "digital" in text or "dig rip" in text:
            return "digital"
        if "vinyl" in text:
            return "vinyl"
        if "atmos" in text:
            return "atmos"
        if "flac" in text or "lossless" in text:
            return "flac"

    return "unknown"

def upsert_album(cur, conn, album, collection_id=None):
    cur.execute(
        """
        INSERT INTO hindiflacs_albums_list (
            album_name, album_link, album_cover,
            hindiflacs_actors, director_name, music_director,
            total_files, album_type, collection_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (album_link)
        DO UPDATE SET
            album_name = EXCLUDED.album_name,
            album_cover = EXCLUDED.album_cover,
            hindiflacs_actors = EXCLUDED.hindiflacs_actors,
            director_name = EXCLUDED.director_name,
            music_director = EXCLUDED.music_director,
            total_files = EXCLUDED.total_files,
            album_type = EXCLUDED.album_type,
            collection_id = COALESCE(EXCLUDED.collection_id, hindiflacs_albums_list.collection_id)
        RETURNING id
        """,
        (
            album["album_name"],
            album["album_link"],
            album["album_cover"],
            album["actors"],
            album["director"],
            album["music"],
            album["total_files"],
            album["album_type"],
            collection_id,
        ),
    )
    row = cur.fetchone()
    conn.commit()
    return row[0] if row else None

def normalize_url(url, remove_base):
    if not url:
        return url
    return url.replace(remove_base, "")

def parse_album_cards(soup):
    albums = []

    grid = soup.select_one("div.search-section div.related-albums-grid")
    if not grid:
        return albums

    cards = grid.find_all("div", class_="related-album-card")

    for card in cards:
        table = card.find("table")
        if not table:
            continue

        tds = table.find_all("td")
        if len(tds) < 2:
            continue

        cover_td = tds[0]
        a_cover = cover_td.find("a")
        album_link = normalize_url(a_cover["href"], "https://hindiflacs.com") if a_cover else None

        img = cover_td.find("img")
        album_cover = normalize_url(img["src"], "https://hindiflacs.com") if img else None

        info_td = tds[1]
        a_title = info_td.find("a")
        strong_title = a_title.find("strong") if a_title else None
        album_name = clean(strong_title.get_text(strip=True)) if strong_title else None

        actors = None
        music = None
        album_type = None
        total_files = None

        for element in info_td.contents:
            if isinstance(element, str):
                continue

            if element.name == "strong" and element.get_text(strip=True) == "⭐":
                actors_text = element.next_sibling
                if actors_text:
                    actors = clean(str(actors_text).replace("<br/>", "").strip())
            
            if element.name == "strong" and element.get_text(strip=True) == "🎼":
                music_text = element.next_sibling
                if music_text:
                    music = clean(str(music_text).replace("<br/>", "").strip())
            
            if element.name == "img" and element.get("src"):
                img_src = element["src"]
                type_text = element.next_sibling
                if type_text:
                    album_type = clean(type_text.replace("<br/>", ""))
        
        if not album_type and img:
            album_type = detect_album_type(img["src"], info_td.get_text(" ", strip=True))
        
        albums.append({
            "album_name": album_name,
            "album_link": album_link,
            "album_cover": album_cover,
            "actors": actors,
            "music": music,
            "director": None,
            "total_files": None,
            "album_type": album_type
        })

    return albums

def find_next_page_url(soup, current_url):
    pagination = soup.find("div", class_="pagination")
    if not pagination:
        return None

    elements = list(pagination.children)
    active_found = False

    for el in elements:
        if not hasattr(el, "name"):
            continue

        if el.name == "span" and "active" in (el.get("class") or []):
            active_found = True
            continue

        if active_found and el.name == "a":
            href = el.get("href")
            if href:
                return urljoin(current_url, href)

    return None

def crawl_album_list(option_value, collection_id=None):
    base_url = "https://hindiflacs.com/"
    start_url = urljoin(base_url, option_value.lstrip("/"))

    conn, cur = get_connection()

    url = start_url
    page = 1
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; SM-G975F) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        )
    }

    while url:
        logger.info(f"Fetching page {page}: {url}")
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        albums = parse_album_cards(soup)
        logger.info(f"Found {len(albums)} albums on page {page}")

        for album in albums:
            album_id = upsert_album(cur, conn, album, collection_id)
            logger.debug(f"Saved album: {album['album_name']} (ID: {album_id})")

        next_url = find_next_page_url(soup, url)
        if not next_url:
            logger.info("Reached last page.")
            break

        url = next_url
        page += 1

    update_collection_type_status(cur, conn, option_value, "completed")

    conn.close()
    return {"status": "success", "message": f"Completed crawling {option_value}"}

def update_collection_type_status(cur, conn, option_value, status="completed"):
    cur.execute("""
        UPDATE hindiflacs_collection_type_details
        SET details_status = %s,
            details_updated_at = NOW()
        WHERE option_value = %s
    """, (status, option_value))

    conn.commit()

def crawl_all_album_lists(limit: int = 5):
    conn, cur = get_connection()
    option_values = get_all_option_values(cur, limit)
    conn.close()

    if not option_values:
        return {"status": "error", "message": "No option values found"}

    results = []
    for collection_id, option_value in option_values:
        logger.info(f"Starting crawl for: {option_value}")
        try:
            result = crawl_album_list(option_value, collection_id)
            results.append(result)
        except Exception as e:
            logger.error(f"Error crawling {option_value}: {e}")
            results.append({"status": "error", "option_value": option_value, "message": str(e)})

    return {
        "status": "success",
        "message": "Bulk album crawling completed",
        "total_categories": len(option_values),
        "details": results
    }

@router.get("/crawl/{option_value}")
def crawl(option_value: str, collection_id: int = None):
    if collection_id is None:
        conn, cur = get_connection()
        cur.execute("SELECT id FROM hindiflacs_collection_type_details WHERE option_value = %s", (option_value,))
        row = cur.fetchone()
        conn.close()
        collection_id = row[0] if row else None
    return crawl_album_list(option_value, collection_id)

@router.get("/crawl-all")
def crawl_all(limit: int = 5):
    return crawl_all_album_lists(limit)
