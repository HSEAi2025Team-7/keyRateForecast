"""
Простой парсер всех пресс - релизов ЦБ РФ:
— обходит стартовые страницы
— ищет ссылки только внутри cbr.ru и раздела /press/
— если на странице есть слова про ключевую ставку — сохраняем JSON

Файлы: data/raw/cbr_press/YYYY-MM-DD_<hash>.json
"""

import time
import httpx
from bs4 import BeautifulSoup
import csv
import requests

# >>> ADDED (для обработки дат "как во втором коде")
import re
from datetime import datetime

# >>> ADDED (регэксп и месяцы на русском)
DATE_PAT = re.compile(
    r"\b(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})\b|"   # 24.10.2025
    r"\b(\d{1,2})\s+([А-Яа-я]+)\s+(\d{4})\b"                    # 24 октября 2025
)
MONTHS_RU = {
    "января":1, "февраля":2, "марта":3, "апреля":4, "мая":5, "июня":6,
    "июля":7, "августа":8, "сентября":9, "октября":10, "ноября":11, "декабря":12
}

# >>> ADDED (функция нормализации даты в ISO)
def parse_any_date(text: str) -> str:
    m = DATE_PAT.search(text or "")
    if not m:
        return ""
    if m.group(1) and m.group(2) and m.group(3):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100: y += 2000
        try:
            return datetime(y, mo, d).date().isoformat()
        except Exception:
            return ""
    else:
        d, mon_ru, y = int(m.group(4)), (m.group(5) or "").lower(), int(m.group(6))
        mo = MONTHS_RU.get(mon_ru)
        if not mo:
            return ""
        try:
            return datetime(y, mo, d).date().isoformat()
        except Exception:
            return ""

def get_press():
    base_url = "https://www.cbr.ru"
    ajax_url = "https://www.cbr.ru/Crosscut/NewsList/LoadMore/84035?intOffset=0&extOffset="
    links, seen = [], set()
    offset = 0

    while True:
        r = httpx.get(f"{ajax_url}{offset}", timeout=20, follow_redirects=True)
        html = r.text.strip()
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select('a[href^="/press/pr/?file="]'):
            href = base_url + a["href"]
            if href not in seen:
                seen.add(href)
                links.append(href)

        print(f"Собрано ссылок - {offset}")
        offset += 1
        time.sleep(0.2)

    with open("cbr_press_releases.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(links))

    print("Готово")


get_press()

with open('cbr_press_releases.txt', 'r', encoding='utf-8') as f:
    link = f.readlines()
l = []
for i in link:
    if '\n' in i:
        l.append(i[:-1])

# >>> CHANGED (доб. newline="" для корректной записи CSV в Windows, не обязательно, но безопасно)
with open('cbr_key-rate_press_releases.csv', 'w', encoding='utf-8', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['date', 'title', 'text', 'url']) # делаем таблицу с данными
    for i in l: # добавляем по каждой ссылке данные в таблицу
        response = requests.get(i)
        soup = BeautifulSoup(response.text, "lxml")
        text = soup.find('div', {'class': 'landing-text'}).get_text("\n", strip=True) if soup.find('div', {'class': 'landing-text'}) else soup.get_text(" ", strip=True)
        title = soup.find('h1').get_text(strip=True) if soup.find('h1') else (soup.title.get_text(strip=True) if soup.title else "")

        # >>> CHANGED (получение даты: сначала из блока даты, затем fallback через parse_any_date)
        date_node = soup.find('div', {'class': re.compile(r'news-info-line_date')})  # допускаем вариации класса
        if date_node:
            date = parse_any_date(date_node.get_text(" ", strip=True))
        else:
            page_text = soup.get_text(" ", strip=True)
            date = parse_any_date(page_text)

        writer.writerow([date, title, text, i])
