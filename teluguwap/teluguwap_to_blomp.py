import gc
import re
import time
import psycopg2
import os
import hashlib
import requests
from io import BytesIO
from urllib.parse import urlparse

import swiftclient
from bs4 import BeautifulSoup
from fastapi import APIRouter, Query
from db.db import POSTGRESQL_DATABASE_URL_TELUGUWAP, BLOMP_USER, BLOMP_PASS

router = APIRouter(prefix="/song-download", tags=["song-download"])

# ─────────────────────────────────────────────
# Blomp Swift Notes:
#   - Auth URL  : https://authenticate.blomp.com/v3
#   - Public endpoint: http://swiftproxy.acs.ai.net:8080/v1/AUTH_<project_id>
#   - Container : YOUR EMAIL ADDRESS (e.g. govardhanarao.s@gmail.com)
#   - Folder    : use object path prefix  →  teluguwap_songs/<filename>
# ─────────────────────────────────────────────

def get_db_connection():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL_TELUGUWAP)
    return conn, conn.cursor()


def calculate_md5(file_bytes):
    return hashlib.md5(file_bytes).hexdigest()


def clean(text):
    if not text:
        return None
    text = text.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip()


# ─────────────────────────────────────────────
# BLOMP UPLOAD  (Swift — direct requests PUT)
# ─────────────────────────────────────────────

def get_blomp_auth():
    """
    Authenticates with Blomp and returns (storage_url, token).
    Uses swiftclient only for auth — actual uploads go via raw requests.PUT
    so we have full control over headers and avoid swiftclient bugs.
    """
    conn = swiftclient.Connection(
        authurl="https://authenticate.blomp.com/v3",
        user=BLOMP_USER,
        key=BLOMP_PASS,
        os_options={
            'project_name': 'storage',
            'user_domain_name': 'Default',
            'project_domain_name': 'Default',
            'endpoint_type': 'publicURL'
        },
        auth_version="3",
        insecure=True
    )
    storage_url, token = conn.get_auth()
    print(f"DEBUG: Raw storage_url from catalog = {storage_url}")
    return storage_url, token


def upload_to_blomp_swift(song_id, quality, original_filename, file_bytes):
    """
    Uploads a file to Blomp via raw HTTP PUT (bypasses swiftclient bugs).

    Blomp's Swift container IS your email address.
    'teluguwap_songs' is just a path prefix (pseudo-folder) inside it.

    Final object path:  <email>/teluguwap_songs/<song_id>_<name>_<quality><ext>
    """
    if not file_bytes:
        raise Exception(f"file_bytes is empty for song_id={song_id}, quality={quality}")

    file_hash = calculate_md5(file_bytes)

    name_only = os.path.splitext(original_filename)[0]
    ext = os.path.splitext(original_filename)[1] or ".mp3"
    unique_filename = f"{song_id}_{name_only}_{quality}{ext}"

    # ── Container = your Blomp email ──────────────────────────────────────
    container = BLOMP_USER          # e.g. "govardhanarao.s@gmail.com"
    obj_path  = f"teluguwap_songs/{unique_filename}"

    storage_url, token = get_blomp_auth()

    # Build the full PUT URL
    # storage_url already ends with /AUTH_<id>, e.g.:
    #   http://swiftproxy.acs.ai.net:8080/v1/AUTH_8b989f118e624ca6957e102775583f6f
    put_url = f"{storage_url}/{container}/{obj_path}"
    print(f"DEBUG: PUT → {put_url}  ({len(file_bytes)} bytes)")

    headers = {
        "X-Auth-Token": token,
        "Content-Type": "audio/mpeg",
        "Content-Length": str(len(file_bytes)),
    }

    resp = requests.put(
        put_url,
        data=file_bytes,
        headers=headers,
        timeout=120,
        verify=False   # swiftproxy uses self-signed cert
    )

    print(f"DEBUG: Response {resp.status_code} — {resp.text[:200]}")

    if resp.status_code in (201, 200):
        blomp_path = f"{container}/{obj_path}"
        print(f"SUCCESS: Uploaded → {blomp_path}")
        return blomp_path, file_hash

    # ── Friendly error messages ───────────────────────────────────────────
    if resp.status_code == 403:
        raise Exception(
            f"403 Forbidden — most likely causes:\n"
            f"  1. Container '{container}' does not exist on Blomp yet.\n"
            f"     → Log into blomp.com and create a container named exactly: {container}\n"
            f"  2. Token scope mismatch — try logging out & back into Blomp.\n"
            f"  Raw response: {resp.text[:300]}"
        )
    if resp.status_code == 404:
        raise Exception(
            f"404 Not Found — container '{container}' not found at {storage_url}.\n"
            f"  Raw response: {resp.text[:300]}"
        )

    raise Exception(f"Upload failed: HTTP {resp.status_code} — {resp.text[:300]}")


# ─────────────────────────────────────────────
# TELUGUWAP DOWNLOAD
# ─────────────────────────────────────────────

def download_song_from_source(download_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://teluguwap.in/",
        "Connection": "keep-alive",
    }
    session = requests.Session()

    try:
        session.get("https://teluguwap.in/", headers=headers, timeout=15, verify=False)
        print("DEBUG: Session cookies acquired")
    except Exception as e:
        print(f"DEBUG: Could not pre-fetch homepage: {e}")

    resp = session.get(download_url, headers=headers, allow_redirects=True, timeout=60, verify=False)

    print(f"DEBUG: Status={resp.status_code}, Content-Type={resp.headers.get('Content-Type')}, "
          f"Length={len(resp.content)} bytes, Final URL={resp.url}")

    # Expired one-time token
    if len(resp.content) <= 2 and resp.text.strip() in (";", ""):
        raise Exception("Expired one-time token — re-scrape the song page for a fresh link.")

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" in content_type:
        raise Exception(f"Server returned HTML instead of audio. Body: {resp.text[:300]}")

    if resp.status_code != 200:
        raise Exception(f"Source download failed: {resp.status_code}")

    file_bytes = resp.content
    if not file_bytes:
        raise Exception(f"Downloaded file is empty from: {download_url}")

    filename = os.path.basename(urlparse(resp.url).path)
    if not filename or not filename.endswith(('.mp3', '.m4a', '.flac')):
        filename = f"song_{int(time.time())}.mp3"

    print(f"DEBUG: Filename={filename}, Size={len(file_bytes)} bytes")
    return filename, file_bytes


def parse_song_details(song_link):
    """Scrapes a teluguwap song page and returns FRESH one-time download URLs."""
    url = "https://teluguwap.in" + song_link

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

    downloads = {
        "original": {"link": None, "text": None, "size": None},
        "128":      {"link": None, "text": None, "size": None},
        "320":      {"link": None, "text": None, "size": None},
    }

    bg = None
    for div in soup.find_all("div", class_="bg"):
        h2 = div.find("h2")
        if h2 and "Download Options" in h2.get_text():
            bg = div
            break

    if not bg:
        return {"downloads": downloads}

    forms = bg.find_all("form")
    index = 0
    for form in forms:
        hidden = {inp.get("name"): inp.get("value") for inp in form.find_all("input")}
        type_ = hidden.get("type")
        q     = hidden.get("q")
        ext   = hidden.get("ext")
        qlty  = hidden.get("qlty")

        if not (type_ and q and ext and qlty):
            continue

        download_url = f"files.php?type={type_}&q={q}&ext={ext}&qlty={qlty}"
        btn  = form.find("button")
        text = clean(btn.get_text()) if btn else None
        size_match = re.search(r"\((.*?)\)", form.decode())
        size = clean(size_match.group(1)) if size_match else None

        if index == 0:
            downloads["original"] = {"link": download_url, "text": text, "size": size}
        else:
            if ext == "mp3" and "128" in qlty:
                downloads["128"] = {"link": download_url, "text": text, "size": size}
            if ext == "mp3" and "320" in qlty:
                downloads["320"] = {"link": download_url, "text": text, "size": size}
        index += 1

    return {"downloads": downloads}


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────

@router.get("/test-upload-local")
def test_upload_local(
    file_path: str = Query(..., description="Full path to local file"),
    song_id:   int = Query(999999, description="Dummy song ID"),
    quality:   str = Query("test", description="Quality label")
):
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        filename = os.path.basename(file_path)
        blomp_path, file_hash = upload_to_blomp_swift(
            song_id=song_id,
            quality=quality,
            original_filename=filename,
            file_bytes=file_bytes
        )
        return {
            "status": "success",
            "uploaded_to": blomp_path,
            "md5_hash": file_hash,
            "size_bytes": len(file_bytes)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/get-128kbps/{song_id}")
def get_128kbps_link(song_id: int):
    conn, cur = get_db_connection()
    try:
        cur.execute(
            "SELECT download_link_128kbps, song_name, song_link FROM teluguwap_songs WHERE id=%s",
            (song_id,)
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return {"status": "error", "message": "Song link not found"}

        # Always scrape a fresh token — stored links are one-time use
        details   = parse_song_details(row[2])
        fresh_url = "https://teluguwap.in/" + details["downloads"]["128"]["link"]

        filename, file_bytes = download_song_from_source(fresh_url)
        path, b_hash = upload_to_blomp_swift(song_id, "128kbps", filename, file_bytes)

        return {"status": "success", "blomp_path": path, "hash": b_hash}
    finally:
        cur.close()
        conn.close()


@router.get("/process-pending-uploads")
def process_pending_uploads(limit: int = Query(10)):
    """Batch processes songs with 'blomp_pending' status."""
    conn, cur = get_db_connection()
    results = []
    try:
        # Use SELECT FOR UPDATE SKIP LOCKED so concurrent triggers never pick the same rows
        cur.execute("""
            SELECT id, song_name, download_link_original, download_link_128kbps,
                   download_link_320kbps, song_link
            FROM teluguwap_songs
            WHERE details_status = 'blomp_pending'
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        """, (limit,))
        pending_songs = cur.fetchall()

        if not pending_songs:
            return {"status": "batch_processed", "processed": []}

        # Mark ALL picked rows as 'blomp_picked' immediately so other
        # concurrent triggers won't select the same songs
        picked_ids = [row[0] for row in pending_songs]
        cur.execute(
            "UPDATE teluguwap_songs SET details_status='blomp_picked' WHERE id = ANY(%s)",
            (picked_ids,)
        )
        conn.commit()
        print(f"DEBUG: Marked {len(picked_ids)} songs as blomp_picked: {picked_ids}")

        for s_id, s_name, link_orig, link_128, link_320, song_link_from_db in pending_songs:

            # Scrape fresh one-time tokens ONCE per song
            try:
                details     = parse_song_details(song_link_from_db)
                fresh_links = details["downloads"]
            except Exception as e:
                print(f"Failed to scrape fresh links for song {s_id}: {e}")
                cur.execute(
                    "UPDATE teluguwap_songs SET details_status='blomp_scrape_failed' WHERE id=%s",
                    (s_id,)
                )
                conn.commit()
                results.append({"id": s_id, "status": "blomp_scrape_failed"})
                continue

            quality_work = [
                ("original", link_orig, fresh_links.get("original"), "blomp_path_original", "blomp_hash_original"),
                ("128kbps",  link_128,  fresh_links.get("128"),      "blomp_path_128kbps",  "blomp_hash_128kbps"),
                ("320kbps",  link_320,  fresh_links.get("320"),      "blomp_path_320kbps",  "blomp_hash_320kbps"),
            ]

            song_success = True
            for q_name, q_link_db, fresh_entry, path_col, hash_col in quality_work:
                if not q_link_db:
                    continue   # no link stored for this quality — skip

                fbytes = None
                try:
                    if not fresh_entry or not fresh_entry.get("link"):
                        raise Exception(f"No fresh link found for quality '{q_name}'")

                    fresh_url = "https://teluguwap.in/" + fresh_entry["link"]
                    fname, fbytes = download_song_from_source(fresh_url)
                    b_path, b_hash = upload_to_blomp_swift(s_id, q_name, fname, fbytes)

                    cur.execute(
                        f"UPDATE teluguwap_songs SET {path_col}=%s, {hash_col}=%s WHERE id=%s",
                        (b_path, b_hash, s_id)
                    )
                    conn.commit()
                    print(f"OK  {q_name} for song {s_id} → {b_path}")

                except Exception as e:
                    print(f"FAIL {q_name} for song {s_id}: {e}")
                    song_success = False

                finally:  # ← ADD
                    del fbytes  # ← ADD  free audio bytes immediately
                    gc.collect()
            new_status = "blomp_completed" if song_success else "blomp_partial_failed"
            cur.execute(
                "UPDATE teluguwap_songs SET details_status=%s WHERE id=%s",
                (new_status, s_id)
            )
            conn.commit()
            results.append({"id": s_id, "status": new_status})

        return {"status": "batch_processed", "processed": results}
    finally:
        cur.close()
        conn.close()
