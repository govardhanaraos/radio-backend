from fastapi import FastAPI, Query, APIRouter
from pydantic import BaseModel
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://masstelugu.com"


router = APIRouter(
    prefix="/masstelugu",
    tags=["Stations"],
)


class Album(BaseModel):
    album_name: str
    album_art: str
    starring: Optional[str]
    music: Optional[str]
    director: Optional[str]
    link: str


class AlbumResponse(BaseModel):
    albums: List[Album]
    next_page: Optional[str]


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

    # next page link (like /telugu-songs?page=2)
    next_page_tag = soup.select_one('p.right a')
    if next_page_tag:
        next_href = next_page_tag.get("href", "").strip()
        next_page = urljoin(BASE_URL, next_href)
    else:
        next_page = None

    return AlbumResponse(albums=albums, next_page=next_page)


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