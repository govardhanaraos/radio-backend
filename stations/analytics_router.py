from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from db.db import get_db

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)

# --- Pydantic Models ---
class AdsConfig(BaseModel):
    screen: str
    ads_enabled: bool

class DeviceRegistration(BaseModel):
    deviceId: str
    platform: Optional[str] = None

class LogEntry(BaseModel):
    deviceId: str
    event: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str


# --- Endpoints ---

@router.get("/ads/{screen}", response_model=AdsConfig)
async def get_ads_config(screen: str):
    """
    Fetch ads configuration for a given screen.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")

    ads_doc = await db["ads_config"].find_one({"screen": screen}, {"_id": 0})
    if not ads_doc:
        raise HTTPException(status_code=404, detail="Ads config not found.")
    return ads_doc


@router.post("/device/register")
async def register_device(device: DeviceRegistration):
    """
    Register a device ID in the database.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")

    existing = await db["devices"].find_one({"deviceId": device.deviceId})
    if existing:
        return {"message": "Device already registered."}

    await db["devices"].insert_one({
        "deviceId": device.deviceId,
        "platform": device.platform,
        "registeredAt": device.dict().get("registeredAt", None)
    })
    return {"message": "Device registered successfully."}


@router.post("/log")
async def log_activity(log: LogEntry):
    """
    Store user activity logs in MongoDB.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")

    await db["logs"].insert_one(log.dict())
    return {"message": "Log stored successfully."}