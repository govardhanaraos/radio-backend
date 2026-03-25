import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
}
resp = requests.get("https://hindiflacs.com/Kohrra-2-Web-Series-2026-Ajrh2l-2", headers=headers)
with open("temp_kohrra.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
