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
from masstamilan.masstelugu_router import router as masstelugu_router
from masstamilan.masstamilan_router_new import router as masstamilan_router
from masstamilan.hindimp3bhai_router import router as hindimp3bhai_router
from masstamilan.massmalayalam_router import router as massmalayalam_router
from telugump3.telugump3_home_parse import router as telugump3_home_parse
from telugump3.album_list_parsing import router as album_list_parsing
from telugump3.song_details_crawl import router as song_details_crawl
from telugump3.album_details_parsing import router as album_details_parsing

from teluguwap.teluguwap_home_parse import router as teluguwap_home_parse
from teluguwap.teluguwap_album_list_parsing import router as teluguwap_album_list_parsing
from teluguwap.teluguwap_album_details_parsing import router as teluguwap_album_details_parsing
from teluguwap.teluguwap_song_details_crawl import router as teluguwap_song_details_crawl



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
app.include_router(masstelugu_router)
app.include_router(masstamilan_router)
app.include_router(hindimp3bhai_router)
app.include_router(massmalayalam_router)
app.include_router(telugump3_home_parse)
app.include_router(album_list_parsing)
app.include_router(album_details_parsing)
app.include_router(song_details_crawl)
app.include_router(premium_router, prefix="/premium", tags=["Premium"])

app.include_router(teluguwap_home_parse)
app.include_router(teluguwap_album_list_parsing)
app.include_router(teluguwap_album_details_parsing)
app.include_router(teluguwap_song_details_crawl)
# ... include routers ...