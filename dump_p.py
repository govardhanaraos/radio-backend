from bs4 import BeautifulSoup
with open("temp_kohrra.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")
p = soup.find("div", class_="pagination")
if p:
    open("p_out.txt", "w", encoding="utf-8").write(p.prettify())
