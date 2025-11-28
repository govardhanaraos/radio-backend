from contextlib import asynccontextmanager
from fastapi import FastAPI
# Import the functions directly from the db.db module
from db.db import connect_to_mongo, close_mongo_connection
from stations.router import router as stations_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Logic to run on startup (before the app starts)
    print("Application Startup: Connecting to Mongo...")
    await connect_to_mongo()
    yield # <-- Application is now running and serving requests
    # 2. Logic to run on shutdown (when the app shuts down)
    print("Application Shutdown: Closing Mongo connection...")
    await close_mongo_connection()


app = FastAPI(
    title="Radio Station Backend",
    version="1.0.0",
    lifespan=lifespan,
)


app.include_router(stations_router)

# ... include routers ...