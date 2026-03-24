from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from db.db import get_db, COLLECTION_NAME, RADIO_GARDEN_CHANNELS_COLLECTION
from bson import ObjectId
from auth.dependencies import verify_admin_token

router = APIRouter(prefix="/admin-stations", tags=["Admin Stations"], dependencies=[Depends(verify_admin_token)])

def format_doc(doc):
    if not doc:
        return doc
    # We map _id to id_mongo to prevent collisions with the literal 'id' field in the doc
    doc['id_mongo'] = str(doc['_id'])
    del doc['_id']
    return doc

# ---- Radio Stations (App Default) endpoints ----

@router.get("/radio-stations", summary="Get all regular Radio Stations")
async def get_radio_stations():
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        cursor = db[COLLECTION_NAME].find({}).sort("_id", -1)
        docs = await cursor.to_list(length=3000)
        return [format_doc(doc) for doc in docs]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/radio-stations", summary="Create a new Radio Station")
async def create_radio_station(station: Dict[Any, Any]):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        station.pop('id_mongo', None)
        station.pop('_id', None)
        result = await db[COLLECTION_NAME].insert_one(station)
        new_doc = await db[COLLECTION_NAME].find_one({"_id": result.inserted_id})
        return format_doc(new_doc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.put("/radio-stations/{station_id}", summary="Update a Radio Station")
async def update_radio_station(station_id: str, station: Dict[Any, Any]):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        station.pop('id_mongo', None)
        station.pop('_id', None)
        result = await db[COLLECTION_NAME].update_one(
            {"_id": ObjectId(station_id)},
            {"$set": station}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Station not found.")
        updated_doc = await db[COLLECTION_NAME].find_one({"_id": ObjectId(station_id)})
        return format_doc(updated_doc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.delete("/radio-stations/{station_id}", summary="Delete a Radio Station")
async def delete_radio_station(station_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        result = await db[COLLECTION_NAME].delete_one({"_id": ObjectId(station_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Station not found.")
        return {"success": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# ---- Radio Garden Channels endpoints ----

@router.get("/radio-garden", summary="Get all Radio Garden Stations")
async def get_radio_garden_stations():
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        # NOTE: radio_garden_collection comes from environment variables
        if not RADIO_GARDEN_CHANNELS_COLLECTION:
             raise HTTPException(status_code=500, detail="RADIO_GARDEN_CHANNELS_COLLECTION not mapped.")
             
        cursor = db[RADIO_GARDEN_CHANNELS_COLLECTION].find({}).sort("_id", -1)
        docs = await cursor.to_list(length=3000)
        return [format_doc(doc) for doc in docs]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/radio-garden", summary="Create a new Radio Garden Station")
async def create_radio_garden(station: Dict[Any, Any]):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        station.pop('id_mongo', None)
        station.pop('_id', None)
        result = await db[RADIO_GARDEN_CHANNELS_COLLECTION].insert_one(station)
        new_doc = await db[RADIO_GARDEN_CHANNELS_COLLECTION].find_one({"_id": result.inserted_id})
        return format_doc(new_doc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.put("/radio-garden/{station_id}", summary="Update a Radio Garden Station")
async def update_radio_garden(station_id: str, station: Dict[Any, Any]):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        station.pop('id_mongo', None)
        station.pop('_id', None)
        result = await db[RADIO_GARDEN_CHANNELS_COLLECTION].update_one(
            {"_id": ObjectId(station_id)},
            {"$set": station}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Station not found.")
        updated_doc = await db[RADIO_GARDEN_CHANNELS_COLLECTION].find_one({"_id": ObjectId(station_id)})
        return format_doc(updated_doc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.delete("/radio-garden/{station_id}", summary="Delete a Radio Garden Station")
async def delete_radio_garden(station_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        result = await db[RADIO_GARDEN_CHANNELS_COLLECTION].delete_one({"_id": ObjectId(station_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Station not found.")
        return {"success": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
