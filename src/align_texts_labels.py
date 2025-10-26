"""
Матчим пресс-релизы к ближайшей СЛЕДУЮЩЕЙ дате заседания (и метке -1/0/1).
Вход:
- data/processed/cbr_press_clean.csv  (press_date, text_clean, url, title)
- data/labels/key_rate_labels.csv     (date, rate, rate_next, label)

Выход:
- data/processed/dataset_labeled.csv  (press_date, meeting_date, label, text_clean, title, url)
"""

import pandas as pd
from datetime import datetime

PRESS_CSV = "data/processed/cbr_press_clean.csv"
LABELS_CSV = "data/labels/key_rate_labels.csv"
OUT_CSV = "data/processed/dataset_labeled.csv"

def parse_date_any(x):
    # пробуем несколько форматов
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(str(x).strip(), fmt)
        except Exception:
            continue
    return pd.NaT

press = pd.read_csv(PRESS_CSV)
labels = pd.read_csv(LABELS_CSV, parse_dates=["date"])

press["press_date_parsed"] = press["press_date"].apply(parse_date_any)
press = press.dropna(subset=["press_date_parsed"]).copy()
press = press.sort_values("press_date_parsed")

labels = labels.sort_values("date")

def find_next_label(d):
    future = labels[labels["date"] >= d]
    if len(future)==0:
        return pd.NA, pd.NA
    row = future.iloc[0]
    return row["date"].date().isoformat(), int(row["label"])

press["meeting_date"], press["label"] = zip(*press["press_date_parsed"].apply(find_next_label))
ds = press.dropna(subset=["label"]).copy()

cols = ["press_date_parsed","meeting_date","label","title","url","text_clean"]
ds = ds[cols].rename(columns={"press_date_parsed":"press_date"})

ds.to_csv(OUT_CSV, index=False)
print(f"[OK] сохранено -> {OUT_CSV}; строк: {len(ds)}")
