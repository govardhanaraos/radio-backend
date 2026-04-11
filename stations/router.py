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
                # Use orjson.loads for fast deserialization
                return orjson.loads(cached_data)

        except Exception as e:
            # Log the error but don't stop the request; fall back to the database
            print(f"⚠️ Redis read error, falling back to database: {e}")
            pass  # Continue to database logic if Redis fails

    pool = get_pg_pool()

    if pool is None:
        raise HTTPException(status_code=503, detail="Database connection failed during startup.")

    # --- Pagination Constants ---


    if filters.page < 1:
        raise HTTPException(status_code=400, detail="Page number must be 1 or greater.")
    print(f"filters.page: {filters.page}")
    print(f"filters.limit: {filters.limit}")

    skip_count = (filters.page - 1) * filters.limit
    # ----------------------------

    # 1. Base Query for Filtering
    query_parts = []
    params = []
    
    if filters.language:
        params.append(filters.language)
        # Note: In Mongo it matched BOTH language AND page to filters.language because it was a dict with two keys
        query_parts.append(f"language = ${len(params)} AND page = ${len(params)}")
    
    if filters.genre:
        params.append(filters.genre)
        query_parts.append(f"genre = ${len(params)} AND page = ${len(params)}")

    where_clause = " AND ".join(query_parts)
    if where_clause:
        where_clause = "WHERE " + where_clause

    try:
        sql = f"""
            SELECT * FROM (
                SELECT id, name, logo_url AS "logoUrl", stream_url AS "streamUrl", language, genre, page
                FROM radio_stations
                
                UNION ALL
                
                SELECT id, name, logo_url AS "logoUrl", stream_url AS "streamUrl", language, genre, page
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

            # Serialize the Python list of Station objects into a JSON string
            # orjson.dumps works efficiently with Pydantic models/lists
            serialized_data = orjson.dumps(stations_list)

            # Set the key with an expiration time (EX)
            await r_async.set(CACHE_KEY_FIRST_PAGE, serialized_data, ex=CACHE_TTL)

        # NOTE: We only cache the unfiltered first page to ensure all users get the fast path.
        # If the request has language or genre filters, it bypasses the write-to-cache step.
        return stations_list

    except Exception as e:
        print(f"Error during database query: {e}")
        raise HTTPException(status_code=500, detail="Error fetching stations from database.")