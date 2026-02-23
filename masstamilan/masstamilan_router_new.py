import os
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.async_api import async_playwright
import asyncio
from playwright.sync_api import sync_playwright


# Always use the correct domain (Cloudflare blocks non-www)
BASE_URL = os.environ.get("BASE_URL_MASSTAMILAN") or "https://www.masstamilan.dev"

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




# Change this part of your masstamilan_router.py
def fetch_html_sync(url: str) -> str:
    """Synchronous function for Playwright to avoid event loop conflicts."""
    with sync_playwright() as p:
        # Added mandatory flags for Render/Docker environment
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer"
            ]
        )

        page = browser.new_page(ignore_https_errors=True)

        page.set_extra_http_headers({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        })

        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            html = page.content()
            print(html[:500])
        finally:
            browser.close()

        return str(html)  # Force return as string to prevent coroutine errors

async def fetch_html_with_browser(url: str) -> str:
    """Wraps the sync browser in an executor to keep FastAPI responsive."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fetch_html_sync, url)


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
    print("Fetching URL:", url)
    html = await fetch_html_with_browser(url)
    print("HTML snippet:", html[:300])
    return parse_albums(html)


# -----------------------------
# Album Details Endpoint
# -----------------------------

@router.get("/albumdetails", response_model=AlbumDetails)
async def get_album_details(url: str):
    # FIXED: Use full_url instead of the relative url
    full_url = urljoin(BASE_URL, url)
    html = await fetch_html_with_browser(full_url)
    return parse_album_details(html)