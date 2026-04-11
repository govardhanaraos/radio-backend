import uuid
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from db.db import get_pg_pool
from auth.dependencies import verify_admin_token
import json as py_json

router = APIRouter(prefix="/premium-users-admin", tags=["Premium Users Admin"], dependencies=[Depends(verify_admin_token)])

def _generate_id():
    return uuid.uuid4().hex[:24]

@router.get("/", summary="Get all Premium Users")
async def get_premium_users():
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM premium_users ORDER BY id DESC LIMIT 500")
            out = []
            for row in rows:
                d = dict(row)
                if isinstance(d.get("created_at"), str) is False and d.get("created_at") is not None:
                    d["created_at"] = str(d["created_at"])
                if isinstance(d.get("active_devices"), str):
                    d["active_devices"] = py_json.loads(d["active_devices"])
                out.append(d)
            return out
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/", summary="Create a new Premium User license")
async def create_premium_user(user: Dict[Any, Any]):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        new_id = _generate_id()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO premium_users (id, plain_key, license_key, active_devices, created_at)
                VALUES ($1, $2, $3, $4, $5)
            """, new_id, user.get("plain_key"), user.get("license_key"), py_json.dumps(user.get("active_devices", [])), user.get("created_at"))
            row = await conn.fetchrow("SELECT * FROM premium_users WHERE id = $1", new_id)
            d = dict(row)
            d["active_devices"] = py_json.loads(d["active_devices"]) if isinstance(d.get("active_devices"), str) else []
            if d.get("created_at"):
                d["created_at"] = str(d["created_at"])
            return d
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.put("/{user_id}", summary="Update an existing Premium User")
async def update_premium_user(user_id: str, user: Dict[Any, Any]):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            exists = await conn.fetchval("SELECT 1 FROM premium_users WHERE id = $1", user_id)
            if not exists:
                raise HTTPException(status_code=404, detail="Premium User not found.")
            await conn.execute("""
                UPDATE premium_users 
                SET plain_key = $1, license_key = $2, active_devices = $3
                WHERE id = $4
            """, user.get("plain_key"), user.get("license_key"), py_json.dumps(user.get("active_devices", [])), user_id)
            
            row = await conn.fetchrow("SELECT * FROM premium_users WHERE id = $1", user_id)
            d = dict(row)
            d["active_devices"] = py_json.loads(d["active_devices"]) if isinstance(d.get("active_devices"), str) else []
            if d.get("created_at"):
                d["created_at"] = str(d["created_at"])
            return d
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.delete("/{user_id}", summary="Delete a Premium User")
async def delete_premium_user(user_id: str):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM premium_users WHERE id = $1", user_id)
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="Premium User not found")
        return {"success": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
