import time
import httpx
from bs4 import BeautifulSoup
import csv
import requests

def get_press():
    base_url = "https://www.cbr.ru"
    ajax_url = "https://www.cbr.ru/Handlers/NewsHandler.ashx?type=press_release&From="
    links, seen = [], set()
    offset = 0
    step = 20

    while True:
        r = httpx.get(f"{ajax_url}{offset}&To={offset+step}", timeout=20)
        html = r.text.strip()
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select('a[href^="/press/event/"], a[href^="/press/pr/"]'):
            href = base_url + a["href"]
            if href not in seen:
                seen.add(href)
                links.append(href)

        print(f"Собрано ссылок - {len(links)} (offset={offset})")
        offset += step
        time.sleep(0.2)

    with open("cbr_press_releases.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(links))

    print("Готово, всего ссылок:", len(links))


get_press()

# загрузка контента
with open('cbr_press_releases.txt', 'r', encoding='utf-8') as f:
    l = [i.strip() for i in f if i.strip()]

with open('cbr_press_releases.csv', 'w', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(['date', 'title', 'text', 'url'])
    for i in l:
        response = requests.get(i)
        soup = BeautifulSoup(response.text, "lxml")
        text = soup.find('div', {'class': 'landing-text'})
        text = text.get_text(" ", strip=True) if text else ""
        title = soup.find('h1')
        title = title.get_text(strip=True) if title else ""
        date = soup.find('div', {'class': 'col-md-6 col-12 news-info-line_date'})
        date = date.get_text(strip=True) if date else ""
        writer.writerow([date, title, text, i])