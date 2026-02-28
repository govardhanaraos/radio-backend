import re
import psycopg2
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from fastapi import APIRouter
from db.db import POSTGRESQL_DATABASE_URL_TELUGUWAP

router = APIRouter(prefix="/teluguwap-album-details", tags=["teluguwap-album-details"])


# ---------------------------------------------------------
# DB CONNECTION
# ---------------------------------------------------------
def get_connection():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL_TELUGUWAP)
    return conn, conn.cursor()


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def clean(text):
    if not text:
        return None
    text = text.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip()


def normalize(url):
    if not url:
        return url
    return (
        url.replace("https://teluguwap.in", "")
           .replace("http://i.teluguwap.in", "")
           .replace("https://i.teluguwap.in", "")
    )


# ---------------------------------------------------------
# INSERT / UPSERT HELPERS
# ---------------------------------------------------------
def upsert_actor(cur, conn, name, link, album_id):
    cur.execute("""
        INSERT INTO teluguwap_actors (actor_name, actor_link, album_id)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (name, link, album_id))
    conn.commit()


def upsert_director(cur, conn, name, link, album_id):
    cur.execute("""
        INSERT INTO teluguwap_directors (director_name, director_link, album_id)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (name, link, album_id))
    conn.commit()


def upsert_music_director(cur, conn, name, link, album_id):
    cur.execute("""
        INSERT INTO teluguwap_music_directors (music_director_name, music_director_link, album_id)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (name, link, album_id))
    conn.commit()


def upsert_singer(cur, conn, name, link):
    cur.execute("""
        INSERT INTO teluguwap_singers (singer_name, singer_link)
        VALUES (%s, %s)
        ON CONFLICT (singer_name) DO NOTHING
        RETURNING id
    """, (name, link))

    row = cur.fetchone()
    if row:
        conn.commit()
        return row[0]

    # fetch existing
    cur.execute("SELECT id FROM teluguwap_singers WHERE singer_name=%s", (name,))
    row = cur.fetchone()
    return row[0] if row else None


def insert_song(cur, conn, album_id, song):
    cur.execute("""
        INSERT INTO teluguwap_songs (
            album_id, song_name, song_link, play_link,
            duration, teluguwap_singers
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (song_link)
        DO UPDATE SET
            song_name = EXCLUDED.song_name,
            play_link = EXCLUDED.play_link,
            duration = EXCLUDED.duration,
            teluguwap_singers = EXCLUDED.teluguwap_singers
        RETURNING id
    """, (
        album_id,
        song["name"],
        song["song_link"],
        song["play_link"],
        song["duration"],
        ", ".join(song["singers"])
    ))

    row = cur.fetchone()
    conn.commit()
    return row[0]


def link_song_singers(cur, conn, song_id, singer_ids):
    for sid in singer_ids:
        cur.execute("""
            INSERT INTO teluguwap_song_singers (song_id, singer_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (song_id, sid))
    conn.commit()


# ---------------------------------------------------------
# PARSE ALBUM DETAILS PAGE
# ---------------------------------------------------------
def parse_album_details(album_link):
    url = "https://teluguwap.in" + album_link

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; SM-G975F) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        )
    }

    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # -------------------------------
    # ALBUM METADATA
    # -------------------------------
    meta = soup.find("div", class_="bg")
    if not meta:
        return None

    # Title
    title = None
    title_tag = meta.find("strong", string=re.compile("Title"))
    if title_tag:
        title = clean(title_tag.next_sibling)

    # Year
    year = None
    year_tag = meta.find("strong", string=re.compile("Released Year"))
    if year_tag:
        y = year_tag.find_next("a")
        if y:
            year = int(y.get_text(strip=True)[:4])

    # Cast
    cast = []
    cast_tag = meta.find("strong", string=re.compile("Cast"))
    if cast_tag:
        # iterate siblings until next <strong> tag
        for sib in cast_tag.next_siblings:
            if getattr(sib, "name", None) == "strong":
                break  # reached Director, stop

            if getattr(sib, "name", None) == "a":
                cast.append((clean(sib.get_text()), normalize(sib["href"])))

    director = None
    director_link = None
    d_tag = meta.find("strong", string=re.compile("Director"))
    if d_tag:
        a = d_tag.find_next("a")
        if a:
            director = clean(a.get_text())
            director_link = normalize(a["href"])

    # Music Director
    music = None
    music_link = None
    m_tag = meta.find("strong", string=re.compile("Music"))
    if m_tag:
        a = m_tag.find_next("a")
        if a:
            music = clean(a.get_text())
            music_link = normalize(a["href"])

    # Rating
    rating = None
    r_tag = meta.find("strong", string=re.compile("Rating"))
    if r_tag:
        rating = clean(r_tag.next_sibling)

    # -------------------------------
    # SONG LIST
    # -------------------------------
    songs = []
    grid = soup.find("div", class_="related-albums-grid")
    if grid:
        cards = grid.find_all("div", class_="related-album-card")

        for card in cards:
            td = card.find("td")
            if not td:
                continue

            # Play link
            play_btn = td.find("a", class_="sm2_button")
            play_link = normalize(play_btn["href"]) if play_btn else None

            # Song link + name
            a_song = td.find_all("a")[1]
            song_link = normalize(a_song["href"])
            song_name = clean(a_song.get_text(strip=True))

            # Duration
            small = td.find("small")
            duration = clean(small.get_text(strip=True)) if small else None

            # Singers
            singers = []
            singer_links = []
            for a in td.find_all("a")[2:]:
                singers.append(clean(a.get_text()))
                singer_links.append(normalize(a["href"]))

            songs.append({
                "name": song_name,
                "song_link": song_link,
                "play_link": play_link,
                "duration": duration,
                "singers": singers,
                "singer_links": singer_links
            })

    return {
        "title": title,
        "year": year,
        "cast": cast,
        "director": (director, director_link),
        "music": (music, music_link),
        "rating": rating,
        "songs": songs
    }


# ---------------------------------------------------------
# PROCESS ONE ALBUM
# ---------------------------------------------------------
def process_album(album_id, album_link):
    conn, cur = get_connection()

    try:
        details = parse_album_details(album_link)
        if not details:
            raise Exception("Parsing failed")

        # Update album metadata
        cur.execute("""
            UPDATE teluguwap_albums_list
            SET year=%s, rating=%s, details_status='completed', details_updated_at=NOW()
            WHERE id=%s
        """, (details["year"], details["rating"], album_id))
        conn.commit()

        # Insert cast
        for name, link in details["cast"]:
            upsert_actor(cur, conn, name, link, album_id)

        # Insert director
        d_name, d_link = details["director"]
        if d_name:
            upsert_director(cur, conn, d_name, d_link, album_id)

        # Insert music director
        m_name, m_link = details["music"]
        if m_name:
            upsert_music_director(cur, conn, m_name, m_link, album_id)

        # Insert songs + singers
        for song in details["songs"]:
            song_id = insert_song(cur, conn, album_id, song)

            singer_ids = []
            for name, link in zip(song["singers"], song["singer_links"]):
                sid = upsert_singer(cur, conn, name, link)
                if sid:
                    singer_ids.append(sid)

            link_song_singers(cur, conn, song_id, singer_ids)

        conn.close()
        return {"status": "success", "album_id": album_id}

    except Exception as e:
        # IMPORTANT: rollback first
        conn.rollback()
        cur.execute("""
            UPDATE teluguwap_albums_list
            SET details_status='failed', details_last_error=%s, details_updated_at=NOW()
            WHERE id=%s
        """, (str(e), album_id))
        conn.commit()
        conn.close()
        return {"status": "error", "album_id": album_id, "error": str(e)}

# ---------------------------------------------------------
# BULK PROCESSOR
# ---------------------------------------------------------
def process_pending_albums(limit=50):
    conn, cur = get_connection()

    cur.execute("""
        SELECT id, album_link
        FROM teluguwap_albums_list
        WHERE details_status='pending'
        ORDER BY id
        LIMIT %s
    """, (limit,))

    rows = cur.fetchall()
    conn.close()

    results = []
    for album_id, album_link in rows:
        result = process_album(album_id, album_link)
        results.append(result)

    return {
        "status": "success",
        "processed": len(results),
        "results": results
    }


# ---------------------------------------------------------
# FASTAPI ROUTES
# ---------------------------------------------------------
@router.get("/process-one/{album_id}")
def process_one(album_id: int):
    conn, cur = get_connection()
    cur.execute("SELECT album_link FROM teluguwap_albums_list WHERE id=%s", (album_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {"status": "error", "message": "Album not found"}

    return process_album(album_id, row[0])


@router.get("/process-all")
def process_all(limit: int = 50):
    return process_pending_albums(limit)