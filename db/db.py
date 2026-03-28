import os

from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
import psycopg2
from dotenv import load_dotenv

load_dotenv()


MONGO_URL=os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME')
RADIO_GARDEN_CHANNELS_COLLECTION = os.environ.get('RADIO_GARDEN_CHANNELS_COLLECTION')
SECRET_KEY = os.environ.get('SECRET_KEY')
FIXED_IV = os.environ.get('FIXED_IV')


if DB_NAME is None or DB_NAME == "":
    DB_NAME = "GRRadio"

# ---------------------------------------
# 1. Read DATABASE_URL from environment
# ---------------------------------------
POSTGRESQL_DATABASE_URL = os.getenv("POSTGRESQL_DATABASE_URL")

if not POSTGRESQL_DATABASE_URL:
    raise ValueError("POSTGRESQL_DATABASE_URL environment variable is not set")

POSTGRESQL_DATABASE_URL_TELUGUWAP = os.getenv("POSTGRESQL_DATABASE_URL_TELUGUWAP")

if not POSTGRESQL_DATABASE_URL_TELUGUWAP:
    raise ValueError("POSTGRESQL_DATABASE_URL_TELUGUWAP environment variable is not set")


BLOMP_AUTH_URL = os.getenv("BLOMP_AUTH_URL")

BLOMP_USER = os.getenv("BLOMP_USER")

BLOMP_PASS = os.getenv("BLOMP_PASS")

TENANT = os.getenv("TENANT")

COLLECTION_NAME = os.environ.get('MONGO_COLLECTION_NAME')

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
    print("MONGO_URL", MONGO_URL)
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

def get_pg_conn():
    """Returns a new PostgreSQL connection."""
    try:
        conn = psycopg2.connect(POSTGRESQL_DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None