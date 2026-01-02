import redis.asyncio as redis
import os

# 1. Configuration Constants
CACHE_TTL = 3600  # Time To Live: 1 hour in seconds
CACHE_KEY_FIRST_PAGE = "stations:page:1:limit:50"

# --- Configuration (Load from Render Environment Variables) ---
# Assuming you set REDIS_HOST and REDIS_PORT in Render
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_USERNAME = os.getenv("REDIS_USERNAME")

# --- Initialize Redis Connection ---
# Use decode_responses=True to get Python strings instead of bytes
try:
    r_async = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    r_async.ping()
    print("✅ Redis connection successful!")
except Exception as e:
    print(f"❌ Could not connect to Redis: {e}")
    r_async = None # Set to None if connection fails