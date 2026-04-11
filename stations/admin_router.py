import uuid
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from db.db import get_pg_pool
from auth.dependencies import verify_admin_token

router = APIRouter(prefix="/admin-stations", tags=["Admin Stations"], dependencies=[Depends(verify_admin_token)])

def _generate_id():
    return uuid.uuid4().hex[:24]

# ---- Radio Stations (App Default) endpoints ----

@router.get("/radio-stations", summary="Get all regular Radio Stations")
async def get_radio_stations():
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM radio_stations ORDER BY id DESC LIMIT 3000")
            return [dict(row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/radio-stations", summary="Create a new Radio Station")
async def create_radio_station(station: Dict[Any, Any]):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        new_id = _generate_id()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO radio_stations (id, station_id, name, logo_url, stream_url, language, genre, page)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, new_id, station.get("station_id") or station.get("id"), station.get("name"), 
                 station.get("logoUrl") or station.get("logo_url"), 
                 station.get("streamUrl") or station.get("stream_url"), 
                 station.get("language"), station.get("genre"), station.get("page"))
            
            row = await conn.fetchrow("SELECT * FROM radio_stations WHERE id = $1", new_id)
            return dict(row)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.put("/radio-stations/{station_id}", summary="Update a Radio Station")
async def update_radio_station(station_id: str, station: Dict[Any, Any]):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            exists = await conn.fetchval("SELECT 1 FROM radio_stations WHERE id = $1", station_id)
            if not exists:
                raise HTTPException(status_code=404, detail="Station not found.")
                
            await conn.execute("""
                UPDATE radio_stations 
                SET station_id = $1, name = $2, logo_url = $3, stream_url = $4, language = $5, genre = $6, page = $7
                WHERE id = $8
            """, station.get("station_id") or station.get("id"), station.get("name"), 
                 station.get("logoUrl") or station.get("logo_url"), 
                 station.get("streamUrl") or station.get("stream_url"), 
                 station.get("language"), station.get("genre"), station.get("page"), station_id)
            
            row = await conn.fetchrow("SELECT * FROM radio_stations WHERE id = $1", station_id)
            return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.delete("/radio-stations/{station_id}", summary="Delete a Radio Station")
async def delete_radio_station(station_id: str):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM radio_stations WHERE id = $1", station_id)
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="Station not found.")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# ---- Radio Garden Channels endpoints ----

@router.get("/radio-garden", summary="Get all Radio Garden Stations")
async def get_radio_garden_stations():
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM radio_garden_channels ORDER BY id DESC LIMIT 3000")
            return [dict(row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/radio-garden", summary="Create a new Radio Garden Station")
async def create_radio_garden(station: Dict[Any, Any]):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        new_id = _generate_id()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO radio_garden_channels (id, radio_garden_id, country, genre, channel_id, language, logo_url, name, page, state, stream_url)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """, new_id, station.get("radio_garden_id"), station.get("country"), station.get("genre"), 
                 station.get("channel_id") or station.get("id"), station.get("language"), 
                 station.get("logoUrl") or station.get("logo_url"), station.get("name"), 
                 station.get("page"), station.get("state"), station.get("streamUrl") or station.get("stream_url"))
            
            row = await conn.fetchrow("SELECT * FROM radio_garden_channels WHERE id = $1", new_id)
            return dict(row)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.put("/radio-garden/{station_id}", summary="Update a Radio Garden Station")
async def update_radio_garden(station_id: str, station: Dict[Any, Any]):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            exists = await conn.fetchval("SELECT 1 FROM radio_garden_channels WHERE id = $1", station_id)
            if not exists:
                raise HTTPException(status_code=404, detail="Station not found.")
                
            await conn.execute("""
                UPDATE radio_garden_channels 
                SET radio_garden_id = $1, country = $2, genre = $3, channel_id = $4, language = $5, logo_url = $6, name = $7, page = $8, state = $9, stream_url = $10
                WHERE id = $11
            """, station.get("radio_garden_id"), station.get("country"), station.get("genre"), 
                 station.get("channel_id") or station.get("id"), station.get("language"), 
                 station.get("logoUrl") or station.get("logo_url"), station.get("name"), 
                 station.get("page"), station.get("state"), station.get("streamUrl") or station.get("stream_url"), station_id)
            
            row = await conn.fetchrow("SELECT * FROM radio_garden_channels WHERE id = $1", station_id)
            return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.delete("/radio-garden/{station_id}", summary="Delete a Radio Garden Station")
async def delete_radio_garden(station_id: str):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM radio_garden_channels WHERE id = $1", station_id)
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="Station not found.")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
