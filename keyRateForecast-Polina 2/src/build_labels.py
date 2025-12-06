

import pandas as pd

INP = "data/labels/key_rate_history.csv"
OUT = "data/labels/key_rate_labels.csv"


def to_label(diff: float):
    """Переводим разницу ставки в метку -1/0/1/NaN."""
    if pd.isna(diff):
        # нет следующей даты -> отсутствует метка
        return pd.NA
    if diff == 0:
        return 0
    return 1 if diff > 0 else -1


def main():
    print(f"[build_labels] читаю историю ставок из {INP}...")
    hist = pd.read_csv(INP)

    # дата парсинг
    hist["date"] = pd.to_datetime(hist["date"])
    hist = hist.sort_values("date").reset_index(drop=True)

    # ставка на следующем заседании
    hist["rate_next"] = hist["rate"].shift(-1)

    # difference and label/ метка
    diff = hist["rate_next"] - hist["rate"]
    hist["label"] = diff.apply(to_label)

    # raws only with (label не NaN)
    out = hist.dropna(subset=["label"]).copy()

    # label --> (Int64)
    out["label"] = out["label"].astype("Int64")

    out.to_csv(OUT, index=False)
    print(f"[build_labels] OK, labels saved -> {OUT}")
    print(out[["date", "rate", "rate_next", "label"]].head(10))


if __name__ == "__main__":
    main()
