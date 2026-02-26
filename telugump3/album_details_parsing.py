import logging
import re
from urllib.parse import urljoin
import psycopg2
import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter

from db.db import POSTGRESQL_DATABASE_URL

router = APIRouter(
    prefix="/telugump3albumdetails",
    tags=["telugump3albumdetails"],
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("album_details")


# ---------------------------------------
# DB Connection
# ---------------------------------------
def get_connection():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL)
    return conn, conn.cursor()


# ---------------------------------------
# Clean text helper (removes broken emoji bytes)
# ---------------------------------------
def clean_text(text):
    if not text:
        return None
    text = text.encode("ascii", "ignore").decode()
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------
# Ensure all required tables exist
# ---------------------------------------
def ensure_tables(cur, conn):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS actors (
        id SERIAL PRIMARY KEY,
        actor_name TEXT NOT NULL,
        actor_link TEXT,
        album_id INT REFERENCES albums_list(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS directors (
        id SERIAL PRIMARY KEY,
        director_name TEXT NOT NULL,
        director_link TEXT,
        album_id INT REFERENCES albums_list(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS music_directors (
        id SERIAL PRIMARY KEY,
        music_director_name TEXT NOT NULL,
        music_director_link TEXT,
        album_id INT REFERENCES albums_list(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS songs (
        id SERIAL PRIMARY KEY,
        album_id INT REFERENCES albums_list(id) ON DELETE CASCADE,
        song_name TEXT NOT NULL,
        song_link TEXT UNIQUE,
        play_link TEXT,
        file_size TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS singers (
        id SERIAL PRIMARY KEY,
        singer_name TEXT NOT NULL UNIQUE,
        singer_link TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS song_singers (
        song_id INT REFERENCES songs(id) ON DELETE CASCADE,
        singer_id INT REFERENCES singers(id) ON DELETE CASCADE,
        PRIMARY KEY (song_id, singer_id)
    );
    """)

    conn.commit()


# ---------------------------------------
# Parse Album Details HTML
# ---------------------------------------
def parse_album_details(html, base_url):
    soup = BeautifulSoup(html, "html.parser")

    # VALIDATION 1: must have folder-info
    folder = soup.find("div", class_="folder-info")
    if not folder:
        logger.warning("Skipping: no folder-info found (not an album details page)")
        return None

    # VALIDATION 2: must have album title <h3>
    h3 = folder.find("h3")
    if not h3:
        logger.warning("Skipping: no <h3> album title found")
        return None

    # VALIDATION 3: must contain at least one song (?fid=)
    has_song = soup.find("a", href=lambda x: x and "fid=" in x)
    if not has_song:
        logger.warning("Skipping: no songs found (not an album details page)")
        return None

    folder = soup.find("div", class_="folder-info")
    header_img = folder.find("img")
    album_cover =  header_img["src"] if header_img else None

    # Album name + rating
    # Album name + rating
    h3_text = folder.find("h3").get_text(" ", strip=True)
    h3_text = clean_text(h3_text)

    parts = h3_text.split("⭐")

    album_name = parts[0].strip()
    rating = None

    if len(parts) > 1:
        rating = parts[1].split("(")[0].strip()

    # Year + Decade
    year = None
    decade = None

    year_p = None
    for p in folder.find_all("p"):
        b = p.find("b")
        if b and "📅" in b.get_text():
            year_p = p
            break

    if year_p:
        links = year_p.find_all("a")
        if len(links) >= 1:
            year = clean_text(links[0].get_text(strip=True))
        if len(links) >= 2:
            decade = clean_text(links[1].get_text(strip=True))

    # Actors
    actors = []
    for p in folder.find_all("p"):
        if "👫" in p.get_text():
            for a in p.find_all("a"):
                actors.append({
                    "name": clean_text(a.get_text(strip=True)),
                    "link": a["href"]
                })

    # Directors (can be multiple)
    directors = []
    for p in folder.find_all("p"):
        if "🎥" in p.get_text():
            for a in p.find_all("a"):
                directors.append({
                    "name": clean_text(a.get_text(strip=True)),
                    "link": a["href"]
                })

    # Music Directors (can be multiple)
    music_directors = []
    for p in folder.find_all("p"):
        if "🎹" in p.get_text():
            for a in p.find_all("a"):
                music_directors.append({
                    "name": clean_text(a.get_text(strip=True)),
                    "link": a["href"]
                })

    # Songs
    songs = []
    for bg in soup.find_all("div", class_="bg"):
        song_link = bg.find("a", href=lambda x: x and "fid=" in x)
        if not song_link:
            continue

        play_link = bg.find("a", href=lambda x: x and "play=" in x)
        size_tag = bg.find("small")

        song = {
            "song_name": clean_text(song_link.get_text(strip=True)),
            "song_link": song_link["href"],
            "play_link": play_link["href"] if play_link else None,
            "file_size": clean_text(size_tag.get_text(strip=True)) if size_tag else None,
            "singers": []
        }

        singers_div = bg.find("div", class_="singers-info")
        if singers_div:
            for a in singers_div.find_all("a"):
                song["singers"].append({
                    "name": clean_text(a.get_text(strip=True)),
                    "link": a["href"]
                })

        songs.append(song)

    return {
        "album_name": album_name,
        "album_cover": album_cover,
        "year": year,
        "decade": decade,
        "rating": rating,
        "actors": actors,
        "directors": directors,
        "music_directors": music_directors,
        "songs": songs
    }


# ---------------------------------------
# Save Parsed Data to DB
# ---------------------------------------
def save_album_details_to_db(album_id, data):
    conn, cur = get_connection()
    ensure_tables(cur, conn)
    # Update album metadata
    cur.execute("""
        UPDATE albums_list
        SET album_cover=%s, year=%s, decade=%s, rating=%s
        WHERE id=%s
    """, (data["album_cover"], data["year"], data["decade"], data["rating"], album_id))

    # Clear old linked data
    cur.execute("DELETE FROM actors WHERE album_id=%s", (album_id,))
    cur.execute("DELETE FROM directors WHERE album_id=%s", (album_id,))
    cur.execute("DELETE FROM music_directors WHERE album_id=%s", (album_id,))
    cur.execute("DELETE FROM songs WHERE album_id=%s", (album_id,))

    # Insert actors
    for actor in data["actors"]:
        cur.execute("""
            INSERT INTO actors (actor_name, actor_link, album_id)
            VALUES (%s, %s, %s)
        """, (actor["name"], actor["link"], album_id))

    # Insert directors (multiple)
    for director in data["directors"]:
        cur.execute("""
            INSERT INTO directors (director_name, director_link, album_id)
            VALUES (%s, %s, %s)
        """, (director["name"], director["link"], album_id))

    # Insert music directors (multiple)
    for md in data["music_directors"]:
        cur.execute("""
            INSERT INTO music_directors (music_director_name, music_director_link, album_id)
            VALUES (%s, %s, %s)
        """, (md["name"], md["link"], album_id))

    # Insert songs + singers
    for song in data["songs"]:
        cur.execute("""
            INSERT INTO songs (album_id, song_name, song_link, play_link, file_size)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (album_id, song["song_name"], song["song_link"], song["play_link"], song["file_size"]))
        song_id = cur.fetchone()[0]

        for singer in song["singers"]:
            cur.execute("""
                INSERT INTO singers (singer_name, singer_link)
                VALUES (%s, %s)
                ON CONFLICT (singer_name) DO NOTHING
                RETURNING id
            """, (singer["name"], singer["link"]))

            row = cur.fetchone()
            if row:
                singer_id = row[0]
            else:
                cur.execute("SELECT id FROM singers WHERE singer_name=%s", (singer["name"],))
                singer_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO song_singers (song_id, singer_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (song_id, singer_id))

    conn.commit()
    conn.close()


# ---------------------------------------
# FastAPI Route: Crawl Album Details
# ---------------------------------------
@router.get("/crawl/{album_id}")
def crawl_album_details(album_id: int):
    try:

        conn, cur = get_connection()

        # ✅ make sure all dependent tables exist
        ensure_tables(cur, conn)

        cur.execute("SELECT album_link FROM albums_list WHERE id=%s", (album_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return {"error": "Album not found"}

        album_url = urljoin("https://mp3.teluguwap.in/", row[0])
        logger.debug(f"Fetching album details: {album_url}")

        html = requests.get(album_url, timeout=20).text
        data = parse_album_details(html, "https://mp3.teluguwap.in/")
        if data is None:
            conn, cur = get_connection()
            cur.execute("""
                UPDATE albums_list
                SET details_status='skipped', details_updated_at=NOW()
                WHERE id=%s
            """, (album_id,))
            conn.commit()
            conn.close()
            return {"status": "skipped", "reason": "Invalid album details structure"}

        save_album_details_to_db(album_id, data)
        conn, cur = get_connection()
        cur.execute("""
            UPDATE albums_list
            SET details_status='success', details_updated_at=NOW()
            WHERE id=%s
        """, (album_id,))
        conn.commit()
        conn.close()

        return {"status": "success", "album": data["album_name"]}
    except Exception as e:
        conn, cur = get_connection()
        cur.execute("""
            UPDATE albums_list
            SET details_status='error', details_last_error=%s, details_updated_at=NOW()
            WHERE id=%s
        """, (str(e), album_id))
        conn.commit()
        conn.close()
        raise

@router.get("/crawl-bulk")
def crawl_bulk(limit: int = 500):
    conn, cur = get_connection()

    # Fetch next 500 pending or error albums
    cur.execute("""
        SELECT id, album_link
        FROM albums_list
        WHERE details_status IN ('pending', 'error')
        ORDER BY id
        LIMIT %s
    """, (limit,))

    albums = cur.fetchall()
    conn.close()

    results = []

    for album_id, album_link in albums:
        try:
            result = crawl_album_details(album_id)
            results.append({"album_id": album_id, "result": result})
        except Exception as e:
            results.append({"album_id": album_id, "result": str(e)})

    return {
        "processed": len(results),
        "results": results
    }

