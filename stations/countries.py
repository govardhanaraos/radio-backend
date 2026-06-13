from fastapi import APIRouter, HTTPException
import psycopg2
import logging
import json
from datetime import datetime, timedelta
from  db.db import POSTGRESQL_DATABASE_URL

router = APIRouter(
    prefix="/api/countries",
    tags=["Filters"]
)

logger = logging.getLogger(__name__)


@router.get("/")
async def get_all_countries():
    """
    Fetches a cached list of all available countries across the three tables.
    Forces key regions (Saudi Arabia, India, etc.) to the top of the Quick Chips list.
    """
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(POSTGRESQL_DATABASE_URL)
        cursor = conn.cursor()

        # 1. Check the Cache for Countries
        param_key = 'available_countries'
        cursor.execute("""
            SELECT parameter_data, modified_date 
            FROM app_parameters 
            WHERE parameter_code = %s
        """, (param_key,))

        cache_record = cursor.fetchone()

        # 2. Return cached data if < 30 days old
        if cache_record:
            parameter_data, modified_date = cache_record

            if isinstance(parameter_data, str):
                parameter_data = json.loads(parameter_data)

            if modified_date and (datetime.now() - modified_date < timedelta(days=30)):
                logger.info("Serving countries from cache.")
                return parameter_data

            # 3. Cache Miss: Run the Heavy SQL Query
            logger.info("Cache expired or missing. Running heavy country query...")
            query = """
                WITH t1 AS (
                    SELECT TRIM(LOWER(unnest(string_to_array(country, ',')))) AS c 
                    FROM radio_stations 
                    WHERE country IS NOT NULL AND country <> ''
                ),
                t2 AS (
                    SELECT TRIM(LOWER(unnest(string_to_array(country, ',')))) AS c 
                    FROM radio_garden_channels 
                    WHERE country IS NOT NULL AND country <> ''
                ),
                t3 AS (
                    SELECT TRIM(LOWER(unnest(string_to_array(country, ',')))) AS c 
                    FROM radio_browser_stations 
                    WHERE country IS NOT NULL AND country <> ''
                ),
                combined AS (
                    SELECT c FROM t1
                    UNION ALL
                    SELECT c FROM t2
                    UNION ALL
                    SELECT c FROM t3
                ),
                normalized_countries AS (
                    SELECT 
                        -- ALIAS MAPPING: Force common variations into a single standard name
                        CASE 
                            WHEN c IN ('united states of america', 'the united states of america', 'usa', 'u.s.a.', 'us') THEN 'united states'
                            WHEN c IN ('the united kingdom of great britain and northern ireland', 'great britain', 'uk') THEN 'united kingdom'
                            WHEN c IN ('russian federation') THEN 'russia'
                            WHEN c IN ('korea, republic of', 'republic of korea') THEN 'south korea'
                            WHEN c IN ('uae') THEN 'united arab emirates'
                            ELSE c
                        END AS clean_country
                    FROM combined
                    WHERE c <> '' 
                      AND length(c) BETWEEN 2 AND 50
                      AND c !~ 'http|www'
                      AND c ~ '^[[:alpha:]]'
                )
                SELECT 
                    INITCAP(clean_country) AS country_name, 
                    COUNT(*) AS frequency
                FROM normalized_countries
                GROUP BY INITCAP(clean_country)
                ORDER BY frequency DESC;
            """

        cursor.execute(query)
        country_data = cursor.fetchall()  # Format: [("United States", 15000), ("Germany", 12000), ...]

        # 4. Build the "Top 10" with Priority Regions for GRRadio
        # We explicitly force the locations you and your target audience care about most
        forced_countries = ["Saudi Arabia", "India", "United States", "United Kingdom", "United Arab Emirates"]
        top_countries = list(forced_countries)

        for row in country_data:
            country = row[0]
            if country not in top_countries:
                top_countries.append(country)

            if len(top_countries) >= 10:
                break

        # 5. Extract full alphabetical list
        all_countries = sorted([row[0] for row in country_data])

        # 6. Format Payload
        response_data = {
            "count": len(all_countries),
            "top_countries": top_countries,
            "all_countries": all_countries
        }

        # 7. Upsert into app_parameters cache
        json_payload = json.dumps(response_data)

        if cache_record:
            cursor.execute("""
                UPDATE app_parameters 
                SET parameter_data = %s::jsonb, modified_date = NOW() 
                WHERE parameter_code = %s
            """, (json_payload, param_key))
        else:
            cursor.execute("""
                INSERT INTO app_parameters (parameter_code, parameter_data, modified_date) 
                VALUES (%s, %s::jsonb, NOW())
            """, (param_key, json_payload))

        conn.commit()
        return response_data

    except Exception as e:
        logger.error(f"Error fetching countries: {str(e)}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to fetch countries")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()