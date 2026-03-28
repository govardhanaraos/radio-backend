import os
import json
import time
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from groq import Groq

# Import your DB connection function
from db.db import get_pg_conn

router = APIRouter(prefix="/api/v1/ai", tags=["AI Assistant"])

# --- Configure the AI Assistant (Gemini) ---
# 2. Use the new Client object
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

# --- Caching Setup ---
# Simple in-memory cache: { "language_quality": {"data": [...], "expires_at": timestamp} }
CACHE = {}
CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours


# --- Models ---
class AISongResponse(BaseModel):
    song_name: str
    album_name: str
    blomp_url: str


# --- Helpers ---
def generate_temp_blomp_url(path: str, file_hash: str) -> str:
    """
    Placeholder for your Blomp URL generation logic.
    """
    if not path or not file_hash:
        return ""
    # Replace this with your actual Blomp authentication/URL parsing logic
    return f"https://api.blomp.com/download?path={path}&hash={file_hash}&temp_token=generated"


def get_ai_song_recommendations(language: str) -> List[dict]:
    prompt = f"""
    You are a music expert. Provide a list of the 15 most popular {language} songs.
    Return ONLY a valid JSON array of objects. Do not include markdown formatting or backticks.
    Each object must have exactly two keys: "song_name" and "album_name".
    Example: [{{"song_name": "Tum Hi Ho", "album_name": "Aashiqui 2"}}]
    """

    try:
        # Call Groq's extremely fast Llama 3 model
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.7,
            # Force the model to return valid JSON
            response_format={"type": "json_object"}
        )

        raw_text = chat_completion.choices[0].message.content.strip()
        print(f"Groq Response: {raw_text}")

        # Groq will return something like {"songs": [{"song_name": "...", ...}]}
        data = json.loads(raw_text)

        # Extract the array from the JSON object
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
        raise HTTPException(status_code=400,
                            detail="Currently only 'hindi' language is supported for this table schema.")

    cache_key = f"{language.lower()}_{quality.lower()}"
    current_time = time.time()

    # 1. Check Cache
    if cache_key in CACHE:
        cached_item = CACHE[cache_key]
        if current_time < cached_item["expires_at"]:
            print("Returning AI songs from 6-hour cache.")
            return cached_item["data"]

    # 2. Get AI Recommendations
    ai_recommendations = get_ai_song_recommendations(language)
    if not ai_recommendations:
        raise HTTPException(status_code=500, detail="Failed to generate song list from AI.")

    # 3. Map Quality to DB Columns securely
    quality_columns = {
        "original": ("blomp_path_original", "blomp_hash_original"),
        "128kbps": ("blomp_path_128kbps", "blomp_hash_128kbps"),
        "320kbps": ("blomp_path_320kbps", "blomp_hash_320kbps"),
    }
    path_col, hash_col = quality_columns[quality]

    matched_songs = []

    # 4. Check DB for matches
    conn = get_pg_conn()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    try:
        # Use RealDictCursor so we can access row data by column name
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for ai_song in ai_recommendations:
                # Use ILIKE and % wildcards for fuzzy matching since AI output might differ slightly from DB
                search_song = f"%{ai_song.get('song_name', '')}%"
                search_album = f"%{ai_song.get('album_name', '')}%"

                query = f"""
                    SELECT 
                        s.song_name, 
                        a.album_name, 
                        s.{path_col} AS blomp_path, 
                        s.{hash_col} AS blomp_hash
                    FROM public.hindiflacs_songs s
                    JOIN public.hindiflacs_albums_list a ON s.album_id = a.id
                    WHERE s.song_name ILIKE %s AND a.album_name ILIKE %s
                    AND s.{path_col} IS NOT NULL
                    LIMIT 1;
                """

                cur.execute(query, (search_song, search_album))
                row = cur.fetchone()

                if row:
                    temp_url = generate_temp_blomp_url(row['blomp_path'], row['blomp_hash'])
                    matched_songs.append(
                        AISongResponse(
                            song_name=row['song_name'],
                            album_name=row['album_name'],
                            blomp_url=temp_url
                        )
                    )

                # Stop if we hit 10 successfully matched songs
                if len(matched_songs) >= 10:
                    break
    except Exception as e:
        print(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail="Error querying the database.")
    finally:
        conn.close()

    # 5. Save to Cache and Return
    if not matched_songs:
        raise HTTPException(status_code=404, detail="AI suggested songs, but none were found in the local database.")

    CACHE[cache_key] = {
        "data": matched_songs,
        "expires_at": current_time + CACHE_TTL_SECONDS
    }

    return matched_songs