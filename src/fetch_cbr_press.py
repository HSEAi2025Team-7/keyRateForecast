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

with open('cbr_key-rate_press_releases.csv', 'w', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(['date', 'title', 'text', 'url']) # делаем таблицу с данными
    for i in l: # добавляем по каждой ссылке данные в таблицу
        response = requests.get(i)
        soup = BeautifulSoup(response.text, "lxml")
        text = soup.find('div', {'class': 'landing-text'}).text
        title = soup.find('h1').text
        date = soup.find('div', {'class': 'col-md-6 col-12 news-info-line_date'}).text
        writer.writerow([date, title, text, i])



import os, re, time, json, hashlib
from urllib.parse import urljoin, urldefrag, urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SAVE_DIR = "data/raw/cbr_press"
os.makedirs(SAVE_DIR, exist_ok=True) #из системы/библиотеки ос берем метод создания директории

SEED_URLS = [
    "https://www.cbr.ru/press/press_release/",
    "https://www.cbr.ru/press/keypr/",
    "https://www.cbr.ru/news/#tab_4"
] #стартовые страницы для обхода (на этих страницах гиперссылки на пресс-релизы, эти пресс релизы мы и будем сохранять)

KEYWORDS = ["ключев", "ставк", "процентн", "решение", "совет директор"] #ключевые слова для поиска в тексте пресс-релиза
HEADERS = {"User-Agent": "Mozilla/5.0 (KeyRateForecast bot for learning)"} #заголовок юзер агента для запросов содержит информацию о боте, защита от блокировок
# Регулярное выражение для поиска дат в тексте библиотека питона для поиска дат в формате (форматы: 24.10.2025 и 24 октября 2025)
DATE_PAT = re.compile(
    r"\b(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})\b|"   # 24.10.2025
    r"\b(\d{1,2})\s+([А-Яа-я]+)\s+(\d{4})\b"                    # 24 октября 2025
)
# Словарь для преобразования русских названий месяцев в числа
MONTHS_RU = {
    "января":1, "февраля":2, "марта":3, "апреля":4, "мая":5, "июня":6,
    "июля":7, "августа":8, "сентября":9, "октября":10, "ноября":11, "декабря":12
}

def make_session():
    s = requests.Session()
    retry = Retry(
        total=5, backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s

SESSION = make_session()

def get_soup(url: str):
    r = SESSION.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    text = soup.get_text("\n")
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()

def text_has_keywords(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in KEYWORDS)


def same_domain_cbr(url: str) -> bool:
    try:
        return "cbr.ru" in urlparse(url).netloc
    except Exception:
        return False

ALLOW_SAVE_PATHS = ("/press/", "/news/")  # сохраняем только эти разделы
BLOCKLIST_SUBSTR = (
    "sitemap", "search", "rss", "mailto:", "contact", "kontakt",
    "glossary", "/doc", "/document", "/img", "/images", "/upload"
)

def url_can_be_saved(url: str) -> bool:
    p = urlparse(url)
    if "cbr.ru" not in p.netloc:
        return False
    if not any(seg in p.path for seg in ALLOW_SAVE_PATHS):
        return False
    if any(b in url for b in BLOCKLIST_SUBSTR):
        return False
    return True




def normalize_link(base: str, href: str) -> str | None: # href - ссылка которая может быть относительной или абсолютной
    if not href or href.startswith("#"): return None # если ссылка пустая или якорь, то возвращаем None
    full = urljoin(base, href) # преобразуем относительную ссылку в абсолютную
    full, _ = urldefrag(full) # удаляем фрагмент (якорь) из ссылки
    return full # возвращаем нормализованную ссылку

def parse_any_date(text: str) -> str: 
    """
    Пытаемся вытащить дату из текста и вернуть в виде YYYY-MM-DD.
    Если не получилось — вернём пустую строку.
    """
    m = DATE_PAT.search(text)
    if not m: 
        return ""
    if m.group(1) and m.group(2) and m.group(3):
        # Формат с цифрами: 24.10.2025
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100: y += 2000
        try:
            return datetime(y, mo, d).date().isoformat()
        except Exception:
            return ""
    else:
        # Формат с русским месяцем: 24 октября 2025
        d, mon_ru, y = int(m.group(4)), m.group(5).lower(), int(m.group(6))
        mo = MONTHS_RU.get(mon_ru)
        if not mo: return ""
        try:
            return datetime(y, mo, d).date().isoformat()
        except Exception:
            return ""

def extract_date_title(soup: BeautifulSoup) -> tuple[str, str]:
    title = soup.find("h1").get_text(strip=True) if soup.find("h1") else (soup.title.get_text(strip=True) if soup.title else "")
    # попытаемся искать дату в «видимом» тексте
    txt = clean_text(str(soup))
    date_iso = parse_any_date(txt)
    return date_iso, title

def save_json(url: str, date_iso: str, title: str, text: str) -> None:
    """
    Без длинных имён! Имя файла короткое: YYYY-MM-DD_<hash>.json,
    либо nodate_<hash>.json
    """
    h = hashlib.md5(url.encode("utf-8")).hexdigest()[:12]
    prefix = date_iso if date_iso else "nodate"
    fname = f"{prefix}_{h}.json"
    path = os.path.join(SAVE_DIR, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"url": url, "date": date_iso, "title": title, "text": text},
                  f, ensure_ascii=False, indent=2)
# стрелочка ноне указывает что функция возвращает ничего (None) это процедура и мы задаем только тип возвращаемого значения
def crawl(seed_urls: list[str], max_pages: int = 1200, max_saved: int = 400, delay: float = 0.2) -> None: # функция обхода страниц аргументы это список строк и максимальное количество страниц для обхода (можем положить только цифру, 200-значение по умолчанию)
    queue: list[str] = list(seed_urls) # создали перменную кью, задали ее тип, заполнили ссылками. Создаем очередь для обхода страниц и инициализируем ее стартовыми URL
    seen: set[str] = set() # кью - это очередь - алгоритм путинга, множество для уже посещённых URL (паутина) син - мнжество страничек которые мы уже видели
    saved = 0 #счетчик сохранённых страниц

    while queue and len(seen) < max_pages and saved < max_saved: #пока в очереди есть ссылки и мы не достигли максимального количества сохранённых страниц
        url = queue.pop(0) # вытаскиваем первый URL из очереди
         # если мы уже видели эту ссылку, то пропускаем её
        if url in seen:
            continue
        seen.add(url) # отмечаем ссылку как увиденную (добавляем в множество seen)

        try:
            soup = get_soup(url) #пытаемся скачать страницу и распарсить ее c помощью BeautifulSoup библиотеки
        except Exception as e: # если не получилось, то ловим ошибку и выводим предупреждение
            print(f"[WARN] не скачали {url}: {e}")
            continue

         # Сохраняем ТОЛЬКО страницы из /press/
        
        

        #добавляем любые ссылки внутри cbr.ru в очередь
        for a in soup.find_all("a"):  #ищем все гиперссылки на странице (теги а) и добавляем их в очередь
            href = normalize_link(url, a.get("href")) #нормализуем ссылку (преобразуем относительные ссылки в абсолютные)
            if href and same_domain_cbr(href) and href not in seen: #если ссылка валидная и мы её ещё не видели то добавляем её в очередь
                if not any(b in href for b in ("#","?share=","javascript:")):
                    queue.append(href)

        # пагинация: кнопка "Загрузить ещё" и похожие
        for a in soup.find_all("a"):
            txt = (a.get_text(" ", strip=True) or "").lower()
            if any(s in txt for s in ("загрузить ещё", "загрузить еще", "показать ещё", "показать еще", "ещё", "еще", "следующ")):
                href = normalize_link(url, a.get("href"))
                if href and same_domain_cbr(href) and href not in seen:
                    queue.append(href)

        # дополнительные ajax-атрибуты на кнопках
        for tag in soup.find_all(True):
            for attr in ("data-ajax", "data-url", "data-href", "data-ajax-url"):
                val = tag.get(attr)
                if val:
                    href = normalize_link(url, val)
                    if href and same_domain_cbr(href) and href not in seen:
                        queue.append(href)

        # сохраняем только релевантные разделы
        if not url_can_be_saved(url):
            time.sleep(delay)
            continue


        text = clean_text(str(soup)) # очищаем текст страницы от HTML тегов и скриптов
         # Проверяем наличие ключевых слов в тексте
        if text_has_keywords(text): #если в тексте есть ключевые слова, то сохраняем страницу
            date_iso, title = extract_date_title(soup) #пытаемся извлечь дату и заголовок страницы
             # Сохраняем JSON
            try:
                save_json(url, date_iso, title, text)
                saved += 1 #увеличиваем счётчик сохранённых страниц
                print(f"[OK] сохранено: {url}")
            except Exception as e:
                print(f"[WARN] не сохранили {url}: {e}")

        time.sleep(0.05)

    print(f"[DONE] Просмотрено: {len(seen)}, сохранено: {saved}")
    print(f"[INFO] Осталось в очереди: {len(queue)} (можно увеличить max_pages/max_saved)")
# Запуск парсера при вызове файла напрямую где __name__ == "__main__" означает что файл запущен напрямую а не импортирован
if __name__ == "__main__": # мы запускаем один файл напрямую а не весь проект целиком
    print("[START] Обход ЦБ…") 
    crawl(SEED_URLS, max_pages=1200, max_saved=300, delay=0.2)  # вызываем функцию обхода с ограничением по количеству страниц
    print("[DONE] Смотри файлы в data/raw/cbr_press/")
