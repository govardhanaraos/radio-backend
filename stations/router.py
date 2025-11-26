from fastapi import APIRouter, HTTPException, Depends
from typing import List
from stations.models import Station, StationFilter
from data.stations_db import get_all_stations, get_station_by_id
from db.db import get_db, DB_NAME

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

    collection = database['radio_stations']
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

# Endpoint 2: Get a single station by ID
@router.get("/{station_id}", response_model=Station)
async def read_station(station_id: int):
    """Get details for a specific station."""
    station = get_station_by_id(station_id)
    if station is None:
        # FastAPI handles the HTTP 404 response automatically
        raise HTTPException(status_code=404, detail="Station not found")
    return station