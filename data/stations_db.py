# data/stations_db.py (Revised)
from typing import List, Optional
from stations.models import Station
from db.db import db
from bson.objectid import ObjectId # Required to query by MongoDB's native _id

COLLECTION_NAME = "radio_stations"

# --- ASYNCHRONOUS DATABASE FUNCTIONS ---

async def get_all_stations() -> List[Station]:
    """Retrieves all radio stations from the MongoDB collection."""
    if not db:
        print("Database client not available.")
        return []

    collection = db[COLLECTION_NAME]

    try:
        stations_cursor = collection.find({})
        stations_list = await stations_cursor.to_list(length=None)

        # We assume the documents contain the fields:
        # id, name, logoUrl, streamUrl, Language, genre, page
        return [Station.model_validate(item) for item in stations_list]

    except Exception as e:
        print(f"Error fetching stations from MongoDB: {e}")
        return []


async def get_station_by_id(station_id: str) -> Optional[Station]:
    """Finds a single station by its application ID ('id' field)."""
    if not db:
        return None

    collection = db[COLLECTION_NAME]

    try:
        # QUERY: Find by the 'id' field, which is a string (e.g., "0001")
        document = await collection.find_one({"id": station_id})

        if document:
            return Station.model_validate(document)

    except Exception as e:
        print(f"Error fetching station ID {station_id}: {e}")
        return None

    return None

async def get_station_by_objectid(object_id_str: str) -> Optional[Station]:
    """
    Finds a single station by its MongoDB native _id field (ObjectId).
    Use this if your Flutter app passes the full ObjectId string.
    """
    if not db:
        return None

    collection = db[COLLECTION_NAME]

    try:
        # Convert the string to a proper ObjectId before querying
        mongo_object_id = ObjectId(object_id_str)

        # QUERY: Find by the '_id' field
        document = await collection.find_one({"_id": mongo_object_id})

        if document:
            return Station.model_validate(document)

    except Exception as e:
        print(f"Error fetching station by ObjectId {object_id_str}: {e}")
        return None

    return None