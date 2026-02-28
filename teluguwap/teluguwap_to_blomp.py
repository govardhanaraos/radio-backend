import hmac
import hashlib
import time
import requests
import swiftclient
from io import BytesIO
from db.db import BLOMP_AUTH_URL,BLOMP_USER,BLOMP_PASS,TENANT


def get_conn():
    return swiftclient.Connection(
        authurl=BLOMP_AUTH_URL,
        user=BLOMP_USER,
        key=BLOMP_PASS,
        tenant_name=TENANT,
        auth_version="2"
    )


def transfer_to_blomp(public_url, song_filename):
    # 1. Fetch from the public source
    response = requests.get(public_url, stream=True)
    if response.status_code != 200:
        return None

    # 2. Connect to Blomp
    conn = get_conn()
    container_name = "music_library"

    # Create container if it doesn't exist
    conn.put_container(container_name)

    # 3. Stream the upload to Blomp
    conn.put_object(
        container_name,
        song_filename,
        contents=response.content,
        content_type='audio/mpeg'
    )

    # This is the path you save in your Neon DB
    return f"{container_name}/{song_filename}"

def generate_flutter_download_link(blomp_path):
    key = "the_same_secret_string_from_step_3"
    method = "GET"
    expires = int(time.time() + 3600)  # Valid for 1 hour

    # Blomp storage path format: /v1/BlompDrive_your_email_com/container/filename
    storage_path = f"/v1/BlompDrive_{BLOMP_USER.replace('@', '_').replace('.', '_')}/{blomp_path}"

    hmac_body = f"{method}\n{expires}\n{storage_path}"
    sig = hmac.new(key.encode(), hmac_body.encode(), hashlib.sha1).hexdigest()

    return f"https://storage.blomp.com{storage_path}?temp_url_sig={sig}&temp_url_expires={expires}"