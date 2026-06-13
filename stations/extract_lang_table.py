import os

from dotenv import load_dotenv
from fastapi import APIRouter
import psycopg2
load_dotenv()


PG_URL = os.getenv("POSTGRESQL_DATABASE_URL")

router = APIRouter()


@router.post("/api/admin/fix-garden-languages", tags=["Admin"])
def fix_radio_garden_languages():
    """Extracts languages from slugs based on a master language list."""

    conn = psycopg2.connect(PG_URL)
    cursor = conn.cursor()

    try:
        # 1. Get the Master List of clean languages from Tables 1 & 3
        cursor.execute("""
            WITH t1 AS (SELECT TRIM(LOWER(unnest(string_to_array(language, ',')))) AS l FROM radio_stations),
                 t3 AS (SELECT TRIM(LOWER(unnest(string_to_array(language, ',')))) AS l FROM radio_browser_stations)
            SELECT DISTINCT l FROM (SELECT l FROM t1 UNION SELECT l FROM t3) combined WHERE l <> ''
        """)
        # Create a set of all known languages (e.g., {"english", "hindi", "assamese", ...})
        master_languages = {row[0] for row in cursor.fetchall()}

        # 2. Fetch all Radio Garden Channels
        cursor.execute("SELECT id, page FROM radio_garden_channels WHERE language IS NULL")
        garden_channels = cursor.fetchall()

        updates = []
        for channel_id, page_slug in garden_channels:
            if not page_slug:
                continue

            # Split the slug by hyphens
            slug_words = set(page_slug.lower().split('-'))

            # Find the intersection between words in the slug and our master languages
            found_languages = slug_words.intersection(master_languages)

            if found_languages:
                # Join them with commas to match your other tables (e.g., "english,hindi")
                language_str = ",".join(found_languages)
                updates.append((language_str, channel_id))

        # 3. Bulk update the Radio Garden table with the extracted languages
        if updates:
            psycopg2.extras.execute_values(
                cursor,
                "UPDATE radio_garden_channels SET language = data.lang FROM (VALUES %s) AS data (lang, id) WHERE radio_garden_channels.id = data.id",
                updates
            )
            conn.commit()

        return {"status": "success", "updated_rows": len(updates)}

    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()