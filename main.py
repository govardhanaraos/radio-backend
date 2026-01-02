from contextlib import asynccontextmanager
from fastapi import FastAPI
# Import the functions directly from the db.db module
from db.db import connect_to_mongo, close_mongo_connection
from stations.router import router as stations_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from stations.analytics_router import router as analytics_router
from complaints.router import router as complaints_router
from config.router import router as config_router
from premium.router import router as premium_router



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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to ["https://your-frontend.onrender.com"]
    allow_credentials=True,
    allow_methods=["*"],  # GET, POST, PUT, DELETE, OPTIONS
    allow_headers=["*"],  # Authorization, Content-Type, etc.
)


app.include_router(stations_router)
app.include_router(analytics_router)
app.include_router(complaints_router)
app.include_router(config_router)
app.include_router(premium_router, prefix="/premium", tags=["Premium"])
# ... include routers ...