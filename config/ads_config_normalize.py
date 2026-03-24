"""
Normalize `ads_config` documents by screen.

Storage (MongoDB): each screen keeps only the list-placement blocks that apply.
Analytics API: still returns all four list blocks (for Pydantic / existing clients);
  blocks that do not apply on a screen are forced to disabled defaults.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

LIST_KEYS = ("stations_list", "mp3_list", "downloads_list", "recordings_list")

# Defaults matching InListAdPlacement when a list is not used on a screen.
DISABLED_PLACEMENT: Dict[str, Any] = {
    "enabled": False,
    "every_n_items": 3,
    "first_ad_position": 0,
    "max_ads": 0,
}


def _without_id_fields(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc)
    out.pop("_id", None)
    out.pop("id", None)
    return out


def sanitize_ads_document_for_storage(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Drop list keys that must not exist for this document's screen.

    - radio: only stations_list
    - player: mp3_list, downloads_list, recordings_list (not stations_list)
    - mp3_download: no list blocks
    - global (no screen): no list blocks
    """
    out = _without_id_fields(doc)
    screen: Optional[str] = out.get("screen")

    if screen == "radio":
        for k in ("mp3_list", "downloads_list", "recordings_list"):
            out.pop(k, None)
    elif screen == "player":
        out.pop("stations_list", None)
    elif screen == "mp3_download":
        for k in LIST_KEYS:
            out.pop(k, None)
    else:
        if not screen:
            for k in LIST_KEYS:
                out.pop(k, None)

    return out


def expand_for_analytics_client(screen: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a dict suitable for ScreenAdsConfig: all four list keys present;
    keys that do not apply on this screen are forced to DISABLED_PLACEMENT.
    """
    merged = _without_id_fields(doc)
    merged["screen"] = screen

    if screen == "radio":
        for k in ("mp3_list", "downloads_list", "recordings_list"):
            merged[k] = deepcopy(DISABLED_PLACEMENT)
        merged.setdefault("stations_list", deepcopy(DISABLED_PLACEMENT))
    elif screen == "player":
        merged["stations_list"] = deepcopy(DISABLED_PLACEMENT)
        for k in ("mp3_list", "downloads_list", "recordings_list"):
            merged.setdefault(k, deepcopy(DISABLED_PLACEMENT))
    elif screen == "mp3_download":
        for k in LIST_KEYS:
            merged[k] = deepcopy(DISABLED_PLACEMENT)
    else:
        for k in LIST_KEYS:
            merged.setdefault(k, deepcopy(DISABLED_PLACEMENT))

    for k in LIST_KEYS:
        if k in merged and isinstance(merged[k], dict):
            base = deepcopy(DISABLED_PLACEMENT)
            base.update(merged[k])
            merged[k] = base

    return merged


async def replace_sanitized_ads_doc(db, oid, sanitized: Dict[str, Any]) -> Dict[str, Any]:
    """Write full sanitized document; returns stored doc with _id as ObjectId."""
    from bson import ObjectId

    to_store = deepcopy(sanitized)
    to_store["_id"] = oid
    await db["ads_config"].replace_one({"_id": oid}, to_store)
    return await db["ads_config"].find_one({"_id": oid})
