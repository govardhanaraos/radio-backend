import os

import redis
import sys

from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
# Replace these with your actual Redis Cloud details
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")


def check_redis_connection():
    print(f"Attempting to connect to {REDIS_HOST}:{REDIS_PORT}...")

    try:
        # Initialize the Redis client
        # Note: ssl=True is required for almost all cloud database providers
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            ssl=True,
            decode_responses=True  # Ensures we get strings back instead of bytes
        )

        # The ping() command actually reaches out to the server
        if client.ping():
            print("✅ Successfully connected to Redis!")

            # Optional: Test writing and reading a quick value
            client.set("test_key", "Hello from Python!")
            value = client.get("test_key")
            print(f"📝 Test read successful: {value}")

            # Clean up the test key
            client.delete("test_key")

    except redis.AuthenticationError:
        print("\n❌ Authentication failed: Your password or username is incorrect.")
    except redis.ConnectionError as e:
        print(f"\n❌ Connection failed: Check your host, port, or internet connection. Details: {e}")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")


if __name__ == "__main__":
    check_redis_connection()