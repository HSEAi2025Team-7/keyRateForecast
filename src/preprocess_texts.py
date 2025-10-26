"""
Предобработка текстов пресс-релизов:
1) читаем data/raw/cbr_press/*.json
2) чистим и нормализуем текст
3) сохраняем data/processed/cbr_press_clean.csv
"""

import os, re, json, glob
import pandas as pd
from bs4 import BeautifulSoup
from nltk.corpus import stopwords
from razdel import tokenize
import pymorphy3

RAW_DIR = "data/raw/cbr_press"
OUT_CSV = "data/processed/cbr_press_clean.csv"

STOP_RU = set(stopwords.words("russian"))
MORPH = pymorphy3.MorphAnalyzer()

RE_URL = re.compile(r'https?://\S+|www\.\S+')
RE_HTML = re.compile(r'<[^>]+>')
RE_PUNCT = re.compile(r'[^\w\s]', re.UNICODE)
RE_MULTI_SPACE = re.compile(r'\s+')

# сокращения → разворачиваем в нормальные слова (пополняй, если нужно)
ABBR_MAP = {
    "рф": "российская федерация",
    "цб": "центральный банк",
    "цбр": "центральный банк россии",
    "сша": "соединенные штаты америки",
}

def clean_html(text: str) -> str:
    soup = BeautifulSoup(text, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    text = soup.get_text("\n")
    return text

def normalize_text(text: str) -> str:
    text = text.lower()
    text = RE_URL.sub(" ", text)
    text = RE_HTML.sub(" ", text)
    text = RE_PUNCT.sub(" ", text)
    text = RE_MULTI_SPACE.sub(" ", text).strip()
    return text

def expand_abbr(token: str) -> str:
    return ABBR_MAP.get(token, token)

def lemmatize_token(tok: str) -> str:
    # только слова из букв — тогда лемматизируем
    if re.fullmatch(r"[а-яёa-z]+", tok):
        p = MORPH.parse(tok)
        if p:
            return p[0].normal_form
    return tok

def preprocess_one(text: str) -> str:
    # 1) убрать HTML и привести к базовой форме
    text = clean_html(text)
    text = normalize_text(text)

    # 2) токенизация
    tokens = [t.text for t in tokenize(text)]

    # 3) обработка: аббревиатуры → разворачиваем, стоп-слова → удаляем, лемматизация
    out = []
    for tok in tokens:
        tok = expand_abbr(tok)
        if tok in STOP_RU:
            continue
        if len(tok) == 1:  # одиночные символы — шум
            continue
        tok = lemmatize_token(tok)
        out.append(tok)

    return " ".join(out)

def load_raw() -> pd.DataFrame:
    rows = []
    for path in glob.glob(os.path.join(RAW_DIR, "*.json")):
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        rows.append({
            "press_date": obj.get("date", ""),
            "title": obj.get("title", ""),
            "url": obj.get("url", ""),
            "text_raw": obj.get("text", ""),
        })
    return pd.DataFrame(rows)

if __name__ == "__main__":
    df = load_raw()
    if df.empty:
        raise SystemExit("Нет файлов в data/raw/cbr_press/*.json — запусти парсер сначала.")
    df["text_clean"] = df["text_raw"].apply(preprocess_one)
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"[OK] сохранено -> {OUT_CSV}; строк: {len(df)}")
