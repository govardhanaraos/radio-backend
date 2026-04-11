import uuid
import json as py_json
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from db.db import get_pg_pool
from auth.dependencies import verify_admin_token
from config.ads_config_normalize import (
    sanitize_ads_document_for_storage,
    replace_sanitized_ads_doc,
)
from stations.analytics_router import invalidate_ads_config_cache

router = APIRouter(prefix="/ads-config", tags=["Ads Config"])

def _generate_id():
    return uuid.uuid4().hex[:24]

def _reconstruct_doc(row):
    d = dict(row)
    cdata = d.get("ads_data")
    if isinstance(cdata, str):
        cdata = py_json.loads(cdata)
    elif cdata is None:
        cdata = {}
    return {**cdata, "id": d["id"], "screen": d["screen"]}

@router.get("/", summary="Get all Ads Configurations")
async def get_ads_configs():
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM ads_config ORDER BY id DESC LIMIT 100")
            out = []
            for row in rows:
                doc = _reconstruct_doc(row)
                sanitized = sanitize_ads_document_for_storage(doc)
                sanitized["id"] = doc["id"]
                out.append(sanitized)
            return out
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post(
    "/normalize-all",
    summary="Rewrite all ads_config docs to per-screen list layout",
    dependencies=[Depends(verify_admin_token)],
)
async def normalize_all_ads_configs():
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        n = 0
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM ads_config")
            for row in rows:
                doc = _reconstruct_doc(row)
                oid = doc["id"]
                sanitized = sanitize_ads_document_for_storage(doc)
                await replace_sanitized_ads_doc(pool, oid, sanitized)
                screen = sanitized.get("screen")
                await invalidate_ads_config_cache(screen)
                n += 1
        return {"normalized": n}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/", summary="Create a new Ads Configuration", dependencies=[Depends(verify_admin_token)])
async def create_ads_config(config: Dict[Any, Any]):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        config.pop("id", None)
        config.pop("_id", None)
        new_id = _generate_id()
        screen = config.pop("screen", "global")
        
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO ads_config (id, screen, ads_data)
                VALUES ($1, $2, $3)
            """, new_id, screen, py_json.dumps(config))
            
            row = await conn.fetchrow("SELECT * FROM ads_config WHERE id = $1", new_id)
            new_doc = _reconstruct_doc(row)
            
            sanitized = sanitize_ads_document_for_storage(new_doc)
            final = await replace_sanitized_ads_doc(pool, new_id, sanitized)
            screen_final = sanitized.get("screen")
            await invalidate_ads_config_cache(screen_final)
            return final
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.put("/{config_id}", summary="Update an existing Ads Configuration", dependencies=[Depends(verify_admin_token)])
async def update_ads_config(config_id: str, config: Dict[Any, Any]):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM ads_config WHERE id = $1", config_id)
            if not row:
                raise HTTPException(status_code=404, detail="Ads configuration not found.")
            existing = _reconstruct_doc(row)

        patch = dict(config)
        patch.pop("id", None)
        patch.pop("_id", None)

        merged = {**existing, **patch}

        sanitized = sanitize_ads_document_for_storage(merged)
        final = await replace_sanitized_ads_doc(pool, config_id, sanitized)
        screen = final.get("screen")
        await invalidate_ads_config_cache(screen)
        return final
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.delete("/{config_id}", summary="Delete an Ads Configuration", dependencies=[Depends(verify_admin_token)])
async def delete_ads_config(config_id: str):
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM ads_config WHERE id = $1", config_id)
            if row:
                doc = _reconstruct_doc(row)
                await conn.execute("DELETE FROM ads_config WHERE id = $1", config_id)
                await invalidate_ads_config_cache(doc.get("screen"))
                return {"success": True}
            raise HTTPException(status_code=404, detail="Ads configuration not found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
