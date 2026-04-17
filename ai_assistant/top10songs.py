import os
import json
from typing import List

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from groq import Groq
from db.redis_config import (r_async, CACHE_TTL, CACHE_KEY_FIRST_PAGE)
import swiftclient
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# Import your DB connection function
from db.db import get_pg_conn

load_dotenv()

router = APIRouter(prefix="/api/v1/ai", tags=["AI Assistant"])


# --- Configurations ---
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
BLOMP_PASS = os.environ.get("BLOMP_PASS", "your_blomp_password")

print(f"BLOMP_PASS: {BLOMP_PASS}")

print(f"GROQ_API_KEY: {os.environ.get("GROQ_API_KEY", "")}")

redis_client = r_async
# Cache tokens and AI responses for 12 Hours
CACHE_TTL_SECONDS = 43200


# --- Models ---
class AISongResponse(BaseModel):
    song_name: str
    album_name: str
    blomp_url: str
    auth_token: str  # Added so Flutter can authenticate the stream


# --- Helpers ---
def get_blomp_auth_data(email: str) -> dict:
    """
    Authenticates with Blomp and returns the storage_url and token.
    Caches the token in Redis for 12 hours to avoid spamming the Auth API.
    """
    if not email:
        return {}

    cache_key = f"blomp_auth:{email}"

    # 1. Check if we already have a valid token for this email
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        print(f"Redis Auth Read Error: {e}")

    # 2. Fetch new token from Blomp
    try:
        swift_conn = swiftclient.Connection(
            authurl="https://authenticate.blomp.com/v3",
            user=email,
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
        swift_conn.close()

        auth_data = {"storage_url": storage_url, "token": token}

        # 3. Cache it for 12 hours
        try:
            redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(auth_data))
        except Exception as e:
            print(f"Redis Auth Write Error: {e}")

        return auth_data

    except Exception as e:
        print(f"Blomp Auth Error for {email}: {e}")
        return {}


def get_ai_song_recommendations(language: str) -> List[dict]:
    prompt = f"""
    You are a music expert. Provide a list of the 15 most popular {language} songs.
    Return ONLY a valid JSON array of objects. Do not include markdown formatting or backticks.
    Each object must have exactly two keys: "song_name" and "album_name".
    """
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        raw_text = chat_completion.choices[0].message.content.strip()
        data = json.loads(raw_text)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            for key in data.keys():
                if isinstance(data[key], list):
                    return data[key]
        return []
    except Exception as e:
        print(f"AI Generation Error: {e}")
        return []


# --- Endpoint ---
@router.get("/top-songs", response_model=List[AISongResponse])
def get_ai_top_songs(
        language: str = Query("hindi", description="Language of the songs"),
        quality: str = Query("128kbps", pattern="^(original|128kbps|320kbps)$", description="Audio quality")
):
    if language.lower() != "hindi":
        raise HTTPException(status_code=400, detail="Currently only 'hindi' language is supported.")

    cache_key = f"top_songs:{language.lower()}:{quality.lower()}"

    # 1. Check Redis Cache First
    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            print("Returning AI songs from 12-hour Redis cache.")
            return json.loads(cached_data)
    except Exception as e:
        print(f"Redis Read Error: {e}")

    # 2. Cache Miss: Get AI Recommendations
    ai_recommendations = get_ai_song_recommendations(language)
    if not ai_recommendations:
        raise HTTPException(status_code=500, detail="Failed to generate song list from AI.")

    # 3. Map Quality
    quality_columns = {
        "original": "blomp_path_original",
        "128kbps": "blomp_path_128kbps",
        "320kbps": "blomp_path_320kbps",
    }
    path_col = quality_columns[quality]

    matched_songs = []

    # 4. Check DB for matches & Get User Email
    conn = get_pg_conn()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for ai_song in ai_recommendations:
                search_song = f"%{ai_song.get('song_name', '')}%"
                search_album = f"%{ai_song.get('album_name', '')}%"

                query = f"""
                    SELECT 
                        s.song_name, 
                        a.album_name, 
                        s.{path_col} AS blomp_path, 
                        uma.email AS blomp_user_email
                    FROM public.hindiflacs_songs s
                    JOIN public.hindiflacs_albums_list a ON s.album_id = a.id
                    LEFT JOIN public.user_mail_accounts uma ON s.blomp_user_id = uma.id
                    WHERE s.song_name ILIKE %s AND a.album_name ILIKE %s
                    AND s.{path_col} IS NOT NULL
                    LIMIT 1;
                """

                cur.execute(query, (search_song, search_album))
                row = cur.fetchone()

                if row:
                    blomp_email = row.get('blomp_user_email') or os.environ.get("BLOMP_USER")

                    # Fetch Cached Auth Data (Storage URL + Token)
                    auth_data = get_blomp_auth_data(blomp_email)

                    if auth_data:
                        # Construct the direct OpenStack Swift URL
                        object_path = row['blomp_path']
                        if not object_path.startswith("hindiflacs_songs/"):
                            object_path = f"hindiflacs_songs/{object_path}"

                        blomp_url = f"{auth_data['storage_url']}/{blomp_email}/{object_path}"

                        matched_songs.append(
                            AISongResponse(
                                song_name=row['song_name'],
                                album_name=row['album_name'],
                                blomp_url=blomp_url,
                                auth_token=auth_data['token']  # Give the token to Flutter
                            )
                        )

                if len(matched_songs) >= 10:
                    break
    except Exception as e:
        print(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail="Error querying the database.")
    finally:
        conn.close()

    if not matched_songs:
        raise HTTPException(status_code=404, detail="AI suggested songs, but none were found in the database.")

    # 5. Save to Redis
    try:
        result_list = [s.model_dump() if hasattr(s, 'model_dump') else s.dict() for s in matched_songs]
        redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(result_list))
        print("Stored new AI songs in Redis cache for 12 hours.")
    except Exception as e:
        print(f"Redis Write Error: {e}")

    return matched_songs