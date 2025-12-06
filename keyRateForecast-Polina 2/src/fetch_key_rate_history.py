

import datetime as dt
import pandas as pd
import requests
from urllib.parse import urlencode


BASE_URL = "https://www.cbr.ru/hd_base/KeyRate/"
OUT_CSV = "data/labels/key_rate_history.csv"


def build_url(from_date: dt.date, to_date: dt.date) -> str:

    params = {
        "UniDbQuery.From": from_date.strftime("%d.%m.%Y"),
        "UniDbQuery.To": to_date.strftime("%d.%m.%Y"),
        "UniDbQuery.Posted": "True",
    }
    return BASE_URL + "?" + urlencode(params, encoding="utf-8")


def fetch_keyrate_table(from_date: dt.date, to_date: dt.date) -> pd.DataFrame:

    url = build_url(from_date, to_date)
    print(f"[fetch_key_rate_history] GET {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    tables = pd.read_html(resp.text, decimal=",", thousands=" ")
    if not tables:
        raise RuntimeError("Не удалось найти таблицу с ключевой ставкой на странице")

    df = tables[0].copy()

    df.columns = [c.strip() for c in df.columns]

    if "Дата" not in df.columns or "Ставка" not in df.columns:

        df = df.iloc[:, :2]
        df.columns = ["Дата", "Ставка"]

    df = df[["Дата", "Ставка"]].dropna()

    df["date"] = pd.to_datetime(df["Дата"], dayfirst=True, errors="coerce")
    df["rate"] = (
        df["Ставка"]
        .astype(str)
        .str.replace("\xa0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    df["rate"] = pd.to_numeric(df["rate"], errors="coerce")

    df = df.dropna(subset=["date", "rate"])[["date", "rate"]]
    df = df.sort_values("date").reset_index(drop=True)
    return df


def main():

    start_date = dt.date(2013, 9, 17)
    end_date = dt.date.today()

    df = fetch_keyrate_table(start_date, end_date)
    print(df.head())
    print(df.tail())

    OUT_PATH = OUT_CSV
    df.to_csv(OUT_PATH, index=False)
    print(f"[fetch_key_rate_history] OK, сохранено -> {OUT_PATH}, строк: {len(df)}")


if __name__ == "__main__":
    main()
