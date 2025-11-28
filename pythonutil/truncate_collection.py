import pymongo
from pymongo.errors import ConnectionFailure

# IMPORTANT: Replace these connection details with your actual MongoDB credentials
MONGO_URI = "mongodb://govardhanaraofmuser:mK18NY3DJ260hsrp@atlas-sql-690d90acc3db4977165ba1c3-evtrqj.a.query.mongodb.net/GRRadio?ssl=true&authSource=admin"
DATABASE_NAME = "GRRadio"
COLLECTION_NAME = "radio_stations"


def truncate_collection():
    """Connects to MongoDB and deletes all documents in a specified collection."""
    print("Attempting to connect to MongoDB...")

    try:
        # Establish connection
        client = pymongo.MongoClient(MONGO_URI)
        client.admin.command('ping')  # Test connection
        print("Connection successful.")

        # Access database and collection
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]

        # Use deleteMany to truncate (delete all documents)
        result = collection.delete_many({})

        print(f"✅ Successfully truncated collection '{COLLECTION_NAME}'.")
        print(f"   -> Deleted {result.deleted_count} documents.")

        # Close the connection
        client.close()

    except ConnectionFailure:
        print(f"❌ Error: Could not connect to MongoDB at {MONGO_URI}. Is the server running?")
    except Exception as e:
        print(f"An error occurred during MongoDB operation: {e}")


if __name__ == '__main__':
    # Be absolutely sure this is what you want before running!
    truncate_collection()