import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
}
resp = requests.get("https://hindiflacs.com/Kohrra-2-Web-Series-2026-Ajrh2l-2", headers=headers)
soup = BeautifulSoup(resp.text, "html.parser")
pagination = soup.find("div", class_="pagination")
print("Pagination div:", pagination)
print("All pagination divs:", soup.find_all(class_=lambda x: x and "pagin" in x.lower()))
