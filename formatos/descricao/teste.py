import requests
from bs4 import BeautifulSoup
import re

keyword = "passagem de ônibus para são paulo"

url = "https://www.google.com/search"

params = {
    "q": keyword,
    "num": 10,
    "hl": "pt-BR",
    "gl": "br"
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

response = requests.get(url, params=params, headers=headers)
soup = BeautifulSoup(response.text, "html.parser")

results = []
for block in soup.select("div.tF2Cxc, div.g"):
    title_tag = block.select_one("h3")
    link_tag = block.select_one("a")
    snippet_tag = block.select_one("div.VwiC3b, span.aCOpRe")
    if title_tag and link_tag and link_tag.get("href", "").startswith("http"):
        results.append({
            "titulo": title_tag.get_text(),
            "link": link_tag["href"],
            "snippet": snippet_tag.get_text() if snippet_tag else ""
        })

for i, r in enumerate(results[:10], start=1):
    print(f"{i}. {r['titulo']}\n   {r['link']}\n   {r['snippet']}\n")

print(f"Total capturado: {len(results)}")