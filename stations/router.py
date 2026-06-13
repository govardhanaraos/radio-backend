from fastapi import APIRouter, HTTPException, Depends
from typing import List
# Assuming Station and StationFilter are defined in stations.models
from stations.models import Station, StationFilter
from db.db import get_pg_pool
import orjson
from db.redis_config import (r_async, CACHE_TTL, CACHE_KEY_FIRST_PAGE)

# Use APIRouter to group all station-related endpoints
router = APIRouter(
    prefix="/stations",
    tags=["Stations"],
)


@router.get("/", response_model=List[Station])
async def fetch_stations(
        filters: StationFilter = Depends()
):
    # --- Caching Logic: Check Redis for the first page (page=1, limit=50) ---
    is_cacheable_request = (filters.page == 1 and filters.limit == 50)

    if is_cacheable_request and r_async is not None:
        try:
            # 1. Check Redis Cache
            cached_data = await r_async.get(CACHE_KEY_FIRST_PAGE)

            if cached_data:
                print("🚀 Cache Hit: Returning stations from Redis.")
                # Deserialize the JSON string back into a Python list
                return orjson.loads(cached_data)

        except Exception as e:
            print(f"⚠️ Redis read error, falling back to database: {e}")
            pass  # Continue to database logic if Redis fails

    pool = get_pg_pool()

    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection failed during startup.")

    if filters.page < 1:
        raise HTTPException(status_code=400, detail="Page number must be 1 or greater.")

    print(f"filters.page: {filters.page}")
    print(f"filters.limit: {filters.limit}")

    skip_count = (filters.page - 1) * filters.limit

    # 1. Base Query for Filtering
    query_parts = []
    params = []

    if filters.language:
        # FIX: Use ILIKE with wildcards to find languages inside comma-separated lists
        params.append(f"%{filters.language}%")
        # Search for the language in EITHER the language column OR the page slug
        query_parts.append(f"(language ILIKE ${len(params)} OR page ILIKE ${len(params)})")

    if filters.genre:
        # FIX: Use ILIKE for genres/tags as well
        params.append(f"%{filters.genre}%")
        query_parts.append(f"genre ILIKE ${len(params)}")

    where_clause = " AND ".join(query_parts)
    if where_clause:
        where_clause = "WHERE " + where_clause

    try:
        # UPDATE: Added 'country' to all three SELECT statements
        sql = f"""
                SELECT * FROM (
                    SELECT id::text, name, logo_url AS "logoUrl", stream_url AS "streamUrl", language, genre, country, page
                    FROM radio_stations

                    UNION ALL

                    SELECT id::text, name, logo_url AS "logoUrl", stream_url AS "streamUrl", language, genre, country, page
                    FROM radio_garden_channels

                    
                ) AS combined
                {where_clause}
                OFFSET ${len(params) + 1} LIMIT ${len(params) + 2}
            """
        params.extend([skip_count, filters.limit])

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        stations_list = [dict(row) for row in rows]

        # --- Caching Logic: Store in Redis on Cache Miss ---
        if is_cacheable_request and r_async is not None and not filters.language and not filters.genre:
            print(f"💾 Cache Miss: Storing result in Redis for {CACHE_TTL} seconds.")
            serialized_data = orjson.dumps(stations_list)
            await r_async.set(CACHE_KEY_FIRST_PAGE, serialized_data, ex=CACHE_TTL)

        return stations_list

    except Exception as e:
        print(f"Error during database query: {e}")
        raise HTTPException(status_code=500, detail="Error fetching stations from database.")