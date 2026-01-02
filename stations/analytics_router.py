from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from db.db import get_db
from db.redis_config import r_async, CACHE_TTL
import orjson

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)

# --- Pydantic Models ---
class AdsConfig(BaseModel):
    screen: str
    ads_enabled: bool

class GlobalAdsConfig(BaseModel):
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
@router.get("/config/global", response_model=GlobalAdsConfig)
async def get_global_ads_status():
    """
    Fetch the global ads status from cache or database.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")

    global_cache_key = "ads_config:global"
    global_ads = None

    # 1. Attempt to fetch from Redis cache
    if r_async is not None:
        try:
            cached_global = await r_async.get(global_cache_key)
            if cached_global:
                global_ads = orjson.loads(cached_global)
        except Exception as e:
            print(f"⚠️ Redis read error: {e}")

    # 2. If not in cache, fetch from MongoDB app_config collection
    if not global_ads:
        global_doc = await db["ads_config"].find_one({}, {"_id": 0})
        if not global_doc:
            raise HTTPException(status_code=404, detail="Global ads config not found.")

        global_ads = global_doc

        # 3. Store in Redis for future requests
        if r_async is not None:
            try:
                await r_async.set(global_cache_key, orjson.dumps(global_ads), ex=CACHE_TTL)
            except Exception as e:
                print(f"⚠️ Redis write error: {e}")

    return global_ads

@router.get("/ads/{screen}", response_model=AdsConfig)
async def get_ads_config(screen: str):
    """
    Fetch ads configuration for a given screen.
    If global ads are disabled, return ads_enabled=False immediately.
    Otherwise check screen-level config with Redis caching.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")

    # 1. Check global ads config
    global_cache_key = "ads_config:global"
    global_ads = None

    if r_async is not None:
        try:
            cached_global = await r_async.get(global_cache_key)
            if cached_global:
                global_ads = orjson.loads(cached_global)
        except Exception as e:
            print(f"⚠️ Redis read error for global ads: {e}")

    if not global_ads:
        global_doc = await db["ads_config"].find_one({}, {"_id": 0})
        if not global_doc:
            raise HTTPException(status_code=404, detail="Global ads config not found.")
        global_ads = global_doc
        if r_async is not None:
            try:
                await r_async.set(global_cache_key, orjson.dumps(global_ads), ex=CACHE_TTL)
            except Exception as e:
                print(f"⚠️ Redis write error for global ads: {e}")

    # 2. If global ads disabled → skip screen check
    if not global_ads.get("ads_enabled", False):
        return {"screen": screen, "ads_enabled": False}

    # 3. Screen-level ads config
    cache_key = f"ads_config:{screen}"
    if r_async is not None:
        try:
            cached_data = await r_async.get(cache_key)
            if cached_data:
                print(f"🚀 Cache Hit: Ads config for {screen}")
                return orjson.loads(cached_data)
        except Exception as e:
            print(f"⚠️ Redis read error, falling back to DB: {e}")

    ads_doc = await db["ads_config"].find_one({"screen": screen}, {"_id": 0})
    if not ads_doc:
        raise HTTPException(status_code=404, detail="Ads config not found.")

    if r_async is not None:
        try:
            await r_async.set(cache_key, orjson.dumps(ads_doc), ex=CACHE_TTL)
            print(f"💾 Cache Miss: Stored ads config for {screen}")
        except Exception as e:
            print(f"⚠️ Redis write error: {e}")

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