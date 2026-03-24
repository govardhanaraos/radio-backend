from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from db.db import get_db
from bson import ObjectId
from auth.dependencies import verify_admin_token

router = APIRouter(prefix="/app-settings", tags=["App Settings"])

def format_doc(doc):
    if not doc:
        return doc
    doc['id'] = str(doc['_id'])
    del doc['_id']
    return doc

@router.get("/", summary="Get all App Settings")
async def get_app_settings():
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        cursor = db["app_settings"].find({})
        docs = await cursor.to_list(length=100)
        return [format_doc(doc) for doc in docs]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/", summary="Create a new App Setting", dependencies=[Depends(verify_admin_token)])
async def create_app_setting(setting: Dict[Any, Any]):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        setting.pop('id', None)
        setting.pop('_id', None)
        result = await db["app_settings"].insert_one(setting)
        new_doc = await db["app_settings"].find_one({"_id": result.inserted_id})
        return format_doc(new_doc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.put("/{setting_id}", summary="Update an existing App Setting", dependencies=[Depends(verify_admin_token)])
async def update_app_setting(setting_id: str, setting: Dict[Any, Any]):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        setting.pop('id', None)
        setting.pop('_id', None)
        result = await db["app_settings"].update_one(
            {"_id": ObjectId(setting_id)},
            {"$set": setting}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="App Setting not found.")
        updated_doc = await db["app_settings"].find_one({"_id": ObjectId(setting_id)})
        return format_doc(updated_doc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.delete("/{setting_id}", summary="Delete an App Setting", dependencies=[Depends(verify_admin_token)])
async def delete_app_setting(setting_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        result = await db["app_settings"].delete_one({"_id": ObjectId(setting_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="App Setting not found")
        return {"success": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
