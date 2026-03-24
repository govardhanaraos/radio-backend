from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from db.db import get_db

"""
python_api_download_screen_config.py

FastAPI router + Pydantic models for the MP3 Download Screen remote config.

Mount in your main app with:
    from python_api_download_screen_config import router as download_screen_router
    app.include_router(download_screen_router)

MongoDB collection:  app_parameters
Document identifier: { "config_key": "download_screen" }

──────────────────────────────────────────────────────────────────────────────
Sample MongoDB document
──────────────────────────────────────────────────────────────────────────────

{
  "config_key": "download_screen",

  // ── Language selector chips ──────────────────────────────────────────────
  "languages_enabled": true,
  "languages": [
    { "label": "Telugu", "value": "Telugu" },
    { "label": "Hindi",  "value": "Hindi"  },
    { "label": "Tamil",  "value": "Tamil"  }
  ],

  // ── Content-type tiles ───────────────────────────────────────────────────
  // Valid icon values: music_note | movie | album | mic | library_music |
  //                    headphones | queue_music | piano | star | favorite
  "content_types_enabled": true,
  "content_types": [
    { "label": "Song",   "value": "Song",   "icon": "music_note" },
    { "label": "Movie",  "value": "Movie",  "icon": "movie"      },
    { "label": "Album",  "value": "Album",  "icon": "album"      },
    { "label": "Artist", "value": "Artist", "icon": "mic"        }
  ],

  // ── Search section ───────────────────────────────────────────────────────
  // NOTE: No explicit flag — search is visible automatically when BOTH
  // languages_enabled=true AND languages is non-empty
  // AND content_types_enabled=true AND content_types is non-empty.
  // To hide search: set languages_enabled=false or content_types_enabled=false.

  // ── Browse-by-album grid ─────────────────────────────────────────────────
  "browse_by_album_enabled": true,
  "album_entries": [
    {
      "label":    "Telugu",
      "lang":     "telugu",
      "base_url": "https://example.com/telugu",
      "icon":     "library_music",
      "color_a":  "#7C4DFF",
      "color_b":  "#9C6FFF",
      "enabled":  true
    },
    {
      "label":    "Tamil",
      "lang":     "tamil",
      "base_url": "https://example.com/tamil",
      "icon":     "library_music",
      "color_a":  "#E91E63",
      "color_b":  "#FF5722",
      "enabled":  true
    },
    {
      "label":    "Hindi",
      "lang":     "hindi",
      "base_url": "https://example.com/hindi",
      "icon":     "library_music",
      "color_a":  "#FF6D00",
      "color_b":  "#FF9800",
      "enabled":  true
    },
    {
      "label":    "Malayalam",
      "lang":     "malayalam",
      "base_url": "https://example.com/malayalam",
      "icon":     "library_music",
      "color_a":  "#00897B",
      "color_b":  "#26C6DA",
      "enabled":  false
    }
  ],

  // ── Old MP3 archive button ───────────────────────────────────────────────
  "old_archive_enabled": true
}

──────────────────────────────────────────────────────────────────────────────
Ad config document (separate collection: analytics / screen: "mp3_download")
──────────────────────────────────────────────────────────────────────────────

{
  "screen":                   "mp3_download",
  "ads_enabled":              true,
  "banner_enabled":           true,
  "interstitial_enabled":     true,
  "interstitial_every_n_taps": 5,
  "inlist_enabled":           false,
  "mp3_list":        { "enabled": false },
  "downloads_list":  { "enabled": false },
  "recordings_list": { "enabled": false }
}

Note: The Library screen (Music / Downloads / Recordings tabs) uses
      screen: "player" — a separate document.
"""


router = APIRouter(prefix="/appconfig", tags=["App Config"])

# ── Pydantic models ────────────────────────────────────────────────────────────

class LangOption(BaseModel):
    label: str
    value: str


class ContentTypeOption(BaseModel):
    label: str
    value: str
    icon: str = "music_note"  # Must match an icon key the Flutter app recognises


class AlbumBrowseEntry(BaseModel):
    label:    str
    lang:     str           # Key passed to AlbumListPage
    base_url: str           # URL for OldMp3Browser fallback
    icon:     str  = "library_music"
    color_a:  str  = "#7C4DFF"  # Hex string, e.g. "#7C4DFF"
    color_b:  str  = "#448AFF"
    enabled:  bool = True


class DownloadScreenConfig(BaseModel):
    # ── Language chips ─────────────────────────────────────────────────────
    languages_enabled: bool = True
    languages: List[LangOption] = Field(default_factory=list)

    # ── Content-type tiles ─────────────────────────────────────────────────
    content_types_enabled: bool = True
    content_types: List[ContentTypeOption] = Field(default_factory=list)

    # ── Browse by album ────────────────────────────────────────────────────
    browse_by_album_enabled: bool = True
    album_entries: List[AlbumBrowseEntry] = Field(default_factory=list)

    # ── Old archive button ─────────────────────────────────────────────────
    old_archive_enabled: bool = True

    # ── Search visibility rule (informational — not stored) ────────────────
    # Visible when: languages_enabled=true AND languages non-empty
    #               AND content_types_enabled=true AND content_types non-empty.


class AppUpdateConfig(BaseModel):
    """
    App update configuration stored in `app_parameters` collection.
    The document is identified by `parameter_code`.
    """

    app_update_enabled: bool = False
    app_update_version: str = ""
    app_update_url: str = ""


# ── Router ─────────────────────────────────────────────────────────────────────


@router.get(
    "/download-screen",
    response_model=DownloadScreenConfig,
    summary="Get MP3 Download Screen configuration",
    description=(
        "Returns the full display configuration for the MP3 Download screen: "
        "language chips, content-type tiles, browse-by-album entries "
        "(each with enabled flag, icon, gradient colours and base URL), "
        "and the old-archive button flag. "
        "The search section is shown on the client when both language and "
        "content-type sections are enabled and non-empty."
    ),
)
async def get_download_screen_config():
    db = get_db()
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database not connected. Check MongoDB connection on startup.",
        )
    try:
        doc = await db["app_parameters"].find_one(
            {"config_key": "download_screen"},
            {"_id": 0},  # Exclude MongoDB _id from response
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"MongoDB query failed: {exc}",
        )
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail="No document found with config_key='download_screen' in app_config collection.",
        )
    # Strip extra fields not in the Pydantic model (e.g. parameter_code)
    for extra_field in ("parameter_code", "config_key"):
        doc.pop(extra_field, None)
    try:
        return DownloadScreenConfig(**doc)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"DB document found but failed to parse into DownloadScreenConfig: {exc}",
        )


@router.put(
    "/download-screen",
    response_model=DownloadScreenConfig,
    summary="Upsert MP3 Download Screen configuration",
    description=(
        "Creates or fully replaces the download screen config document. "
        "Use this from your admin panel to enable/disable sections, "
        "add/remove languages, content types, or album browse entries."
    ),
)
async def upsert_download_screen_config(config: DownloadScreenConfig):
    db = get_db()
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database not connected. Check MongoDB connection on startup.",
        )
    try:
        doc = config.model_dump()
        doc["config_key"] = "download_screen"
        await db["app_parameters"].replace_one(
            {"config_key": "download_screen"},
            doc,
            upsert=True,
        )
        return config
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save download screen config: {exc}",
        )


@router.patch(
    "/download-screen/album-entry/{lang}",
    response_model=DownloadScreenConfig,
    summary="Enable or disable a single album browse entry",
    description=(
        "Toggles the enabled flag for the album entry matching the given "
        "lang key (e.g. 'telugu', 'hindi').  All other fields are unchanged."
    ),
)
async def patch_album_entry_enabled(lang: str, enabled: bool):
    db = get_db()
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database not connected. Check MongoDB connection on startup.",
        )
    try:
        result = await db["app_parameters"].update_one(
            {
                "config_key": "download_screen",
                "album_entries.lang": lang,
            },
            {"$set": {"album_entries.$.enabled": enabled}},
        )
        if result.matched_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No album entry found with lang='{lang}'",
            )
        doc = await db["app_parameters"].find_one(
            {"config_key": "download_screen"}, {"_id": 0}
        )
        for extra_field in ("parameter_code", "config_key"):
            doc.pop(extra_field, None)
        return DownloadScreenConfig(**doc)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))



@router.get("/availableupdate")
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


@router.put("/availableupdate", summary="Update App Update parameters")
async def upsert_app_update_config(config: AppUpdateConfig):
    """
    Updates the `app_update_*` records in `app_parameters`, matched by `parameter_code`.
    """

    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection failed.")

    try:
        enabled_value = "true" if config.app_update_enabled else "false"
        updates: Dict[str, Any] = {
            "app_update_enabled": enabled_value,
            "app_update_version": config.app_update_version,
            "app_update_url": config.app_update_url,
        }

        collection = db["app_parameters"]
        for parameter_code, value in updates.items():
            await collection.update_one(
                {"parameter_code": parameter_code},
                {"$set": {"value": value}},
                upsert=True,
            )

        return {"status": "success", "config": updates}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

