import os

from fastapi import FastAPI, Query, APIRouter
from pydantic import BaseModel
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
from db.redis_config import r_async


BASE_URL = os.environ.get('BASE_URL_MASSHINDI')

if BASE_URL is None or BASE_URL == "":
    BASE_URL = "https://mp3bhai.com"

router = APIRouter(
    prefix="/hindimp3bhai",
    tags=["HindiMp3Bhai"],
)


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


async def cached_fetch_json(url: str, cache_key: str, parser_fn):
    # 1. Check cache
    cached = await r_async.get(cache_key)
    if cached:
        print("CACHE HIT:", cache_key)
        return json.loads(cached)

    # 2. Fetch HTML directly
    resp = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9"
    }, timeout=10)
    resp.raise_for_status()

    html = resp.text

    # 3. Parse HTML → Pydantic model
    parsed_model = parser_fn(html)

    # 4. Convert to dict
    parsed_dict = parsed_model.dict()

    # 5. Store JSON in Redis
    await r_async.set(cache_key, json.dumps(parsed_dict))

    print("CACHE STORE:", cache_key)
    return parsed_dict

def parse_albums(html: str) -> AlbumResponse:
    soup = BeautifulSoup(html, "html.parser")

    gw = soup.find("div", class_="gw")
    albums: List[Album] = []

    if not gw:
        return AlbumResponse(albums=[], next_page=None)

    for item in gw.find_all("div", class_="a-i"):
        a_tag = item.find("a")
        if not a_tag:
            continue

        # album page link
        link_rel = a_tag.get("href", "").strip()
        link = link_rel

        # album art
        img = a_tag.find("img")
        album_art_rel = img.get("src", "").strip() if img else ""
        album_art = urljoin(BASE_URL, album_art_rel)

        # album name
        title_tag = a_tag.find("h2")
        album_name = title_tag.get_text(strip=True) if title_tag else ""

        # details (starring, music, director)
        p_tag = a_tag.find("p")
        starring = music = director = None

        if p_tag:
            # each line separated by <br/>
            # we’ll walk over <b> tags and their following text
            for b in p_tag.find_all("b"):
                label = b.get_text(strip=True).rstrip(":").lower()
                # text after </b>
                value = b.next_sibling
                if value:
                    value = str(value).strip()
                else:
                    value = ""

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


def parse_pagination(soup):
    nav = soup.select_one("nav.pagy")

    pages = []
    current_page = None
    next_page = None
    prev_page = None

    if nav:
        for a in nav.find_all("a"):
            text = a.get_text(strip=True)

            # Current page
            if "current" in a.get("class", []):
                current_page = int(text)
                pages.append({"page": current_page, "url": None})
                continue

            # Normal page links
            href = a.get("href")
            if href:
                page_num = None
                if "page=" in href:
                    try:
                        page_num = int(href.split("page=")[1])
                    except:
                        page_num = None

                pages.append({"page": page_num, "url": href})

                # Detect prev/next
                if a.get("aria-label") == "Next":
                    next_page = href
                if a.get("aria-label") == "Previous":
                    prev_page = href

    # ---------------------------------------------
    # SPECIAL CASE: Page 1 (no nav.pagy)
    # ---------------------------------------------
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

def parse_album_details(html: str) -> AlbumDetails:
    soup = BeautifulSoup(html, "html.parser")

    # -----------------------------------------
    # Album Name (BEST SOURCE)
    # -----------------------------------------
    album_name_tag = soup.select_one("meta[itemprop='name']")
    album_name = album_name_tag.get("content", "").strip() if album_name_tag else ""

    # Album art
    img = soup.select_one("figure img")
    album_art = urljoin(BASE_URL, img.get("src")) if img else ""

    info = soup.find("fieldset")
    starring, music, director, lyricists, year, language = parse_movie_info(info)

    # Tracks
    tracks = []
    table = soup.select_one("table#tl")
    if table:
        rows = table.find_all("tr")[1:]  # skip header
        for row in rows:
            pos = int(row.find("span", itemprop="position").text)
            name = row.find("a").text.strip()

            singers = row.find("span", itemprop="byArtist").text.strip()
            duration = row.find("span", itemprop="duration").text.strip()

            links = row.find_all("a", class_="dlink")
            dl128 = dl320 = None
            for link in links:
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

def parse_movie_info(info: BeautifulSoup):
    starring = music = director = lyricists = year = language = None

    if not info:
        return starring, music, director, lyricists, year, language

    # Loop through all <b> tags inside fieldset
    for b in info.find_all("b"):
        label = b.get_text(strip=True).rstrip(":").lower()

        # Collect everything until <br/>
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

@router.get("/albums", response_model=AlbumResponse)
async def get_albums(relative_url: Optional[str] = None):
    url = urljoin(BASE_URL, relative_url) if relative_url else BASE_URL + "/"
    cache_key = f"hindimp3bhai:albums:{relative_url or 'root'}"

    parsed = await cached_fetch_json(
        url=url,
        cache_key=cache_key,
        parser_fn=parse_albums
    )

    return parsed

@router.get("/albumdetails", response_model=AlbumDetails)
async def get_album_details(url: str):
    full_url = urljoin(BASE_URL, url)
    cache_key = f"hindimp3bhai:albumdetails:{url}"

    parsed = await cached_fetch_json(
        url=full_url,
        cache_key=cache_key,
        parser_fn=parse_album_details
    )

    return parsed