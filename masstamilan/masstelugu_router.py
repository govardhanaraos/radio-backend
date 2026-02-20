from fastapi import FastAPI, Query, APIRouter
from pydantic import BaseModel
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://masstelugu.com"


router = APIRouter(
    prefix="/masstelugu",
    tags=["MassTelugu"],
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
        link = urljoin(BASE_URL, link_rel)

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
    if not nav:
        return {
            "current_page": None,
            "pages": [],
            "next_page": None,
            "prev_page": None
        }

    pages = []
    current_page = None
    next_page = None
    prev_page = None

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

            pages.append({
                "page": page_num,
                "url": urljoin(BASE_URL, href)
            })

            # Detect prev/next
            if a.get("aria-label") == "Next":
                next_page = urljoin(BASE_URL, href)
            if a.get("aria-label") == "Previous":
                prev_page = urljoin(BASE_URL, href)

    # ---------------------------------------------
    # SPECIAL CASE: Page 1 has no "Next" in <nav>
    # ---------------------------------------------
    if current_page == 1 and next_page is None:
        right_p = soup.select_one("p.right")
        if right_p:
            a_tag = right_p.find("a")
            if a_tag and a_tag.get("href"):
                next_page = urljoin(BASE_URL, a_tag.get("href"))

    return {
        "current_page": current_page,
        "pages": pages,
        "next_page": next_page,
        "prev_page": prev_page
    }

@router.get("/albums", response_model=AlbumResponse)
def get_albums(page: int = Query(1, ge=1)):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    if page == 1:
        url = BASE_URL + "/"
    else:
        url = f"{BASE_URL}/telugu-songs?page={page}"

    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    return parse_albums(resp.text)

def parse_album_details(html: str) -> AlbumDetails:
    soup = BeautifulSoup(html, "html.parser")

    # Album name
    h1 = soup.find("h1")
    album_name = h1.get_text(strip=True) if h1 else ""

    # Album art
    img = soup.select_one("figure img")
    album_art = urljoin(BASE_URL, img.get("src")) if img else ""

    # Movie info
    info = soup.find("fieldset")
    starring = music = director = year = language = None

    if info:
        for b in info.find_all("b"):
            label = b.get_text(strip=True).rstrip(":").lower()
            value = b.next_sibling.strip() if b.next_sibling else ""

            if label == "starring":
                starring = value
            elif label == "music":
                music = value
            elif label == "director":
                director = value
            elif label == "year":
                year = value
            elif label == "language":
                language = value

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

@router.get("/album", response_model=AlbumDetails)
def get_album_details(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0",
    }

    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    return parse_album_details(resp.text)