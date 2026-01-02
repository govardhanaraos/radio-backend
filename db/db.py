import os

from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional

MONGO_URL=os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
RADIO_GARDEN_CHANNELS_COLLECTION = os.environ.get('RADIO_GARDEN_CHANNELS_COLLECTION')
SECRET_KEY = os.environ.get('SECRET_KEY')
FIXED_IV = os.environ.get('FIXED_IV')

if MONGO_URL is None or MONGO_URL == "":
    MONGO_URL = "mongodb://govardhanaraofmuser:Retail546321987@ac-1iddvrw-shard-00-00.mihjnbk.mongodb.net:27017,ac-1iddvrw-shard-00-01.mihjnbk.mongodb.net:27017,ac-1iddvrw-shard-00-02.mihjnbk.mongodb.net:27017/?ssl=true&authSource=admin&replicaSet=atlas-w63i5e-shard-0"

print(f"MONGO_URL static DB_NAME: {MONGO_URL}")


if DB_NAME is None or DB_NAME == "":
    DB_NAME = "GRRadio"

print(f"MONGO_URL static DB_NAME: {DB_NAME}")


COLLECTION_NAME = os.environ.get('MONGO_COLLECTION_NAME')

if COLLECTION_NAME is None or COLLECTION_NAME == "":
    COLLECTION_NAME = "radio_garden_channels"

print(f"COLLECTION_NAME db.py: {COLLECTION_NAME}")

# Use the same key and IV in Flutter
if SECRET_KEY is None or SECRET_KEY == "":
    SECRET_KEY = b"YourSuperSecretKey12345678901234" # 32 bytes
if FIXED_IV is None or FIXED_IV == "":
    FIXED_IV = b"FixedIV123456789"                # 16 bytes

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