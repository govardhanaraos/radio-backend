import os
import asyncio
import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from db.redis_config import (r_async, CACHE_TTL, CACHE_KEY_FIRST_PAGE)


# Always use the correct domain (Cloudflare blocks non-www)
BASE_URL = os.environ.get("BASE_URL_MASSTAMILAN") or "https://www.masstamilan.dev"
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")

router = APIRouter(
    prefix="/masstamilan",
    tags=["MassTamilan"],
)

# -----------------------------
# Pydantic Models
# -----------------------------

class Album(BaseModel):
    album_name: str
    album_art: str
    starring: Optional[str]
    music: Optional[str]
    director: Optional[str]
    link: str

class PageLink(BaseModel):
    page: Optional[int]
    url: Optional[str]

class Pagination(BaseModel):
    current_page: Optional[int]
    next_page: Optional[str]
    prev_page: Optional[str]
    pages: List[PageLink]

class AlbumResponse(BaseModel):
    albums: List[Album]
    pagination: Pagination

class Track(BaseModel):
    position: int
    name: str
    singers: str
    duration: str
    download_128: Optional[str]
    download_320: Optional[str]

class AlbumDetails(BaseModel):
    album_name: str
    album_art: str
    starring: Optional[str]
    music: Optional[str]
    director: Optional[str]
    year: Optional[str]
    language: Optional[str]
    tracks: List[Track]

import json

async def cached_fetch_json(url: str, render: bool, cache_key: str, parser_fn):
    # 1. Check cache
    cached = await r_async.get(cache_key)
    if cached:
        print("CACHE HIT:", cache_key)
        return json.loads(cached)

    # 2. Fetch HTML
    html = await fetch_html_scraperapi(url, render)

    # 3. Parse HTML → JSON
    parsed_json = parser_fn(html)

    # 4. Store JSON in Redis
    await r_async.set(cache_key, json.dumps(parsed_json))

    print("CACHE STORE:", cache_key)
    return parsed_json

async def cached_fetch(url: str, render: bool = False, cache_key: str = None):
    if not cache_key:
        cache_key = f"masstamilan:{url}"

    # 1. Check cache
    cached = await r_async.get(cache_key)
    if cached:
        print("CACHE HIT:", cache_key)
        return cached

    # 2. Fetch fresh HTML
    html = await fetch_html_scraperapi(url, render)

    # 3. Store in Redis (no expiry)
    await r_async.set(cache_key, html)

    print("CACHE STORE:", cache_key)
    return html

def build_scraperapi_url(url: str, render: bool = False):
    params = [
        f"api_key={SCRAPER_API_KEY}",
        f"url={url}",
        "keep_headers=true",
        "country_code=in",
        "auto_parse=true"
    ]

    if render:
        params.append("render=true")
    else:
        params.append("render=false")

    return "https://api.scraperapi.com/?" + "&".join(params)

# -----------------------------
# ScraperAPI Fetcher
# -----------------------------

async def fetch_html_scraperapi(url: str, render: bool = False):
    """Fetch HTML using ScraperAPI to bypass Cloudflare."""
    if not SCRAPER_API_KEY:
        raise Exception("SCRAPER_API_KEY is missing. Add it in Render environment variables.")

    api_url = build_scraperapi_url(url, render)

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(api_url)
        response.raise_for_status()
        html = response.text
        return html


# -----------------------------
# Album List Parsing
# -----------------------------

def parse_albums(html: str) -> AlbumResponse:
    soup = BeautifulSoup(html, "html.parser")

    gw = soup.find("div", class_="gw")
    albums: List[Album] = []

    if not gw:
        return AlbumResponse(
            albums=[],
            pagination=Pagination(
                current_page=None,
                next_page=None,
                prev_page=None,
                pages=[]
            )
        )

    for item in gw.find_all("div", class_="a-i"):
        a_tag = item.find("a")
        if not a_tag:
            continue

        link = a_tag.get("href", "").strip()

        img = a_tag.find("img")
        album_art = urljoin(BASE_URL, img.get("src", "").strip()) if img else ""

        title_tag = a_tag.find("h2")
        album_name = title_tag.get_text(strip=True) if title_tag else ""

        p_tag = a_tag.find("p")
        starring = music = director = None

        if p_tag:
            for b in p_tag.find_all("b"):
                label = b.get_text(strip=True).rstrip(":").lower()
                value = (b.next_sibling or "").strip()

                if label == "starring":
                    starring = value
                elif label == "music":
                    music = value
                elif label == "director":
                    director = value

        albums.append(
            Album(
                album_name=album_name,
                album_art=album_art,
                starring=starring,
                music=music,
                director=director,
                link=link,
            )
        )

    pagination = parse_pagination(soup)

    return AlbumResponse(
        albums=albums,
        pagination=Pagination(
            current_page=pagination["current_page"],
            next_page=pagination["next_page"],
            prev_page=pagination["prev_page"],
            pages=[
                PageLink(page=p["page"], url=p["url"])
                for p in pagination["pages"]
            ]
        )
    )


# -----------------------------
# Pagination Parser
# -----------------------------

def parse_pagination(soup):
    nav = soup.select_one("nav.pagy")

    pages = []
    current_page = None
    next_page = None
    prev_page = None

    if nav:
        for a in nav.find_all("a"):
            text = a.get_text(strip=True)

            if "current" in a.get("class", []):
                current_page = int(text)
                pages.append({"page": current_page, "url": None})
                continue

            href = a.get("href")
            if href:
                page_num = None
                if "page=" in href:
                    try:
                        page_num = int(href.split("page=")[1])
                    except:
                        page_num = None

                pages.append({"page": page_num, "url": href})

                if a.get("aria-label") == "Next":
                    next_page = href
                if a.get("aria-label") == "Previous":
                    prev_page = href

    if current_page is None and next_page is None:
        right_p = soup.select_one("p.right")
        if right_p:
            a_tag = right_p.find("a")
            if a_tag and a_tag.get("href"):
                next_page = a_tag.get("href")
                current_page = 1
                pages.append({"page": 2, "url": next_page})

    return {
        "current_page": current_page,
        "pages": pages,
        "next_page": next_page,
        "prev_page": prev_page
    }


# -----------------------------
# Album Details Parsing
# -----------------------------

def parse_album_details(html: str) -> AlbumDetails:
    soup = BeautifulSoup(html, "html.parser")

    album_name_tag = soup.select_one("meta[itemprop='name']")
    album_name = album_name_tag.get("content", "").strip() if album_name_tag else ""

    img = soup.select_one("figure img")
    album_art = urljoin(BASE_URL, img.get("src")) if img else ""

    info = soup.find("fieldset")
    starring, music, director, lyricists, year, language = parse_movie_info(info)

    tracks = []
    table = soup.select_one("table#tl")
    if table:
        rows = table.find_all("tr")[1:]
        for row in rows:
            pos = int(row.find("span", itemprop="position").text)
            name = row.find("a").text.strip()
            singers = row.find("span", itemprop="byArtist").text.strip()
            duration = row.find("span", itemprop="duration").text.strip()

            dl128 = dl320 = None
            for link in row.find_all("a", class_="dlink"):
                href = urljoin(BASE_URL, link.get("href"))
                if "128" in link.text:
                    dl128 = href
                if "320" in link.text:
                    dl320 = href

            tracks.append(
                Track(
                    position=pos,
                    name=name,
                    singers=singers,
                    duration=duration,
                    download_128=dl128,
                    download_320=dl320,
                )
            )

    return AlbumDetails(
        album_name=album_name,
        album_art=album_art,
        starring=starring,
        music=music,
        director=director,
        year=year,
        language=language,
        tracks=tracks,
    )


# -----------------------------
# Movie Info Parser
# -----------------------------

def parse_movie_info(info: BeautifulSoup):
    starring = music = director = lyricists = year = language = None

    if not info:
        return starring, music, director, lyricists, year, language

    for b in info.find_all("b"):
        label = b.get_text(strip=True).rstrip(":").lower()

        values = []
        node = b.next_sibling

        while node and node.name != "br":
            if isinstance(node, str):
                text = node.strip().strip(",")
                if text:
                    values.append(text)
            elif node.name == "a":
                values.append(node.get_text(strip=True))
            node = node.next_sibling

        value = ", ".join(values).strip()

        if label == "starring":
            starring = value
        elif label == "music":
            music = value
        elif label == "director":
            director = value
        elif label == "lyricists":
            lyricists = value
        elif label == "year":
            year = value
        elif label == "language":
            language = value

    return starring, music, director, lyricists, year, language


# -----------------------------
# Albums Endpoint
# -----------------------------

@router.get("/albums", response_model=AlbumResponse)
async def get_albums(relative_url: Optional[str] = None):
    url = urljoin(BASE_URL, relative_url) if relative_url else BASE_URL + "/"
    cache_key = f"albums:{relative_url or 'root'}"

    parsed = await cached_fetch_json(
        url=url,
        render=True,
        cache_key=cache_key,
        parser_fn=parse_albums
    )

    return parsed


# -----------------------------
# Album Details Endpoint
# -----------------------------

@router.get("/albumdetails", response_model=AlbumDetails)
async def get_album_details(url: str):
    full_url = urljoin(BASE_URL, url)
    cache_key = f"albumdetails:{url}"

    parsed = await cached_fetch_json(
        url=full_url,
        render=True,
        cache_key=cache_key,
        parser_fn=parse_album_details
    )

    return parsed

@router.get("/cache/keys")
async def list_cache_keys():
    keys = await r_async.keys("masstamilan:*")
    return {"keys": keys}

@router.get("/cache/get")
async def get_cache_value(key: str):
    value = await r_async.get(key)
    return {"key": key, "value": json.loads(value) if value else None}

@router.delete("/cache/delete")
async def delete_cache_key(key: str):
    await r_async.delete(key)
    return {"deleted": key}

@router.delete("/cache/clear-all")
async def clear_all_cache():
    keys = await r_async.keys("masstamilan:*")
    for k in keys:
        await r_async.delete(k)
    return {"cleared_keys": keys}