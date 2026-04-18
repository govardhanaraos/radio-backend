import os

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException, APIRouter
import httpx
import psycopg2
from psycopg2.extras import execute_values
import logging

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
    """Background task to fetch and upsert stations."""
    logger.info("Starting Radio-Browser sync...")

    try:
        # 1. Fetch data from Radio-Browser
        with httpx.Client(timeout=60.0) as client:
            response = client.get(RADIO_API_URL)
            response.raise_for_status()
            stations_data = response.json()

        logger.info(f"Fetched {len(stations_data)} stations. Preparing database upsert...")

        # 2. Extract necessary fields
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
                # --- NEW FIELDS ---
                s.get("geo_lat"),  # Psycopg2 will automatically convert None to SQL NULL
                s.get("geo_long")
            ))

        # 3. Connect to Database
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # 4. Create table if missing (Updated with geo_lat/geo_long)
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

        # 5. The Upsert Query (Updated)
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

        # 6. Execute bulk upsert
        execute_values(cursor, upsert_query, records_to_upsert, page_size=1000)

        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Sync completed successfully!")

    except Exception as e:
        logger.error(f"Error during station sync: {str(e)}")


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