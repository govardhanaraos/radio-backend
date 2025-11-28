import os

from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional

MONGO_URL=os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')

# Use environment variables for your connection string in a real app!
#MONGO_URL = "mongodb+srv://govardhanaraofmuser:mK18NY3DJ260hsrp@cluster0.mihjnbk.mongodb.net/GRRadio?retryWrites=true&w=majority&authSource=admin"
if MONGO_URL is None or MONGO_URL == "":
    MONGO_URL = "mongodb://govardhanaraofmuser:Retail546321987@ac-1iddvrw-shard-00-00.mihjnbk.mongodb.net:27017,ac-1iddvrw-shard-00-01.mihjnbk.mongodb.net:27017,ac-1iddvrw-shard-00-02.mihjnbk.mongodb.net:27017/?ssl=true&authSource=admin&replicaSet=atlas-w63i5e-shard-0"

if DB_NAME is None or DB_NAME == "":
    DB_NAME = "GRRadio"

print(f"MONGO_URL static DB_NAME: {DB_NAME}")

#MONGO_URL=os.environ.get('MONGO_URL')
#DB_NAME = os.environ.get('DB_NAME')


print(f"MONGO_URL  env DB_NAME: {DB_NAME}")

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