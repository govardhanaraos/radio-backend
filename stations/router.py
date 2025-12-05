from fastapi import APIRouter, HTTPException, Depends
from typing import List
# Assuming Station and StationFilter are defined in stations.models
from stations.models import Station, StationFilter
# Assuming get_db, DB_NAME, and COLLECTION_NAME are defined in db.db
from db.db import get_db, DB_NAME, COLLECTION_NAME,RADIO_GARDEN_CHANNELS_COLLECTION
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

    database = get_db()

    if database is None:
        raise HTTPException(status_code=503, detail="Database connection failed during startup.")

    # --- Pagination Constants ---


    if filters.page < 1:
        raise HTTPException(status_code=400, detail="Page number must be 1 or greater.")
    print(f"filters.page: {filters.page}")
    print(f"filters.limit: {filters.limit}")

    skip_count = (filters.page - 1) * filters.limit
    # ----------------------------

    # The collection to start the aggregation pipeline from (radio_stations)
    radio_stations_collection = database[COLLECTION_NAME]

    # 1. Base Query for Filtering
    match_query = {}
    if filters.language:
        # Note: The field name must match the name AFTER projection/standardization (i.e., 'language')
        match_query['language'] = filters.language
        match_query['page'] = filters.language
    if filters.genre:
        match_query['genre'] = filters.genre
        match_query['page'] = filters.genre


    # 2. Aggregation Pipeline Definition
    pipeline = [
        # Stage 1: Standardize fields from the starting collection (radio_stations)
        {
            "$project": {
                "_id": 0,  # Exclude MongoDB's internal _id
                "id": "$id",
                "name": "$name",
                "logoUrl": "$logoUrl",
                "streamUrl": "$streamUrl",
                "language": "$language",  # Already matches the target structure
                "genre": "$genre",  # Already matches the target structure
                "page": "$page"
            }
        },

        # Stage 2: Combine with the second collection (radio_garden_channels)
        {
            "$unionWith": {
                "coll": RADIO_GARDEN_CHANNELS_COLLECTION,
                "pipeline": [
                    # Sub-Stage for the second collection: Standardize its fields
                    {
                        "$project": {
                            "_id": 0,
                            "id": "$id",
                            "name": "$name",
                            "logoUrl": "$logoUrl",
                            "streamUrl": "$streamUrl",
                            "language": "$language",
                            "genre": "$genre",
                            "page": "$page"
                            # radio_garden_channels fields 'radio_garden_id', 'country', 'state' are dropped
                        }
                    }
                ]
            }
        },

        # Stage 3: Apply Filters (Matching on the combined and standardized set)
        {
            "$match": match_query
        },

        # Stage 4: Pagination - Skip (offset)
        {
            "$skip": skip_count
        },

        # Stage 5: Pagination - Limit (page size)
        {
            "$limit": filters.limit
        }
    ]

    try:
        # Run the aggregation pipeline
        stations_cursor = radio_stations_collection.aggregate(pipeline)

        # Convert the motor cursor result into a list
        stations_list = await stations_cursor.to_list(length=filters.limit)

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