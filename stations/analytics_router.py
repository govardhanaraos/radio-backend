from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from db.db import get_db
from db.redis_config import r_async, CACHE_TTL
import orjson

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────

class GlobalAdsConfig(BaseModel):
    """
    Master switch stored in ads_config collection as the document
    that has NO 'screen' field (i.e. the global document).

    MongoDB document shape:
    {
        "ads_enabled": true
    }
    """
    ads_enabled: bool


class InListAdPlacement(BaseModel):
    """
    Controls where in-list (native in-feed) ads appear inside a list.

    Fields
    ------
    enabled          : Whether in-list ads are active for this list.
    every_n_items    : Insert an ad tile after every N content rows.
                       e.g. 6 → ad after row 6, 12, 18 …
    first_ad_position: Override the index of the very first ad tile.
                       Useful if you want the first ad to appear earlier
                       or later than `every_n_items` would place it.
                       0 means "use every_n_items for the first ad too".
    max_ads          : Cap the total number of ad tiles in the list.
                       0 means unlimited.
    """
    enabled: bool = False
    every_n_items: int = Field(default=6, ge=1)
    first_ad_position: int = Field(default=0, ge=0)
    max_ads: int = Field(default=0, ge=0)


class ScreenAdsConfig(BaseModel):
    """
    Per-screen ads config returned by GET /analytics/ads/{screen}.

    The four list keys (stations_list, mp3_list, downloads_list,
    recordings_list) each carry their own InListAdPlacement block so
    every list inside a single screen can be tuned independently.

    MongoDB document shape (example for 'radio' screen):
    {
        "screen": "radio",
        "ads_enabled": true,
        "banner_enabled": true,
        "interstitial_enabled": false,
        "interstitial_every_n_taps": 5,
        "inlist_enabled": true,
        "stations_list": {
            "enabled": true,
            "every_n_items": 6,
            "first_ad_position": 0,
            "max_ads": 0
        },
        "mp3_list": {
            "enabled": false,
            "every_n_items": 8,
            "first_ad_position": 0,
            "max_ads": 3
        },
        "downloads_list": {
            "enabled": false,
            "every_n_items": 6,
            "first_ad_position": 0,
            "max_ads": 0
        },
        "recordings_list": {
            "enabled": false,
            "every_n_items": 6,
            "first_ad_position": 0,
            "max_ads": 0
        }
    }
    """
    screen: str

    # ── Top-level ad type flags ───────────────────────────────────────────────
    ads_enabled: bool = False
    banner_enabled: bool = False

    # Interstitial: shown at natural break-points (e.g. every N station taps).
    interstitial_enabled: bool = False
    interstitial_every_n_taps: int = Field(default=5, ge=1)

    # Master in-list toggle — individual list blocks below are only respected
    # when this is also True.
    inlist_enabled: bool = False

    # ── Per-list in-list placement config ─────────────────────────────────────
    stations_list:   InListAdPlacement = Field(default_factory=InListAdPlacement)
    mp3_list:        InListAdPlacement = Field(default_factory=InListAdPlacement)
    downloads_list:  InListAdPlacement = Field(default_factory=InListAdPlacement)
    recordings_list: InListAdPlacement = Field(default_factory=InListAdPlacement)


class AdsConfigUpsert(BaseModel):
    """
    Request body for PUT /analytics/ads/{screen} (admin upsert).
    All fields are optional so callers can patch only what they need.
    """
    ads_enabled: Optional[bool] = None
    banner_enabled: Optional[bool] = None
    interstitial_enabled: Optional[bool] = None
    interstitial_every_n_taps: Optional[int] = Field(default=None, ge=1)
    inlist_enabled: Optional[bool] = None
    stations_list:   Optional[InListAdPlacement] = None
    mp3_list:        Optional[InListAdPlacement] = None
    downloads_list:  Optional[InListAdPlacement] = None
    recordings_list: Optional[InListAdPlacement] = None


class GlobalAdsConfigUpsert(BaseModel):
    """Request body for PUT /analytics/config/global (admin upsert)."""
    ads_enabled: bool


class DeviceRegistration(BaseModel):
    deviceId: str
    platform: Optional[str] = None


class LogEntry(BaseModel):
    deviceId: str
    event: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_global_ads(db) -> dict:
    """
    Return the global ads document, preferring Redis cache.
    Raises HTTP 404 if the document does not exist in MongoDB.
    """
    global_cache_key = "ads_config:global"

    if r_async is not None:
        try:
            cached = await r_async.get(global_cache_key)
            if cached:
                return orjson.loads(cached)
        except Exception as e:
            print(f"⚠️ Redis read error (global): {e}")

    doc = await db["ads_config"].find_one({"screen": {"$exists": False}}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Global ads config not found.")

    if r_async is not None:
        try:
            await r_async.set(global_cache_key, orjson.dumps(doc), ex=CACHE_TTL)
        except Exception as e:
            print(f"⚠️ Redis write error (global): {e}")

    return doc


async def _invalidate_cache(key: str):
    """Delete a single Redis key, swallowing errors."""
    if r_async is not None:
        try:
            await r_async.delete(key)
        except Exception as e:
            print(f"⚠️ Redis delete error ({key}): {e}")


# ─────────────────────────────────────────────────────────────────────────────
# READ endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/config/global", response_model=GlobalAdsConfig)
async def get_global_ads_status():
    """
    Fetch the global ads master-switch.

    Response
    --------
    { "ads_enabled": true }
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")

    return await _get_global_ads(db)


@router.get("/ads/{screen}", response_model=ScreenAdsConfig)
async def get_ads_config(screen: str):
    """
    Fetch full ads configuration for a given screen.

    Logic
    -----
    1. Read global ads flag (Redis → MongoDB).
    2. If global is disabled → return a fully-disabled config immediately
       (no DB round-trip for the screen document).
    3. Otherwise read the screen document (Redis → MongoDB) and return it.

    Response includes per-ad-type flags AND per-list in-list placement
    numbers (every_n_items, first_ad_position, max_ads) for all four
    list types: stations, mp3, downloads, recordings.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")

    # ── Step 1: global check ─────────────────────────────────────────────────
    global_ads = await _get_global_ads(db)

    if not global_ads.get("ads_enabled", False):
        # Return fully-disabled config — no need to hit the screen document.
        return ScreenAdsConfig(screen=screen)

    # ── Step 2: screen-level config ──────────────────────────────────────────
    cache_key = f"ads_config:{screen}"

    if r_async is not None:
        try:
            cached = await r_async.get(cache_key)
            if cached:
                print(f"🚀 Cache Hit: ads config for '{screen}'")
                return ScreenAdsConfig(**orjson.loads(cached))
        except Exception as e:
            print(f"⚠️ Redis read error ({screen}), falling back to DB: {e}")

    ads_doc = await db["ads_config"].find_one({"screen": screen}, {"_id": 0})
    if not ads_doc:
        raise HTTPException(
            status_code=404,
            detail=f"Ads config for screen '{screen}' not found."
        )

    if r_async is not None:
        try:
            await r_async.set(cache_key, orjson.dumps(ads_doc), ex=CACHE_TTL)
            print(f"💾 Cache Miss: stored ads config for '{screen}'")
        except Exception as e:
            print(f"⚠️ Redis write error ({screen}): {e}")

    return ScreenAdsConfig(**ads_doc)


# ─────────────────────────────────────────────────────────────────────────────
# WRITE endpoints  (admin / management use)
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/config/global", response_model=GlobalAdsConfig)
async def upsert_global_ads_config(payload: GlobalAdsConfigUpsert):
    """
    Create or update the global ads master-switch.

    Also invalidates the Redis cache so the next GET sees the new value
    immediately without waiting for TTL expiry.

    Request body
    ------------
    { "ads_enabled": true }
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")

    update_doc = {"ads_enabled": payload.ads_enabled}

    await db["ads_config"].update_one(
        {"screen": {"$exists": False}},   # match the global document
        {"$set": update_doc},
        upsert=True,
    )

    await _invalidate_cache("ads_config:global")

    return update_doc


@router.put("/ads/{screen}", response_model=ScreenAdsConfig)
async def upsert_screen_ads_config(screen: str, payload: AdsConfigUpsert):
    """
    Create or update the ads configuration for a specific screen.

    Only fields present in the request body are written — absent fields
    keep their existing database values (partial update / PATCH semantics
    implemented via $set).

    Invalidates the Redis cache for the screen on success.

    Supported screens (by convention): radio, player, mp3_download
    Any screen name is accepted; unknown names are created on first call.

    Example request body for the 'radio' screen
    --------------------------------------------
    {
        "ads_enabled": true,
        "banner_enabled": true,
        "interstitial_enabled": true,
        "interstitial_every_n_taps": 5,
        "inlist_enabled": true,
        "stations_list": {
            "enabled": true,
            "every_n_items": 6,
            "first_ad_position": 3,
            "max_ads": 10
        },
        "mp3_list": {
            "enabled": true,
            "every_n_items": 8,
            "first_ad_position": 0,
            "max_ads": 3
        },
        "downloads_list": {
            "enabled": false,
            "every_n_items": 6,
            "first_ad_position": 0,
            "max_ads": 0
        },
        "recordings_list": {
            "enabled": false,
            "every_n_items": 6,
            "first_ad_position": 0,
            "max_ads": 0
        }
    }
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")

    # Build $set payload from only the provided (non-None) fields.
    set_fields: dict = {"screen": screen}

    payload_dict = payload.dict(exclude_none=True)
    for field, value in payload_dict.items():
        if isinstance(value, dict):
            # Flatten nested models (InListAdPlacement) into dot-notation keys
            # so we do a targeted update rather than overwriting the whole sub-doc.
            for sub_key, sub_val in value.items():
                set_fields[f"{field}.{sub_key}"] = sub_val
        else:
            set_fields[field] = value

    result = await db["ads_config"].find_one_and_update(
        {"screen": screen},
        {"$set": set_fields},
        upsert=True,
        return_document=True,  # pymongo ReturnDocument.AFTER equivalent in motor
    )

    # Invalidate Redis so the next GET reflects the update immediately.
    await _invalidate_cache(f"ads_config:{screen}")

    if result is None:
        raise HTTPException(status_code=500, detail="Upsert failed unexpectedly.")

    result.pop("_id", None)
    return ScreenAdsConfig(**result)


# ─────────────────────────────────────────────────────────────────────────────
# Device & Logging endpoints  (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/device/register")
async def register_device(device: DeviceRegistration):
    """Register a device ID in the database."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")

    existing = await db["devices"].find_one({"deviceId": device.deviceId})
    if existing:
        return {"message": "Device already registered."}

    await db["devices"].insert_one({
        "deviceId": device.deviceId,
        "platform": device.platform,
        "registeredAt": None,
    })
    return {"message": "Device registered successfully."}


@router.post("/log")
async def log_activity(log: LogEntry):
    """Store user activity logs in MongoDB."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")

    await db["logs"].insert_one(log.dict())
    return {"message": "Log stored successfully."}
