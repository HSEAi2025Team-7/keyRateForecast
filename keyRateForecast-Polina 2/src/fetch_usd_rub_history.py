

import datetime as dt
import pandas as pd
import requests
import xml.etree.ElementTree as ET

OUT_CSV = "data/macro/usd_rub_daily.csv"
CBR_URL = "https://www.cbr.ru/scripts/XML_dynamic.asp"
USD_TAG = "R01235"  # код доллара США у ЦБ


def fetch_usd_history(start_date: dt.date, end_date: dt.date) -> pd.DataFrame:
    params = {
        "date_req1": start_date.strftime("%d/%m/%Y"),
        "date_req2": end_date.strftime("%d/%m/%Y"),
        "VAL_NM_RQ": USD_TAG,
    }
    print(f"[fetch_usd_rub_history] GET {CBR_URL} with {params}")
    resp = requests.get(CBR_URL, params=params, timeout=30)
    resp.raise_for_status()

    # Ответ в windows-1251
    resp.encoding = "windows-1251"
    root = ET.fromstring(resp.text)

    rows = []
    for rec in root.findall("Record"):
        date_str = rec.attrib.get("Date")
        value_str = rec.findtext("Value")
        if not date_str or not value_str:
            continue
        date = dt.datetime.strptime(date_str, "%d.%m.%Y").date()
        rate = float(value_str.replace(",", "."))
        rows.append({"date": date, "usd_rub": rate})

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    return df


def main():
    start_date = dt.date(2013, 9, 17)
    end_date = dt.date.today()

    df = fetch_usd_history(start_date, end_date)
    print(df.head())
    print(df.tail())

    df.to_csv(OUT_CSV, index=False)
    print(f"[fetch_usd_rub_history] OK, сохранено -> {OUT_CSV}, строк: {len(df)}")


if __name__ == "__main__":
    main()
