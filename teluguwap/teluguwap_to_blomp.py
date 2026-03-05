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

import logging

router = APIRouter(prefix="/song-download", tags=["song-download"])

logging.getLogger("keystoneclient").setLevel(logging.WARNING)

# ─────────────────────────────────────────────
# Blomp Swift Notes:
#   - Auth URL  : https://authenticate.blomp.com/v3
#   - Public endpoint: http://swiftproxy.acs.ai.net:8080/v1/AUTH_<project_id>
#   - Container : YOUR EMAIL ADDRESS (e.g. govardhanarao.s@gmail.com)
#   - Folder    : use object path prefix  →  teluguwap_songs/<filename>
#
# Memory budget on Render free (512MB total, 1 worker):
#   ~120MB  app base
#   ~15MB   one MP3 in BytesIO (peak, freed immediately after PUT)
#   ~5MB    overhead
#   ─────────────────
#   ~140MB peak — well within 512MB with 1 worker
# ─────────────────────────────────────────────

CHUNK_SIZE = 256 * 1024   # 256 KB read/write chunks


def get_db_connection():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL_TELUGUWAP)
    return conn, conn.cursor()


def clean(text):
    if not text:
        return None
    text = text.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip()


# ─────────────────────────────────────────────
# BLOMP AUTH
# ─────────────────────────────────────────────

def get_blomp_auth():
    """
    Returns (storage_url, token).
    FIX: Called ONCE per batch — not once per quality upload.
    swiftclient Connection is explicitly closed after auth to free its HTTP adapter.
    """
    swift_conn = swiftclient.Connection(
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
    storage_url, token = swift_conn.get_auth()
    try:
        swift_conn.close()
    except Exception:
        pass
    del swift_conn
    print(f"DEBUG: storage_url={storage_url}")
    return storage_url, token


# ─────────────────────────────────────────────
# CORE: stream download → BytesIO → PUT
#
# FIX for memory issue:
#   OLD: resp.content loads entire MP3 at once → 2-3 copies live in RAM
#        (resp internal buffer + file_bytes + fbytes caller ref = ~45MB for 15MB file)
#
#   NEW: stream=True + iter_content(256KB) → single BytesIO buffer (~15MB max)
#        MD5 computed on the fly — no second pass
#        BytesIO closed + deleted immediately after PUT
#        gc.collect() after every quality
# ─────────────────────────────────────────────

def _process_one_quality(s_id, q_name, fresh_url, storage_url, token):
    """
    Streams audio from fresh_url, buffers in BytesIO, PUTs to Blomp.
    Buffer freed immediately after upload regardless of success/failure.
    Returns (blomp_path, file_hash).
    """
    dl_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://teluguwap.in/",
        "Accept": "*/*",
        "Connection": "keep-alive",
    }

    session = requests.Session()
    try:
        session.get("https://teluguwap.in/", headers=dl_headers, timeout=15, verify=False)
    except Exception:
        pass  # cookie pre-fetch is best-effort

    # ── Stream download ───────────────────────────────────────────────────
    resp = session.get(
        fresh_url,
        headers=dl_headers,
        stream=True,            # ← do NOT buffer entire body in requests
        allow_redirects=True,
        timeout=90,
        verify=False
    )

    content_type = resp.headers.get("Content-Type", "")
    print(f"DEBUG: DL status={resp.status_code}, "
          f"Content-Type={content_type}, "
          f"Content-Length={resp.headers.get('Content-Length', '?')}")

    if resp.status_code != 200:
        resp.close()
        session.close()
        raise Exception(f"Source download failed: HTTP {resp.status_code}")

    if "text/html" in content_type:
        snippet = next(resp.iter_content(256), b"")
        resp.close()
        session.close()
        raise Exception(f"Got HTML instead of audio — expired token. Snippet: {snippet[:80]}")

    filename = os.path.basename(urlparse(resp.url).path)
    if not filename or not filename.endswith(('.mp3', '.m4a', '.flac')):
        filename = f"song_{s_id}_{q_name}_{int(time.time())}.mp3"

    # ── Buffer into BytesIO, hash on the fly ─────────────────────────────
    buf   = BytesIO()
    md5   = hashlib.md5()
    total = 0
    try:
        for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                buf.write(chunk)
                md5.update(chunk)
                total += len(chunk)
    finally:
        resp.close()
        session.close()

    if total <= 2:
        buf.close()
        raise Exception("Expired one-time token — response was empty/minimal.")

    file_hash = md5.hexdigest()
    buf.seek(0)   # rewind for PUT

    # ── PUT to Blomp with exact Content-Length ────────────────────────────
    # (old OpenStack Swift rejects chunked Transfer-Encoding → ConnectionAbortedError 10053)
    name_only     = os.path.splitext(filename)[0]
    ext           = os.path.splitext(filename)[1] or ".mp3"
    stored_name   = f"{s_id}_{name_only}_{q_name}{ext}"   # e.g. 3163_04_-_Nuvvante_Nenani_original.m4a
    full_obj_path = f"teluguwap_songs/{stored_name}"
    container     = BLOMP_USER
    put_url       = f"{storage_url}/{container}/{full_obj_path}"

    print(f"DEBUG: PUT {put_url}  ({total} bytes)")

    try:
        put_resp = requests.put(
            put_url,
            data=buf,
            headers={
                "X-Auth-Token": token,
                "Content-Type": "audio/mpeg",
                "Content-Length": str(total),   # exact size — no chunked encoding
            },
            timeout=300,
            verify=False
        )
    finally:
        buf.close()   # ← always free BytesIO even if PUT raises
        del buf

    print(f"DEBUG: PUT status={put_resp.status_code}")

    if put_resp.status_code not in (200, 201):
        if put_resp.status_code == 403:
            raise Exception(
                f"403 Forbidden — container '{container}' missing or token invalid.\n"
                f"Raw: {put_resp.text[:300]}"
            )
        raise Exception(
            f"Blomp PUT failed: HTTP {put_resp.status_code} — {put_resp.text[:200]}"
        )

    # Store only the unique filename — caller prepends container/folder prefix
    print(f"SUCCESS {q_name} song {s_id}: {stored_name}")
    return stored_name, file_hash


# ─────────────────────────────────────────────
# TELUGUWAP SCRAPER
# ─────────────────────────────────────────────

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
    resp.close()   # free response body once parsed into soup

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
        del soup
        return {"downloads": downloads}

    index = 0
    for form in bg.find_all("form"):
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

    del soup, bg
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
        storage_url, token = get_blomp_auth()
        file_size = os.path.getsize(file_path)
        md5 = hashlib.md5()
        filename  = os.path.basename(file_path)
        name_only = os.path.splitext(filename)[0]
        ext       = os.path.splitext(filename)[1] or ".mp3"
        obj_path  = f"teluguwap_songs/{song_id}_{name_only}_{quality}{ext}"
        put_url   = f"{storage_url}/{BLOMP_USER}/{obj_path}"

        buf = BytesIO()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                md5.update(chunk)
                buf.write(chunk)
        buf.seek(0)

        try:
            resp = requests.put(
                put_url,
                data=buf,
                headers={
                    "X-Auth-Token": token,
                    "Content-Type": "audio/mpeg",
                    "Content-Length": str(file_size),
                },
                timeout=300,
                verify=False
            )
        finally:
            buf.close()
            del buf

        if resp.status_code not in (200, 201):
            return {"status": "error", "message": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        return {
            "status": "success",
            "uploaded_to": f"{BLOMP_USER}/{obj_path}",
            "md5_hash": md5.hexdigest(),
            "size_bytes": file_size
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        gc.collect()


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

        details   = parse_song_details(row[2])
        fresh_url = "https://teluguwap.in/" + details["downloads"]["128"]["link"]
        del details

        storage_url, token = get_blomp_auth()
        path, b_hash = _process_one_quality(song_id, "128kbps", fresh_url, storage_url, token)
        return {"status": "success", "blomp_path": path, "hash": b_hash}
    finally:
        cur.close()
        conn.close()
        gc.collect()


@router.get("/process-pending-uploads")
def process_pending_uploads(limit: int = Query(2)):
    """
    Batch processes songs with 'blomp_pending' status.

    RENDER FREE TIER SETTINGS:
      limit=2   (safe default — ~45MB peak per request with 3 qualities × 15MB)
      1 worker  (see gunicorn start command below)

    GUNICORN START COMMAND for render.yaml / start command:
      gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT --timeout 300
                        ─────────── ← was 4, now 1 — saves ~300MB RAM at startup
    """
    conn, cur = get_db_connection()
    results = []
    try:
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

        picked_ids = [row[0] for row in pending_songs]
        cur.execute(
            "UPDATE teluguwap_songs SET details_status='blomp_picked' WHERE id = ANY(%s)",
            (picked_ids,)
        )
        conn.commit()
        print(f"DEBUG: Picked {len(picked_ids)} songs: {picked_ids}")

        # ── FIX: auth ONCE per batch (not once per quality = not 6x per song) ──
        storage_url, token = get_blomp_auth()

        for s_id, s_name, link_orig, link_128, link_320, song_link_from_db in pending_songs:

            try:
                details     = parse_song_details(song_link_from_db)
                fresh_links = details["downloads"]
                del details
            except Exception as e:
                print(f"Scrape failed song {s_id}: {e}")
                cur.execute(
                    "UPDATE teluguwap_songs SET details_status='blomp_scrape_failed', details_updated_at=NOW() WHERE id=%s",
                    (s_id,)
                )
                conn.commit()
                results.append({"id": s_id, "status": "blomp_scrape_failed"})
                gc.collect()
                continue

            quality_work = [
                ("original", link_orig, fresh_links.get("original"), "blomp_path_original", "blomp_hash_original"),
                ("128kbps",  link_128,  fresh_links.get("128"),      "blomp_path_128kbps",  "blomp_hash_128kbps"),
                ("320kbps",  link_320,  fresh_links.get("320"),      "blomp_path_320kbps",  "blomp_hash_320kbps"),
            ]
            del fresh_links

            song_success = True
            for q_name, q_link_db, fresh_entry, path_col, hash_col in quality_work:
                if not q_link_db:
                    continue

                try:
                    if not fresh_entry or not fresh_entry.get("link"):
                        raise Exception(f"No fresh link for '{q_name}'")

                    fresh_url = "https://teluguwap.in/" + fresh_entry["link"]

                    # stream download + PUT — peak RAM = 1 file at a time
                    b_path, b_hash = _process_one_quality(
                        s_id, q_name, fresh_url, storage_url, token
                    )

                    cur.execute(
                        f"UPDATE teluguwap_songs SET {path_col}=%s, {hash_col}=%s, details_updated_at=NOW() WHERE id=%s",
                        (b_path, b_hash, s_id)
                    )
                    conn.commit()
                    print(f"OK  {q_name} song {s_id} → {b_path}")

                except Exception as e:
                    print(f"FAIL {q_name} song {s_id}: {e}")
                    song_success = False

                finally:
                    gc.collect()   # after every quality

            new_status = "blomp_completed" if song_success else "blomp_partial_failed"
            cur.execute(
                "UPDATE teluguwap_songs SET details_status=%s, details_updated_at=NOW() WHERE id=%s",
                (new_status, s_id)
            )
            conn.commit()
            results.append({"id": s_id, "status": new_status})
            gc.collect()   # after every song

        return {"status": "batch_processed", "processed": results}

    finally:
        cur.close()
        conn.close()
        gc.collect()