from fastapi import APIRouter, HTTPException
from db.db import get_db

router = APIRouter()

@router.get("/appconfig")
async def get_app_config():
    try:
        db = get_db()
        if db is None:
            raise HTTPException(status_code=503, detail="Database connection failed.")
        collection = db["app_parameters"]

        cursor = collection.find({})
        params = {}

        async for doc in cursor:
            params[doc["parameter_code"]] = doc.get("value")

        return {"status": "success", "config": params}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))