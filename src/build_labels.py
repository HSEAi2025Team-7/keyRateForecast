"""
Очень простой скрипт:
1) Читает data/labels/key_rate_history.csv (date, rate).
2) Сортирует по дате.
3) Сравнивает ставку со "следующей" датой.
4) Выдаёт метку: -1/0/1 на КАЖДУЮ дату, где есть "следующая".
5) Сохраняет в data/labels/key_rate_labels.csv
"""

import pandas as pd

INP = "data/labels/key_rate_history.csv"
OUT = "data/labels/key_rate_labels.csv"

hist = pd.read_csv(INP, parse_dates=["date"])
hist = hist.sort_values("date").reset_index(drop=True)

# rate_next = ставка на следующей дате
hist["rate_next"] = hist["rate"].shift(-1)

def to_label(diff):
    # если diff > 0 -> выросла -> 1
    # если diff < 0 -> упала  -> -1
    # если diff == 0 или NaN -> 0 (нет движения или последняя строка)
    if pd.isna(diff) or diff == 0:
        return 0
    return 1 if diff > 0 else -1

hist["label"] = (hist["rate_next"] - hist["rate"]).apply(to_label)

# убираем последнюю строку (у неё нет следующей даты)
out = hist.dropna(subset=["rate_next"]).copy()

out.to_csv(OUT, index=False)
print(f"[OK] labels saved -> {OUT}")
print(out[["date","rate","rate_next","label"]].head(10))
