"""
Простой парсер релизов ЦБ РФ:
— обходит стартовые страницы
— ищет ссылки только внутри cbr.ru и раздела /press/
— если на странице есть слова про ключевую ставку — сохраняем JSON

Файлы: data/raw/cbr_press/YYYY-MM-DD_<hash>.json
"""

import os, re, time, json, hashlib
from urllib.parse import urljoin, urldefrag, urlparse
import requests
from bs4 import BeautifulSoup
from datetime import datetime

SAVE_DIR = "data/raw/cbr_press"
os.makedirs(SAVE_DIR, exist_ok=True)

SEED_URLS = [
    "https://www.cbr.ru/press/press_release/",
    "https://www.cbr.ru/press/keypr/",
]

KEYWORDS = ["ключев", "ставк", "процентн", "решение", "совет директор"]
HEADERS = {"User-Agent": "Mozilla/5.0 (KeyRateForecast bot for learning)"}

DATE_PAT = re.compile(
    r"\b(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})\b|"   # 24.10.2025
    r"\b(\d{1,2})\s+([А-Яа-я]+)\s+(\d{4})\b"                    # 24 октября 2025
)

MONTHS_RU = {
    "января":1, "февраля":2, "марта":3, "апреля":4, "мая":5, "июня":6,
    "июля":7, "августа":8, "сентября":9, "октября":10, "ноября":11, "декабря":12
}

def get_soup(url: str):
    r = requests.get(url, headers=HEADERS, timeout=30)
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

def url_is_press(url: str) -> bool:
    """Сохраняем только пресс-разделы, чтобы не захватывать контакты и прочее."""
    try:
        p = urlparse(url)
        return "cbr.ru" in p.netloc and "/press/" in p.path
    except Exception:
        return False

def normalize_link(base: str, href: str) -> str | None:
    if not href or href.startswith("#"): return None
    full = urljoin(base, href)
    full, _ = urldefrag(full)
    return full

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

def crawl(seed_urls: list[str], max_pages: int = 200) -> None:
    queue: list[str] = list(seed_urls)
    seen: set[str] = set()
    saved = 0

    while queue and len(seen) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)

        try:
            soup = get_soup(url)
        except Exception as e:
            print(f"[WARN] не скачали {url}: {e}")
            continue

        # Добавляем новые ссылки
        for a in soup.find_all("a"):
            href = normalize_link(url, a.get("href"))
            if href and href not in seen:
                queue.append(href)

        # Сохраняем ТОЛЬКО страницы из /press/
        if not url_is_press(url):
            time.sleep(0.05)
            continue

        text = clean_text(str(soup))
        if text_has_keywords(text):
            date_iso, title = extract_date_title(soup)
            try:
                save_json(url, date_iso, title, text)
                saved += 1
                print(f"[OK] сохранено: {url}")
            except Exception as e:
                print(f"[WARN] не сохранили {url}: {e}")

        time.sleep(0.05)

    print(f"[DONE] Просмотрено: {len(seen)}, сохранено: {saved}")

if __name__ == "__main__":
    print("[START] Обход ЦБ…")
    crawl(SEED_URLS, max_pages=300)
    print("[DONE] Смотри файлы в data/raw/cbr_press/")
