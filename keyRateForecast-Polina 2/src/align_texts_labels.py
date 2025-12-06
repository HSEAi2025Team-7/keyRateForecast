

import pandas as pd
from datetime import datetime

PRESS_CSV = "data/processed/cbr_press_clean.csv"
LABELS_CSV = "data/labels/key_rate_labels.csv"
OUT_CSV = "data/processed/dataset_labeled.csv"


def main():
    print(f"[align_texts_labels] читаю пресс-релизы из {PRESS_CSV}...")
    press = pd.read_csv(PRESS_CSV)

    # парсинг инфо даты из релизов
    press["press_date"] = pd.to_datetime(press["press_date"])

    # читаем и сочетаем метка-> заседание
    print(f"[align_texts_labels] читаю метки заседаний из {LABELS_CSV}...")
    labels = pd.read_csv(LABELS_CSV, parse_dates=["date"])
    labels = labels.sort_values("date").reset_index(drop=True)

    # сортируем пресс-релизы для merge_asof
    press = press.sort_values("press_date").reset_index(drop=True)

    # merge_asof: к каждому press_date прицепляем ближайший date >= press_date
    # direction="forward" = "следующее" дате/ часу / времени
    print("[align_texts_labels] маплю каждый пресс-релиз к ближайшему следующему заседанию...")
    merged = pd.merge_asof(
        press,
        labels,
        left_on="press_date",
        right_on="date",
        direction="forward",
    )

    # meeting_date = дата заседания (может быть NaT, если заседания нет)
    merged["meeting_date"] = merged["date"]

    # decision = label по ставке (-1/0/1 или NaN)
    merged = merged.rename(columns={"label": "decision"})

    # приводим meeting_date к строке (YYYY-MM-DD), но в CSV храним как есть (Timestamp тоже ок)

    merged["meeting_date"] = merged["meeting_date"].dt.date.astype("string")

    # ключевые колонки
    cols = ["press_date", "meeting_date", "decision", "title", "url", "text_clean"]
    ds = merged[cols].copy()

    ds.to_csv(OUT_CSV, index=False)
    print(f"[align_texts_labels] OK, сохранено -> {OUT_CSV}; строк: {len(ds)}")
    print(ds.head(5))


if __name__ == "__main__":
    main()
