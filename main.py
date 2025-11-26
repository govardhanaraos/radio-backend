# main.py
from fastapi import FastAPI
# Import the functions directly from the db.db module
from db.db import connect_to_mongo, close_mongo_connection
from stations.router import router as stations_router

app = FastAPI(
    title="Radio Station Backend",
    version="1.0.0",
)

# 1. Register the connection function to run before the app starts
@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()

# 2. Register the close function to run when the app shuts down
@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()

app.include_router(stations_router)

# ... include routers ...