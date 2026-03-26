import re
import psycopg2
import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter
from db.db import POSTGRESQL_DATABASE_URL_TELUGUWAP

router = APIRouter(prefix="/hindiflacs-song-details", tags=["hindiflacs-song-details"])


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
        url.replace("https://hindiflacs.com", "")
           .replace("http://hindiflacs.com", "")
           .replace("https://i.hindiflacs.com", "")
    )


# ---------------------------------------------------------
# PARSE SONG DETAILS PAGE
# ---------------------------------------------------------
def parse_song_details(song_link):
    url = "https://hindiflacs.com" + song_link

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

    # -----------------------------------------------------
    # COMPOSER (robust detection)
    # -----------------------------------------------------
    composer = None

    # 1) Try strong-tag version first
    comp_tag = soup.find("strong", string=re.compile(r"Composer", re.I))
    if comp_tag:
        next_a = comp_tag.find_next("a")
        if next_a:
            composer = clean(next_a.get_text())
        else:
            # text after strong tag
            composer = clean(comp_tag.next_sibling)
    else:
        # 2) Fallback: search raw text "Composer:"
        text_node = soup.find(string=re.compile(r"Composer\s*:", re.I))
        if text_node:
            # Extract text after "Composer:"
            after = re.split(r"Composer\s*:\s*", text_node, flags=re.I)
            if len(after) > 1:
                composer = clean(after[1])
            else:
                # maybe composer is in next <a>
                parent = text_node.parent
                next_a = parent.find("a")
                if next_a:
                    composer = clean(next_a.get_text())

    # -----------------------------------------------------
    # DOWNLOAD OPTIONS
    # -----------------------------------------------------
    downloads = {
        "original": {"link": None, "text": None, "size": None},
        "128": {"link": None, "text": None, "size": None},
        "320": {"link": None, "text": None, "size": None},
    }

    bg = None
    for div in soup.find_all("div", class_="bg"):
        h2 = div.find("h2")
        if h2 and "Download Options" in h2.get_text():
            bg = div
            break

    if not bg:
        return {"composer": composer, "downloads": downloads}

    forms = bg.find_all("form")

    index = 0
    for form in forms:
        hidden = {inp.get("name"): inp.get("value") for inp in form.find_all("input")}

        type_ = hidden.get("type")
        q = hidden.get("q")
        ext = hidden.get("ext")
        qlty = hidden.get("qlty")

        if not (type_ and q and ext and qlty):
            continue

        # Construct URL (NO base URL)
        download_url = f"files.php?type={type_}&q={q}&ext={ext}&qlty={qlty}"

        # Button text
        btn = form.find("button")
        text = clean(btn.get_text()) if btn else None

        # Size (text after </button>)
        size_match = re.search(r"\((.*?)\)", form.decode())
        size = clean(size_match.group(1)) if size_match else None

        # Map to DB fields
        if index == 0:
            # ORIGINAL
            downloads["original"] = {
                "link": download_url,
                "text": text,
                "size": size
            }
        else:
            if ext == "mp3" and "128" in qlty:
                downloads["128"] = {
                    "link": download_url,
                    "text": text,
                    "size": size
                }
            if ext == "mp3" and "320" in qlty:
                downloads["320"] = {
                    "link": download_url,
                    "text": text,
                    "size": size
                }

        index += 1

    return {
        "composer": composer,
        "downloads": downloads
    }


# ---------------------------------------------------------
# PROCESS ONE SONG
# ---------------------------------------------------------
def process_song(song_id, song_link):
    conn, cur = get_connection()

    try:
        details = parse_song_details(song_link)
        if not details:
            raise Exception("Parsing failed")

        d = details["downloads"]

        cur.execute("""
            UPDATE hindiflacs_songs
            SET 
                composer=%s,
                download_link_original=%s,
                download_text_original=%s,
                download_size_original=%s,

                download_link_128kbps=%s,
                download_text_128kbps=%s,
                download_size_128kbps=%s,

                download_link_320kbps=%s,
                download_text_320kbps=%s,
                download_size_320kbps=%s,

                details_status='completed',
                details_updated_at=NOW()
            WHERE id=%s
        """, (
            details["composer"],

            d["original"]["link"],
            d["original"]["text"],
            d["original"]["size"],

            d["128"]["link"],
            d["128"]["text"],
            d["128"]["size"],

            d["320"]["link"],
            d["320"]["text"],
            d["320"]["size"],

            song_id
        ))

        conn.commit()
        conn.close()
        return {"status": "success", "song_id": song_id}

    except Exception as e:
        conn.rollback()
        cur.execute("""
            UPDATE hindiflacs_songs
            SET details_status='failed', details_last_error=%s, details_updated_at=NOW()
            WHERE id=%s
        """, (str(e), song_id))
        conn.commit()
        conn.close()
        return {"status": "error", "song_id": song_id, "error": str(e)}


# ---------------------------------------------------------
# BULK PROCESSOR
# ---------------------------------------------------------
def process_pending_songs(limit=50):
    conn, cur = get_connection()

    cur.execute("""
        SELECT id, song_link
        FROM hindiflacs_songs
        WHERE details_status='pending'
        ORDER BY id
        LIMIT %s
        FOR UPDATE SKIP LOCKED
    """, (limit,))

    rows = cur.fetchall()

    if rows:
        picked_ids = [r[0] for r in rows]
        cur.execute(
            "UPDATE hindiflacs_songs SET details_status='in_progress' WHERE id = ANY(%s)",
            (picked_ids,)
        )
        conn.commit()

    conn.close()

    results = []
    for song_id, song_link in rows:
        results.append(process_song(song_id, song_link))

    return {
        "status": "success",
        "processed": len(results),
        "results": results
    }


# ---------------------------------------------------------
# FASTAPI ROUTES
# ---------------------------------------------------------
@router.get("/process-one/{song_id}")
def process_one(song_id: int):
    conn, cur = get_connection()
    cur.execute("SELECT song_link FROM hindiflacs_songs WHERE id=%s", (song_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {"status": "error", "message": "Song not found"}

    return process_song(song_id, row[0])


@router.get("/process-all")
def process_all(limit: int = 50):
    return process_pending_songs(limit)
