import logging
from urllib.parse import urljoin
import psycopg2
import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter
from db.db import POSTGRESQL_DATABASE_URL
import re

router = APIRouter(
    prefix="/telugump3songdetails",
    tags=["telugump3songdetails"],
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("song_details")


def get_connection():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL)
    return conn, conn.cursor()


def clean_text(text):
    if not text:
        return None
    text = text.encode("ascii", "ignore").decode()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_song_details(html, base_url):
    soup = BeautifulSoup(html, "html.parser")

    title_div = soup.find("div", class_="nav-section")
    song_title = title_div.find("h2").get_text(strip=True) if title_div else None

    info_div = soup.find("div", class_="info")
    singers = composer = duration = None

    if info_div:
        raw = info_div.get_text(" ", strip=True)
        cleaned = clean_text(raw)

        if "Singers:" in cleaned:
            singers = cleaned.split("Singers:")[1].split("Composer:")[0].strip()

        if "Composer:" in cleaned:
            composer = cleaned.split("Composer:")[1].split("Duration:")[0].strip()

        if "Duration:" in cleaned:
            duration = cleaned.split("Duration:")[1].strip()

    download_div = soup.find("div", class_="download-options")
    original = kb128 = kb320 = None

    if download_div:
        for a in download_div.find_all("a"):
            text = a.get_text(strip=True)
            href = a["href"]
            size = None

            if "(" in text and ")" in text:
                size = text[text.find("(")+1:text.find(")")]

            if "Original" in text:
                original = {"link": href, "text": text, "size": size}
            elif "320" in text:
                kb320 = {"link": href, "text": text, "size": size}
            elif "128" in text:
                kb128 = {"link": href, "text": text, "size": size}

    return {
        "song_title": song_title,
        "singers": singers,
        "composer": composer,
        "duration": duration,
        "original": original,
        "kb128": kb128,
        "kb320": kb320
    }

def save_song_details_to_db(song_id, data):
    conn, cur = get_connection()

    cur.execute("""
        UPDATE songs SET
            singers=%s,
            composer=%s,
            duration=%s,

            download_link_original=%s,
            download_text_original=%s,
            download_size_original=%s,

            download_link_128kbps=%s,
            download_text_128kbps=%s,
            download_size_128kbps=%s,

            download_link_320kbps=%s,
            download_text_320kbps=%s,
            download_size_320kbps=%s
        WHERE id=%s
    """, (
        data["singers"],
        data["composer"],
        data["duration"],

        data["original"]["link"] if data["original"] else None,
        data["original"]["text"] if data["original"] else None,
        data["original"]["size"] if data["original"] else None,

        data["kb128"]["link"] if data["kb128"] else None,
        data["kb128"]["text"] if data["kb128"] else None,
        data["kb128"]["size"] if data["kb128"] else None,

        data["kb320"]["link"] if data["kb320"] else None,
        data["kb320"]["text"] if data["kb320"] else None,
        data["kb320"]["size"] if data["kb320"] else None,

        song_id
    ))

    conn.commit()
    conn.close()


@router.get("/crawl")
def crawl_song_details(song_id: str):
    base_url = "https://mp3.teluguwap.in/"

    # Normalize input
    clean_id = song_id.replace("?fid=", "").replace("fid=", "").strip()
    relative_url = f"?fid={clean_id}"

    # Build full URL
    song_url = f"{base_url}{relative_url}"
    logger.debug(f"Fetching song details: {song_url}")

    # Fetch HTML
    html = requests.get(song_url, timeout=20).text
    data = parse_song_details(html, base_url)

    # Find song_id in DB
    conn, cur = get_connection()
    cur.execute("SELECT id FROM songs WHERE song_link=%s", (relative_url,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {"error": "Song not found in DB"}

    db_song_id = row[0]

    # Save parsed details
    save_song_details_to_db(db_song_id, data)

    return {
        "status": "success",
        "song": data["song_title"],
        "song_id": db_song_id,
        "relative_url": relative_url
    }