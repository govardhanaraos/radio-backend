import os

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException, APIRouter
import httpx
import psycopg2
from psycopg2.extras import execute_values
import logging
import time

load_dotenv()

# Create the router (the department)
router = APIRouter(
    prefix="/radio-browser/api/stations",
    tags=["Stations"]
)

# Replace with your actual Aiven PostgreSQL connection string
DATABASE_URL = os.getenv("POSTGRESQL_DATABASE_URL_TELUGUWAP")
RADIO_API_URL = os.getenv("RADIO_BROWSER_API_URL")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def sync_radio_stations_task():
    """Background task to fetch and upsert stations using pagination."""
    logger.info("Starting paginated Radio-Browser sync...")

    limit = 10000  # Fetch 10,000 stations at a time
    offset = 0
    total_processed = 0

    try:
        # 1. Connect to Database once before the loop
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # 2. Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS radio_browser_stations (
                stationuuid UUID PRIMARY KEY,
                name TEXT,
                url TEXT,
                url_resolved TEXT,
                homepage TEXT,
                favicon TEXT,
                tags TEXT,
                country TEXT,
                countrycode VARCHAR(10),
                language TEXT,
                votes INT DEFAULT 0,
                codec VARCHAR(50),
                bitrate INT DEFAULT 0,
                lastchangetime TIMESTAMP,
                geo_lat DOUBLE PRECISION,
                geo_long DOUBLE PRECISION
            );
        """)
        conn.commit()

        # 3. The Upsert Query
        upsert_query = """
            INSERT INTO radio_browser_stations (
                stationuuid, name, url, url_resolved, homepage, favicon, tags,
                country, countrycode, language, votes, codec, bitrate, lastchangetime,
                geo_lat, geo_long
            ) VALUES %s
            ON CONFLICT (stationuuid) DO UPDATE SET
                name = EXCLUDED.name,
                url = EXCLUDED.url,
                url_resolved = EXCLUDED.url_resolved,
                homepage = EXCLUDED.homepage,
                favicon = EXCLUDED.favicon,
                tags = EXCLUDED.tags,
                country = EXCLUDED.country,
                countrycode = EXCLUDED.countrycode,
                language = EXCLUDED.language,
                votes = EXCLUDED.votes,
                codec = EXCLUDED.codec,
                bitrate = EXCLUDED.bitrate,
                lastchangetime = EXCLUDED.lastchangetime,
                geo_lat = EXCLUDED.geo_lat,
                geo_long = EXCLUDED.geo_long;
        """

        # 4. Open HTTP client and start pagination loop
        with httpx.Client(timeout=60.0) as client:
            while True:
                logger.info(f"Fetching stations with limit={limit} and offset={offset}...")

                # Append limit and offset to the API URL
                paginated_url = f"{RADIO_API_URL}?limit={limit}&offset={offset}"
                response = client.get(paginated_url)
                response.raise_for_status()
                stations_data = response.json()

                # If the API returns an empty list, we have reached the end of the database
                if not stations_data:
                    logger.info("No more stations returned. Sync complete!")
                    break

                # 5. Extract fields
                records_to_upsert = []
                for s in stations_data:
                    if not s.get("stationuuid"):
                        continue

                    records_to_upsert.append((
                        s.get("stationuuid"),
                        s.get("name", "")[:255],
                        s.get("url"),
                        s.get("url_resolved"),
                        s.get("homepage"),
                        s.get("favicon"),
                        s.get("tags"),
                        s.get("country"),
                        s.get("countrycode"),
                        s.get("language"),
                        s.get("votes", 0) or 0,
                        s.get("codec"),
                        s.get("bitrate", 0) or 0,
                        s.get("lastchangetime_iso8601"),
                        s.get("geo_lat"),
                        s.get("geo_long")
                    ))

                # 6. Execute bulk upsert for this chunk
                if records_to_upsert:
                    execute_values(cursor, upsert_query, records_to_upsert, page_size=1000)
                    conn.commit()

                    total_processed += len(records_to_upsert)
                    logger.info(f"Successfully saved chunk. Total processed so far: {total_processed}")

                # 7. Increment the offset for the next loop
                offset += limit

                # Polite delay to prevent rate-limiting by Radio-Browser
                time.sleep(1)

        cursor.close()
        conn.close()
        logger.info(f"Final Total: Synced {total_processed} stations into PostgreSQL.")

    except Exception as e:
        logger.error(f"Error during station sync: {str(e)}")
        # If it fails, ensure connections are closed safely
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

@router.post("/sync", tags=["Admin"])
async def trigger_station_sync(background_tasks: BackgroundTasks):
    """
    Endpoint to trigger the massive Radio-Browser data sync.
    Runs in the background so the HTTP request doesn't timeout.
    """
    background_tasks.add_task(sync_radio_stations_task)
    return {
        "status": "success",
        "message": "Station sync initiated in the background. Check server logs for progress."
    }


@router.get("get-stations", tags=["Public"])
async def get_all_stations(limit: int = 50, offset: int = 0):
    """
    Your modified API to serve the stations to your Flutter app.
    """
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT * FROM radio_browser_stations 
            ORDER BY votes DESC 
            LIMIT %s OFFSET %s
        """, (limit, offset))

        stations = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"data": stations}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))