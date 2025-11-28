from fastapi import APIRouter, HTTPException, Depends
from typing import List
from stations.models import Station, StationFilter
from db.db import get_db, DB_NAME,COLLECTION_NAME

# Use APIRouter to group all station-related endpoints
router = APIRouter(
    prefix="/stations",
    tags=["Stations"],
)

@router.get("/", response_model=List[Station])
async def fetch_stations(
        # FastAPI automatically handles optional query parameters (?language=English)
        filters: StationFilter = Depends()
):
    database = get_db()

    if database is None:
        raise HTTPException(status_code=503, detail="Database connection failed during startup.")

    print(f"COLLECTION_NAME router.py: {COLLECTION_NAME}")

    collection = database[COLLECTION_NAME]
    query = {} # Initialize an empty MongoDB query dictionary

    # Build the MongoDB query based on the filters provided by the client
    if filters.language:
        # Use the MongoDB field name ('Language') for the query
        query['Language'] = filters.language

    if filters.genre:
        query['genre'] = filters.genre

    # Add logic for other filters (e.g., page) here

    try:
        # Pass the constructed query to find()
        stations_cursor = collection.find({})
        stations_list = await stations_cursor.to_list(length=100)

        return stations_list

    except Exception as e:
        print(f"Error during database query: {e}")
        raise HTTPException(status_code=500, detail="Error fetching stations from database.")

