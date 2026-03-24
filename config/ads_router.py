from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from db.db import get_db
from bson import ObjectId
from auth.dependencies import verify_admin_token
from config.ads_config_normalize import (
    sanitize_ads_document_for_storage,
    replace_sanitized_ads_doc,
)
from stations.analytics_router import invalidate_ads_config_cache

router = APIRouter(prefix="/ads-config", tags=["Ads Config"])


def format_doc(doc):
    if not doc:
        return doc
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


@router.get("/", summary="Get all Ads Configurations")
async def get_ads_configs():
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        cursor = db["ads_config"].find({})
        docs = await cursor.to_list(length=100)
        out = []
        for doc in docs:
            oid = doc["_id"]
            sanitized = sanitize_ads_document_for_storage(doc)
            sanitized["_id"] = oid
            out.append(format_doc(sanitized))
        return out
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/normalize-all",
    summary="Rewrite all ads_config docs to per-screen list layout (strip invalid list keys)",
    dependencies=[Depends(verify_admin_token)],
)
async def normalize_all_ads_configs():
    """One-shot cleanup after changing layout rules."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        cursor = db["ads_config"].find({})
        n = 0
        async for doc in cursor:
            oid = doc["_id"]
            sanitized = sanitize_ads_document_for_storage(doc)
            await replace_sanitized_ads_doc(db, oid, sanitized)
            screen = sanitized.get("screen")
            await invalidate_ads_config_cache(screen)
            n += 1
        return {"normalized": n}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/", summary="Create a new Ads Configuration", dependencies=[Depends(verify_admin_token)])
async def create_ads_config(config: Dict[Any, Any]):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        config.pop("id", None)
        config.pop("_id", None)
        result = await db["ads_config"].insert_one(config)
        new_doc = await db["ads_config"].find_one({"_id": result.inserted_id})
        oid = result.inserted_id
        sanitized = sanitize_ads_document_for_storage(new_doc)
        await replace_sanitized_ads_doc(db, oid, sanitized)
        final = await db["ads_config"].find_one({"_id": oid})
        screen = sanitized.get("screen")
        await invalidate_ads_config_cache(screen)
        return format_doc(final)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/{config_id}", summary="Update an existing Ads Configuration", dependencies=[Depends(verify_admin_token)])
async def update_ads_config(config_id: str, config: Dict[Any, Any]):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        oid = ObjectId(config_id)
        existing = await db["ads_config"].find_one({"_id": oid})
        if not existing:
            raise HTTPException(status_code=404, detail="Ads configuration not found.")

        patch = dict(config)
        patch.pop("id", None)
        patch.pop("_id", None)

        merged = {**existing, **patch}
        merged.pop("_id", None)

        sanitized = sanitize_ads_document_for_storage(merged)
        await replace_sanitized_ads_doc(db, oid, sanitized)

        final = await db["ads_config"].find_one({"_id": oid})
        screen = final.get("screen")
        await invalidate_ads_config_cache(screen)
        return format_doc(final)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{config_id}", summary="Delete an Ads Configuration", dependencies=[Depends(verify_admin_token)])
async def delete_ads_config(config_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        oid = ObjectId(config_id)
        doc = await db["ads_config"].find_one({"_id": oid})
        result = await db["ads_config"].delete_one({"_id": oid})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Ads configuration not found")
        if doc:
            await invalidate_ads_config_cache(doc.get("screen"))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
