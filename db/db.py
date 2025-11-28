import os

from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional

MONGO_URL=os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')

print(f"MONGO_URL static DB_NAME: {DB_NAME}")


if DB_NAME is None or DB_NAME == "":
    DB_NAME = "GRRadio"

print(f"MONGO_URL static DB_NAME: {DB_NAME}")


COLLECTION_NAME = os.environ.get('MONGO_COLLECTION_NAME')

if COLLECTION_NAME is None or COLLECTION_NAME == "":
    COLLECTION_NAME = "radio_garden_channels"

print(f"COLLECTION_NAME db.py: {COLLECTION_NAME}")


# Global variable to hold the database client instance
client = None
db = None

async def connect_to_mongo():
    """Initializes the MongoDB connection."""
    global client, db
    if client and db:
        return
    print("Connecting to MongoDB...")
    try:
        # 1. Create the async client
        client = AsyncIOMotorClient(
            MONGO_URL,
            serverSelectionTimeoutMS=120000  # 120 second timeout
        )
        # 2. Assign the database instance
        db = client[DB_NAME]
        await client.admin.command('ping') # Test connection
        print("Successfully connected to MongoDB.")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        # Re-raise the exception to stop the application from starting
        raise

async def close_mongo_connection():
    """Closes the MongoDB connection when the application shuts down."""
    global client
    if client:
        print("Closing MongoDB connection.")
        client.close()

def get_db() -> Optional[AsyncIOMotorDatabase]:
    """Returns the initialized database instance."""
    # This is the safest way to access the global variable set in startup
    return db