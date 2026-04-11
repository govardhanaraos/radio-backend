import uuid
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from db.db import get_pg_pool
from auth.dependencies import verify_admin_token
import json as py_json

router = APIRouter(prefix="/app-settings", tags=["App Settings"])

def _generate_id():
    return uuid.uuid4().hex[:24]

def _reconstruct_doc(row):
    d = dict(row)
    cdata = d.get("config_data")
    if isinstance(cdata, str):
        cdata = py_json.loads(cdata)
    elif cdata is None:
        cdata = {}
    return {**cdata, "id": d["id"], "config_name": d["config_name"]}

@router.get("/", summary="Get all App Settings")
async def get_app_settings():
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM app_settings ORDER BY id DESC LIMIT 100")
            return [_reconstruct_doc(row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/", summary="Create a new App Setting", dependencies=[Depends(verify_admin_token)])
async def create_app_setting(setting: Dict[Any, Any]):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        setting.pop('id', None)
        setting.pop('_id', None)
        new_id = _generate_id()
        config_name = setting.pop('config_name', 'unknown')
        config_data = py_json.dumps(setting)
        
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO app_settings (id, config_name, config_data)
                VALUES ($1, $2, $3)
            """, new_id, config_name, config_data)
            
            row = await conn.fetchrow("SELECT * FROM app_settings WHERE id = $1", new_id)
            return _reconstruct_doc(row)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.put("/{setting_id}", summary="Update an existing App Setting", dependencies=[Depends(verify_admin_token)])
async def update_app_setting(setting_id: str, setting: Dict[Any, Any]):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        setting.pop('id', None)
        setting.pop('_id', None)
        config_name = setting.pop('config_name', 'unknown')
        config_data = py_json.dumps(setting)
        
        async with pool.acquire() as conn:
            exists = await conn.fetchval("SELECT 1 FROM app_settings WHERE id = $1", setting_id)
            if not exists:
                raise HTTPException(status_code=404, detail="App Setting not found.")
                
            await conn.execute("""
                UPDATE app_settings 
                SET config_name = $1, config_data = $2
                WHERE id = $3
            """, config_name, config_data, setting_id)
            
            row = await conn.fetchrow("SELECT * FROM app_settings WHERE id = $1", setting_id)
            return _reconstruct_doc(row)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.delete("/{setting_id}", summary="Delete an App Setting", dependencies=[Depends(verify_admin_token)])
async def delete_app_setting(setting_id: str):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM app_settings WHERE id = $1", setting_id)
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="App Setting not found")
        return {"success": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
