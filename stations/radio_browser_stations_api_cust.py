from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
import asyncpg

from db.db import get_pg_pool

router = APIRouter(prefix="/radio-browser", tags=["World Radio - Radio Browser"])


# ─── Response Schemas ────────────────────────────────────────────────────────
class RadioStation(BaseModel):
    stationuuid: UUID
    name: Optional[str] = None
    url: Optional[str] = None
    url_resolved: Optional[str] = None
    homepage: Optional[str] = None
    favicon: Optional[str] = None
    tags: Optional[str] = None
    country: Optional[str] = None
    countrycode: Optional[str] = None
    language: Optional[str] = None
    votes: Optional[int] = None
    codec: Optional[str] = None
    bitrate: Optional[int] = None
    lastchangetime: Optional[datetime] = None
    geo_lat: Optional[float] = None
    geo_long: Optional[float] = None

    class Config:
        from_attributes = True


class PaginatedStations(BaseModel):
    total: int
    page: int
    limit: int
    results: list[RadioStation]


class CountryCount(BaseModel):
    country: str
    countrycode: Optional[str] = None
    station_count: int


class TagCount(BaseModel):
    tag: str
    station_count: int


class LanguageCount(BaseModel):
    language: str
    station_count: int


class StatsResponse(BaseModel):
    total_stations: int
    total_countries: int
    total_country_codes: int
    total_languages: int
    total_codecs: int
    playable_stations: int
    avg_bitrate: Optional[float] = None


# ─── Dependency ───────────────────────────────────────────────────────────────
def _pool_dep() -> asyncpg.Pool:
    pool = get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="PostgreSQL pool not initialised")
    return pool


def _records_to_stations(rows) -> list[RadioStation]:
    return [RadioStation(**dict(r)) for r in rows]


# ─── 1. Search stations ───────────────────────────────────────────────────────
@router.get("/stations/search", response_model=PaginatedStations)
async def search_stations(
    name: Optional[str] = Query(None, description="Partial station name"),
    tag: Optional[str] = Query(None, description="Genre / tag (partial)"),
    country: Optional[str] = Query(None, description="Country name (partial)"),
    countrycode: Optional[str] = Query(None, description="ISO country code e.g. IN, US"),
    language: Optional[str] = Query(None, description="Language (partial)"),
    codec: Optional[str] = Query(None, description="Codec e.g. MP3, AAC"),
    min_bitrate: Optional[int] = Query(None, description="Min bitrate in kbps"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    order_by: str = Query("votes", enum=["votes", "name", "bitrate", "lastchangetime"]),
    pool: asyncpg.Pool = Depends(_pool_dep),
):
    conditions = ["url_resolved IS NOT NULL", "url_resolved != ''"]
    args: list = []

    def add(cond: str, val):
        args.append(val)
        conditions.append(cond.replace("?", f"${len(args)}"))

    if name:        add("name ILIKE ?",        f"%{name}%")
    if tag:         add("tags ILIKE ?",         f"%{tag}%")
    if country:     add("country ILIKE ?",      f"%{country}%")
    if countrycode: add("countrycode ILIKE ?",  countrycode.upper())
    if language:    add("language ILIKE ?",     f"%{language}%")
    if codec:       add("codec ILIKE ?",        f"%{codec}%")
    if min_bitrate: add("bitrate >= ?",         min_bitrate)

    where = " AND ".join(conditions)
    direction = "DESC" if order_by in ("votes", "bitrate", "lastchangetime") else "ASC"
    offset = (page - 1) * limit

    count_sql = f"SELECT COUNT(*) FROM public.radio_browser_stations WHERE {where}"
    total = await pool.fetchval(count_sql, *args)

    data_sql = f"""
        SELECT * FROM public.radio_browser_stations
        WHERE {where}
        ORDER BY {order_by} {direction} NULLS LAST
        LIMIT ${len(args) + 1} OFFSET ${len(args) + 2}
    """
    rows = await pool.fetch(data_sql, *args, limit, offset)

    return PaginatedStations(
        total=total, page=page, limit=limit,
        results=_records_to_stations(rows),
    )


# ─── 2. Single station by UUID ────────────────────────────────────────────────
@router.get("/stations/{stationuuid}", response_model=RadioStation)
async def get_station(
    stationuuid: UUID,
    pool: asyncpg.Pool = Depends(_pool_dep),
):
    row = await pool.fetchrow(
        "SELECT * FROM public.radio_browser_stations WHERE stationuuid = $1",
        str(stationuuid),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Station not found")
    return RadioStation(**dict(row))


# ─── 3. Top voted stations ────────────────────────────────────────────────────
@router.get("/stations/top/voted", response_model=list[RadioStation])
async def top_voted_stations(
    limit: int = Query(20, ge=1, le=100),
    countrycode: Optional[str] = Query(None),
    pool: asyncpg.Pool = Depends(_pool_dep),
):
    if countrycode:
        rows = await pool.fetch(
            """SELECT * FROM public.radio_browser_stations
               WHERE url_resolved IS NOT NULL AND url_resolved != ''
                 AND votes > 0 AND countrycode = $1
               ORDER BY votes DESC LIMIT $2""",
            countrycode.upper(), limit,
        )
    else:
        rows = await pool.fetch(
            """SELECT * FROM public.radio_browser_stations
               WHERE url_resolved IS NOT NULL AND url_resolved != ''
                 AND votes > 0
               ORDER BY votes DESC LIMIT $1""",
            limit,
        )
    return _records_to_stations(rows)


# ─── 4. Stations by country code ─────────────────────────────────────────────
@router.get("/stations/by-country/{countrycode}", response_model=PaginatedStations)
async def stations_by_country(
    countrycode: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    pool: asyncpg.Pool = Depends(_pool_dep),
):
    cc = countrycode.upper()
    offset = (page - 1) * limit
    total = await pool.fetchval(
        """SELECT COUNT(*) FROM public.radio_browser_stations
           WHERE countrycode = $1 AND url_resolved IS NOT NULL""",
        cc,
    )
    rows = await pool.fetch(
        """SELECT * FROM public.radio_browser_stations
           WHERE countrycode = $1 AND url_resolved IS NOT NULL
           ORDER BY votes DESC NULLS LAST
           LIMIT $2 OFFSET $3""",
        cc, limit, offset,
    )
    return PaginatedStations(
        total=total, page=page, limit=limit,
        results=_records_to_stations(rows),
    )


# ─── 5. Stations by tag / genre ───────────────────────────────────────────────
@router.get("/stations/by-tag/{tag}", response_model=PaginatedStations)
async def stations_by_tag(
    tag: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    pool: asyncpg.Pool = Depends(_pool_dep),
):
    like = f"%{tag}%"
    offset = (page - 1) * limit
    total = await pool.fetchval(
        """SELECT COUNT(*) FROM public.radio_browser_stations
           WHERE tags ILIKE $1 AND url_resolved IS NOT NULL""",
        like,
    )
    rows = await pool.fetch(
        """SELECT * FROM public.radio_browser_stations
           WHERE tags ILIKE $1 AND url_resolved IS NOT NULL
           ORDER BY votes DESC NULLS LAST
           LIMIT $2 OFFSET $3""",
        like, limit, offset,
    )
    return PaginatedStations(
        total=total, page=page, limit=limit,
        results=_records_to_stations(rows),
    )


# ─── 6. Stations by language ──────────────────────────────────────────────────
@router.get("/stations/by-language/{language}", response_model=PaginatedStations)
async def stations_by_language(
    language: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    pool: asyncpg.Pool = Depends(_pool_dep),
):
    like = f"%{language}%"
    offset = (page - 1) * limit
    total = await pool.fetchval(
        """SELECT COUNT(*) FROM public.radio_browser_stations
           WHERE language ILIKE $1 AND url_resolved IS NOT NULL""",
        like,
    )
    rows = await pool.fetch(
        """SELECT * FROM public.radio_browser_stations
           WHERE language ILIKE $1 AND url_resolved IS NOT NULL
           ORDER BY votes DESC NULLS LAST
           LIMIT $2 OFFSET $3""",
        like, limit, offset,
    )
    return PaginatedStations(
        total=total, page=page, limit=limit,
        results=_records_to_stations(rows),
    )


# ─── 7. Nearby stations (Haversine geo search) ───────────────────────────────
@router.get("/stations/nearby", response_model=list[RadioStation])
async def nearby_stations(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius_km: float = Query(500, description="Search radius in km"),
    limit: int = Query(20, ge=1, le=100),
    pool: asyncpg.Pool = Depends(_pool_dep),
):
    rows = await pool.fetch(
        """
        SELECT * FROM (
            SELECT *,
              (6371 * acos(
                cos(radians($1)) * cos(radians(geo_lat)) *
                cos(radians(geo_long) - radians($2)) +
                sin(radians($1)) * sin(radians(geo_lat))
              )) AS distance_km
            FROM public.radio_browser_stations
            WHERE geo_lat IS NOT NULL AND geo_long IS NOT NULL
              AND url_resolved IS NOT NULL
        ) sub
        WHERE distance_km <= $3
        ORDER BY distance_km ASC
        LIMIT $4
        """,
        lat, lon, radius_km, limit,
    )
    return _records_to_stations(rows)


# ─── 8. Random stations ───────────────────────────────────────────────────────
@router.get("/stations/random", response_model=list[RadioStation])
async def random_stations(
    limit: int = Query(10, ge=1, le=50),
    countrycode: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    pool: asyncpg.Pool = Depends(_pool_dep),
):
    conditions = ["url_resolved IS NOT NULL", "url_resolved != ''"]
    args: list = []

    def add(cond: str, val):
        args.append(val)
        conditions.append(cond.replace("?", f"${len(args)}"))

    if countrycode: add("countrycode = ?", countrycode.upper())
    if tag:         add("tags ILIKE ?",    f"%{tag}%")

    where = " AND ".join(conditions)
    args.append(limit)
    rows = await pool.fetch(
        f"SELECT * FROM public.radio_browser_stations WHERE {where} ORDER BY RANDOM() LIMIT ${len(args)}",
        *args,
    )
    return _records_to_stations(rows)


# ─── 9. All countries with station counts ────────────────────────────────────
@router.get("/meta/countries", response_model=list[CountryCount])
async def list_countries(pool: asyncpg.Pool = Depends(_pool_dep)):
    rows = await pool.fetch(
        """
        SELECT country, countrycode, COUNT(*) AS station_count
        FROM public.radio_browser_stations
        WHERE country IS NOT NULL AND country != ''
          AND url_resolved IS NOT NULL
        GROUP BY country, countrycode
        ORDER BY station_count DESC
        """
    )
    return [CountryCount(**dict(r)) for r in rows]


# ─── 10. Top tags / genres with counts ───────────────────────────────────────
@router.get("/meta/tags", response_model=list[TagCount])
async def list_tags(
    limit: int = Query(50, ge=1, le=200),
    pool: asyncpg.Pool = Depends(_pool_dep),
):
    rows = await pool.fetch(
        """
        SELECT TRIM(tag) AS tag, COUNT(*) AS station_count
        FROM public.radio_browser_stations,
             LATERAL unnest(string_to_array(tags, ',')) AS tag
        WHERE tags IS NOT NULL AND tags != ''
          AND url_resolved IS NOT NULL
        GROUP BY TRIM(tag)
        ORDER BY station_count DESC
        LIMIT $1
        """,
        limit,
    )
    return [TagCount(**dict(r)) for r in rows]


# ─── 11. All languages with counts ───────────────────────────────────────────
@router.get("/meta/languages", response_model=list[LanguageCount])
async def list_languages(pool: asyncpg.Pool = Depends(_pool_dep)):
    rows = await pool.fetch(
        """
        SELECT TRIM(lang) AS language, COUNT(*) AS station_count
        FROM public.radio_browser_stations,
             LATERAL unnest(string_to_array(language, ',')) AS lang
        WHERE language IS NOT NULL AND language != ''
          AND url_resolved IS NOT NULL
        GROUP BY TRIM(lang)
        ORDER BY station_count DESC
        """
    )
    return [LanguageCount(**dict(r)) for r in rows]


# ─── 12. DB stats summary ─────────────────────────────────────────────────────
@router.get("/meta/stats", response_model=StatsResponse)
async def stats(pool: asyncpg.Pool = Depends(_pool_dep)):
    row = await pool.fetchrow(
        """
        SELECT
          COUNT(*)                                                         AS total_stations,
          COUNT(DISTINCT country)                                          AS total_countries,
          COUNT(DISTINCT countrycode)                                      AS total_country_codes,
          COUNT(DISTINCT language)                                         AS total_languages,
          COUNT(DISTINCT codec)                                            AS total_codecs,
          SUM(CASE WHEN url_resolved IS NOT NULL
                    AND url_resolved != '' THEN 1 ELSE 0 END)             AS playable_stations,
          ROUND(AVG(bitrate)::numeric, 1)                                 AS avg_bitrate
        FROM public.radio_browser_stations
        """
    )
    return StatsResponse(**dict(row))