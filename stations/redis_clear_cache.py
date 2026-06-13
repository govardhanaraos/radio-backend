import asyncio
import argparse
import redis.asyncio as redis
from fastapi import HTTPException, Query, APIRouter

router = APIRouter(prefix="/redis", tags=["redis"])

from db.redis_config import r_async

@router.delete("/clear-cache")
async def clear_redis_cache(
        key: str = Query(..., description="The exact Redis cache key to delete (e.g., stations_first_page)")
):
    """
    Clears a specific key from the Redis cache.
    """
    # 1. Ensure Redis is actually connected
    if r_async is None:
        raise HTTPException(status_code=503, detail="Redis is not connected.")

    try:
        # 2. Attempt to delete the key
        result = await r_async.delete(key)

        # result will be 1 if deleted, 0 if the key didn't exist
        if result == 1:
            return {
                "status": "success",
                "message": f"Cache key '{key}' deleted successfully."
            }
        else:
            return {
                "status": "not_found",
                "message": f"Cache key '{key}' not found (it may have already expired)."
            }

    except Exception as e:
        print(f"Error clearing Redis cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to communicate with Redis.")