import json
import os
from datetime import timedelta, datetime

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
import psycopg2
import logging
from  db.db import POSTGRESQL_DATABASE_URL
# Define the router
router = APIRouter(
    prefix="/api/languages",
    tags=["Filters"]
)


logger = logging.getLogger(__name__)


@router.get("/")
async def get_all_languages():
    """
    Fetches languages from cache. If older than 30 days, re-runs the heavy SQL,
    forces specific regional languages to the top, and updates the cache.
    """
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(POSTGRESQL_DATABASE_URL)
        cursor = conn.cursor()

        # 1. Check the Cache
        param_key = 'available_languages'
        cursor.execute('SELECT parameter_data, modified_date FROM app_parameters WHERE parameter_code = %s', (param_key,))
        cache_record = cursor.fetchone()

        if cache_record:
            parameter_data, modified_date = cache_record

            # Since parameter_data is JSONB in your DB, psycopg2 might return it as a dict directly!
            if isinstance(parameter_data, str):
                parameter_data = json.loads(parameter_data)

            if modified_date and (datetime.now() - modified_date < timedelta(days=30)):
                logger.info("Serving languages from cache.")
                return parameter_data

            # 3. Cache Miss or Expired: Run the heavy query
            logger.info("Cache expired or missing. Running heavy language query...")
            query = """
                WITH t1 AS (
                    SELECT TRIM(LOWER(unnest(string_to_array(language, ',')))) AS lang 
                    FROM radio_stations 
                    WHERE language IS NOT NULL AND language <> ''
                ),
                t2 AS (
                    SELECT TRIM(LOWER(unnest(string_to_array(language, ',')))) AS lang 
                    FROM radio_garden_channels 
                    WHERE language IS NOT NULL AND language <> ''
                ),
                t3 AS (
                    SELECT TRIM(LOWER(unnest(string_to_array(language, ',')))) AS lang 
                    FROM radio_browser_stations 
                    WHERE language IS NOT NULL AND language <> ''
                ),
                combined AS (
                    SELECT lang FROM t1
                    UNION ALL
                    SELECT lang FROM t2
                    UNION ALL
                    SELECT lang FROM t3
                )
                SELECT 
                    INITCAP(lang) AS language, 
                    COUNT(*) AS frequency
                FROM combined
                WHERE lang <> '' 
                  -- RULE 1: Must be between 2 and 30 characters long
                  AND length(lang) BETWEEN 2 AND 30
                  -- RULE 2: Exclude anything containing "http" or "www" just to be safe
                  AND lang !~ 'http|www'
                  -- RULE 3: Strict Whitelist - Starts with a letter, followed ONLY by letters, spaces, hyphens, or apostrophes until the very end
                  AND lang ~ '^[[:alpha:]][[:alpha:] \-]*$'
                GROUP BY INITCAP(lang)
                ORDER BY frequency DESC;
            """

        cursor.execute(query)
        language_data = cursor.fetchall()  # Format: [("English", 5000), ("Spanish", 3000), ...]

        # 4. Build the "Top 10" with Forced Priorities
        forced_languages = ["Arabic", "Tamil", "Telugu"]
        top_languages = list(forced_languages)  # Start with our priorities

        for row in language_data:
            lang = row[0]
            # Add popular languages that aren't already in our forced list
            if lang not in top_languages:
                top_languages.append(lang)

            # Stop once we have exactly 10 chips
            if len(top_languages) >= 10:
                break

        # 5. Extract the full alphabetical list
        all_languages = sorted([row[0] for row in language_data])

        # 6. Format the final response payload
        response_data = {
            "count": len(all_languages),
            "top_languages": top_languages,
            "all_languages": all_languages
        }

        # 7. Upsert the new data into the app_parameters table
        # We use ::jsonb to explicitly tell Postgres to treat the string as JSON
        json_payload = json.dumps(response_data)

        if cache_record:
            # Update existing record
            cursor.execute("""
                        UPDATE app_parameters 
                        SET parameter_data = %s::jsonb, modified_date = NOW() 
                        WHERE parameter_code = %s
                    """, (json_payload, param_key))
        else:
            # Insert new record (No need to pass 'id', Postgres handles it now!)
            cursor.execute("""
                        INSERT INTO app_parameters (parameter_code, parameter_data, modified_date) 
                        VALUES (%s, %s::jsonb, NOW())
                    """, (param_key, json_payload))

        conn.commit()
        return response_data

    except Exception as e:
        logger.error(f"Error fetching languages: {str(e)}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to fetch languages")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()