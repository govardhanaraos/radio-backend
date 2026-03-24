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

router = APIRouter(prefix="/hindiflacs-song-download", tags=["hindiflacs-song-download"])
logging.getLogger("keystoneclient").setLevel(logging.WARNING)

CHUNK_SIZE = 256 * 1024

def get_next_blomp_account(cur):
    cur.execute("""
         SELECT uma.id, uma.email
        FROM user_mail_accounts uma
        where uma.default_account='Y' order by uma.sort_order LIMIT 1
    """)
    row = cur.fetchone()
    if not row:
        raise Exception("No accounts found in user_mail_accounts table.")
    return row

def get_db_connection():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL_TELUGUWAP)
    return conn, conn.cursor()

def clean(text):
    if not text:
        return None
    text = text.encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip()

def get_blomp_auth(user: str = None, password: str = None):
    auth_user = user or BLOMP_USER
    auth_pass = password or BLOMP_PASS
    swift_conn = swiftclient.Connection(
        authurl="https://authenticate.blomp.com/v3",
        user=auth_user,
        key=auth_pass,
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
    return storage_url, token

def _process_one_quality(s_id, q_name, fresh_url, storage_url, token, container: str = None):
    dl_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://hindiflacs.com/",
        "Accept": "*/*",
        "Connection": "keep-alive",
    }

    session = requests.Session()
    try:
        session.get("https://hindiflacs.com/", headers=dl_headers, timeout=15, verify=False)
    except Exception:
        pass

    resp = session.get(
        fresh_url,
        headers=dl_headers,
        stream=True,
        allow_redirects=True,
        timeout=90,
        verify=False
    )

    content_type = resp.headers.get("Content-Type", "")
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
    buf.seek(0)

    name_only     = os.path.splitext(filename)[0]
    ext           = os.path.splitext(filename)[1] or ".mp3"
    stored_name   = f"{s_id}_{name_only}_{q_name}{ext}"
    full_obj_path = f"hindiflacs_songs/{stored_name}"
    container     = container or BLOMP_USER
    put_url       = f"{storage_url}/{container}/{full_obj_path}"

    put_resp = None
    try:
        put_resp = requests.put(
            put_url,
            data=buf,
            headers={
                "X-Auth-Token": token,
                "Content-Type": "audio/mpeg",
                "Content-Length": str(total),
            },
            timeout=300,
            verify=False
        )
    except Exception as put_exc:
        if put_resp is None or put_resp.status_code not in (200, 201):
            buf.close()
            del buf
            raise
    finally:
        buf.close()
        del buf

    if put_resp.status_code not in (200, 201):
        if put_resp.status_code == 403:
            raise Exception(f"403 Forbidden — container '{container}' missing or token invalid.")
        raise Exception(f"Blomp PUT failed: HTTP {put_resp.status_code} — {put_resp.text[:200]}")

    return stored_name, file_hash

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
    resp.close()

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

@router.get("/get-128kbps/{song_id}")
def get_128kbps_link(song_id: int):
    conn, cur = get_db_connection()
    try:
        cur.execute(
            "SELECT download_link_128kbps, song_name, song_link FROM hindiflacs_songs WHERE id=%s",
            (song_id,)
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return {"status": "error", "message": "Song link not found"}

        details   = parse_song_details(row[2])
        fresh_url = "https://hindiflacs.com/" + details["downloads"]["128"]["link"]
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
    conn, cur = get_db_connection()
    results = []
    try:
        cur.execute("""
            SELECT id, song_name, download_link_original, download_link_128kbps,
                   download_link_320kbps, song_link
            FROM hindiflacs_songs
            WHERE details_status = 'blomp_pending'
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        """, (limit,))
        pending_songs = cur.fetchall()

        if not pending_songs:
            return {"status": "batch_processed", "processed": []}

        picked_ids = [row[0] for row in pending_songs]
        cur.execute(
            "UPDATE hindiflacs_songs SET details_status='blomp_picked' WHERE id = ANY(%s)",
            (picked_ids,)
        )
        conn.commit()

        blomp_account_id, blomp_account_mail = get_next_blomp_account(cur)
        storage_url, token = get_blomp_auth(user=blomp_account_mail)

        for s_id, s_name, link_orig, link_128, link_320, song_link_from_db in pending_songs:
            try:
                details     = parse_song_details(song_link_from_db)
                fresh_links = details["downloads"]
                del details
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                cur.execute(
                    "UPDATE hindiflacs_songs SET details_status='blomp_scrape_failed', details_updated_at=NOW() WHERE id=%s",
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
                    fresh_url = "https://hindiflacs.com/" + fresh_entry["link"]
                    b_path, b_hash = _process_one_quality(
                        s_id, q_name, fresh_url, storage_url, token,
                        container=blomp_account_mail
                    )
                    cur.execute(
                        f"UPDATE hindiflacs_songs SET {path_col}=%s, {hash_col}=%s, details_updated_at=NOW() WHERE id=%s",
                        (b_path, b_hash, s_id)
                    )
                    conn.commit()
                except Exception as e:
                    song_success = False
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                finally:
                    gc.collect()

            new_status = "blomp_completed" if song_success else "blomp_partial_failed"
            cur.execute(
                """UPDATE hindiflacs_songs
                   SET details_status=%s,
                       details_updated_at=NOW(),
                       blomp_user_id=%s
                   WHERE id=%s""",
                (new_status, blomp_account_id, s_id)
            )
            conn.commit()
            results.append({"id": s_id, "status": new_status})
            gc.collect()

        return {"status": "batch_processed", "processed": results}

    finally:
        cur.close()
        conn.close()
        gc.collect()

@router.get("/check-existence/{song_id}")
def check_blomp_file_exists(
    song_id: int,
    quality: str = Query(..., description="Accepted values: 'original', '128kbps', or '320kbps'")
):
    column_map = {
        '128kbps': 'blomp_path_128kbps',
        '320kbps': 'blomp_path_320kbps',
        'original': 'blomp_path_original'
    }

    col_name = column_map.get(quality.lower())
    if not col_name:
        return {"error": f"Invalid quality type: {quality}"}

    conn = None
    try:
        conn = psycopg2.connect(POSTGRESQL_DATABASE_URL_TELUGUWAP)
        cur = conn.cursor()
        query = f"""
            SELECT ts.{col_name}, uma.email
            FROM hindiflacs_songs ts
            LEFT JOIN user_mail_accounts uma ON uma.id = ts.blomp_user_id
            WHERE ts.id = %s
        """
        cur.execute(query, (song_id,))
        result = cur.fetchone()

        if not result or not result[0]:
            return {"song_id": song_id, "exists": False, "reason": "No path found in database"}

        blomp_object_path = result[0]
        container_name    = result[1] or BLOMP_USER

        swift_conn = swiftclient.Connection(
            authurl="https://authenticate.blomp.com/v3",
            user=container_name,
            key=BLOMP_PASS,
            auth_version="3",
            os_options={"tenant_name": "storage"}
        )

        blomp_object_path=f"hindiflacs_songs/{blomp_object_path}"

        try:
            swift_conn.head_object(container_name, blomp_object_path)
            return {"song_id": song_id, "quality": quality, "exists": True, "path": blomp_object_path}
        except swiftclient.exceptions.ClientException as e:
            if e.http_status == 404:
                return {"song_id": song_id, "exists": False, "reason": "File not found on Blomp"}
            raise e

    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn:
            conn.close()
