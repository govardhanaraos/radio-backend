import os
import asyncio
from dotenv import load_dotenv
load_dotenv('.env')

from fastapi.testclient import TestClient
from main import app

# It's a quick hack mock for db for running test without hitting motor errors on asyncio in windows
import db.db
db.db._db = {} 
class MockCol:
    async def find_one(self, *args, **kwargs):
        return None
    async def insert_one(self, *args, **kwargs):
        pass
    async def update_one(self, *args, **kwargs):
        pass

class MockDB:
    def __getitem__(self, name):
         return MockCol()
    def __setitem__(self, name, val):
         pass

db.db.get_db = lambda: MockDB()

client = TestClient(app)

print("Test 1: Normal question")
response = client.post("/ai/chat", json={
    "device_id": "test_device_123",
    "message": "How do I upgrade to premium?",
    "locale": "en"
})
print(response.json())

print("\nTest 2: Off-topic question")
response = client.post("/ai/chat", json={
    "device_id": "test_device_123",
    "message": "What is the capital of France?",
    "locale": "en"
})
print(response.json())
