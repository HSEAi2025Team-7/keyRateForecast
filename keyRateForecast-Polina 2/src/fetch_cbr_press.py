

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
os.makedirs(SAVE_DIR, exist_ok=True)

SEED_URLS = [
    "https://www.cbr.ru/press/press_release/",
    "https://www.cbr.ru/press/keypr/",
    "https://www.cbr.ru/news/#tab_4"
]
KEYWORDS = [
    "ключев", "ставк", "процентн", "рефинансир", "монетарн", "денежно-кредитн",
    "совет директор", "решение", "центральн банк", "ЦБ", "Банк России",
    "инфляц", "дефляц", "потребительск цен", "индекс цен", "ценов", "рост цен", "удорожан", "подорожан",
    "обменн курс", "курс рубл", "доллар", "евро", "валютн рынок", "ослаблен рубл", "укреплен рубл",
    "санкц", "ограничен импорт", "ограничен экспорт", "пакет санкц", "санкционн давление",
    "геополитическ", "внешнеполитическ", "международн резерв", "SWIFT", "капиталов поток", "отток капитала",
    "ВВП", "экономическ рост", "спад", "замедлен рост", "рецесс", "оживлен экономик", "делов активн",
    "производств", "промышленн производств", "инвестици", "потребительск спрос", "внутренн спрос",
    "облигаци", "доходност", "гособлигаци", "ОФЗ", "фондов рынок", "акц", "инвестор", "ликвидност",
    "кредитн рынок", "депозит", "межбанковск", "ликвидн", "ставк межбанк",
    "фискальн", "бюджетн дефицит", "расход", "доход", "налог", "госдолг", "резервн фонд", "нац проект", "госпрограмм",
    "занятост", "безработиц", "рынок труд", "заработн плат", "доход населени", "производительност труд",
    "ожидан", "прогноз", "перспектив", "оцен", "риск", "неопределенност", "довер", "ожидает повышение", "ожидает снижение",
    "нефть", "газ", "сырь", "экспорт", "импорт", "энергоресурс", "цена на нефть", "ценн металлы",
    "сырьев", "внешн торг", "баланс", "дефицит торгов", "избыточн торгов",
    "ипотек", "потребительск кредит", "банковск сектор", "платежеспособн", "кредитн активн", "уровень долга",
    "ФРС", "ЕЦБ", "ставк ФРС", "ставк ЕЦБ", "глобальн рынок", "миров экономик", "международн инфляц"
]

HEADERS = {"User-Agent": "Mozilla/5.0 (KeyRateForecast bot for learning)"} #заголовок юзер агента для запросов содержит информацию о боте, защита от блокировок

DATE_PAT = re.compile(
    r"\b(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})\b|"   
    r"\b(\d{1,2})\s+([А-Яа-я]+)\s+(\d{4})\b"
)

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




def normalize_link(base: str, href: str) -> str | None:
    if not href or href.startswith("#"): return None
    full = urljoin(base, href)
    full, _ = urldefrag(full)
    return full

def parse_any_date(text: str) -> str: 

    m = DATE_PAT.search(text)
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

        d, mon_ru, y = int(m.group(4)), m.group(5).lower(), int(m.group(6))
        mo = MONTHS_RU.get(mon_ru)
        if not mo: return ""
        try:
            return datetime(y, mo, d).date().isoformat()
        except Exception:
            return ""

def extract_date_title(soup: BeautifulSoup) -> tuple[str, str]:
    title = soup.find("h1").get_text(strip=True)

    txt = clean_text(str(soup))
    date_iso = parse_any_date(txt)
    return date_iso, title

def save_json(url: str, date_iso: str, title: str, text: str) -> None:


    h = hashlib.md5(url.encode("utf-8")).hexdigest()[:12]
    prefix = date_iso if date_iso else "nodate"
    fname = f"{prefix}_{h}.json"
    path = os.path.join(SAVE_DIR, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"url": url, "date": date_iso, "title": title, "text": text},
                  f, ensure_ascii=False, indent=2)

def crawl(seed_urls: list[str], max_pages: int = 1200, max_saved: int = 400, delay: float = 0.2) -> None:
    queue: list[str] = list(seed_urls)
    seen: set[str] = set()
    saved = 0
    while queue and len(seen) < max_pages and saved < max_saved:
        url = queue.pop(0)

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

if __name__ == "__main__":
    print("[START] Обход ЦБ…") 
    crawl(SEED_URLS, max_pages=5000, max_saved=1000, delay=0.2)
    print("[DONE] Смотри файлы в data/raw/cbr_press/")
