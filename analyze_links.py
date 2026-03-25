from bs4 import BeautifulSoup

with open("temp_kohrra.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

links = soup.find_all("a")
for a in links:
    if a.get('href') and ('page' in a['href'] or 'Kohrra' in a['href']):
        print(f"Link: {a.get_text(strip=True)} -> {a['href']}")

print("Checking pagination container:")
container = soup.find("div", class_="pagination")
if container:
    print(container)
else:
    print("No div.pagination found")
    
container2 = soup.find("div", class_="pagination-nav")
if container2:
    print(container2)
