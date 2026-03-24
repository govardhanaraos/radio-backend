from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from db.db import get_db
from bson import ObjectId
from auth.dependencies import verify_admin_token

router = APIRouter(prefix="/premium-users-admin", tags=["Premium Users Admin"], dependencies=[Depends(verify_admin_token)])

def format_doc(doc):
    if not doc:
        return doc
    doc['id'] = str(doc['_id'])
    del doc['_id']
    
    if "created_at" in doc and hasattr(doc["created_at"], "isoformat"):
        doc["created_at"] = doc["created_at"].isoformat()
    return doc

@router.get("/", summary="Get all Premium Users")
async def get_premium_users():
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        cursor = db["premium_users"].find({})
        docs = await cursor.to_list(length=500)
        return [format_doc(doc) for doc in docs]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/", summary="Create a new Premium User license")
async def create_premium_user(user: Dict[Any, Any]):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        user.pop('id', None)
        user.pop('_id', None)
        result = await db["premium_users"].insert_one(user)
        new_doc = await db["premium_users"].find_one({"_id": result.inserted_id})
        return format_doc(new_doc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.put("/{user_id}", summary="Update an existing Premium User")
async def update_premium_user(user_id: str, user: Dict[Any, Any]):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        user.pop('id', None)
        user.pop('_id', None)
        # Prevent wiping created_at if it's sent as string
        if "created_at" in user and isinstance(user["created_at"], str):
             user.pop("created_at")

        result = await db["premium_users"].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": user}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Premium User not found.")
        updated_doc = await db["premium_users"].find_one({"_id": ObjectId(user_id)})
        return format_doc(updated_doc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.delete("/{user_id}", summary="Delete a Premium User")
async def delete_premium_user(user_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected.")
    try:
        result = await db["premium_users"].delete_one({"_id": ObjectId(user_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Premium User not found")
        return {"success": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
