from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional

# Use environment variables for your connection string in a real app!
MONGO_URL = "mongodb+srv://govardhanaraofmuser:mK18NY3DJ260hsrp@cluster0.mihjnbk.mongodb.net/GRRadio?retryWrites=true&w=majority&authSource=admin"
#MONGO_URL = "mongodb://govardhanaraofmuser:mK18NY3DJ260hsrp@atlas-sql-690d90acc3db4977165ba1c3-evtrqj.a.query.mongodb.net/GRRadio?ssl=true&authSource=admin"
DB_NAME = "GRRadio"

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