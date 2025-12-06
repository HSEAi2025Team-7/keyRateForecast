

import pandas as pd
import requests
from pathlib import Path

INFL_URL = "https://www.cbr.ru/hd_base/infl/"
OUT_CSV = "data/macro/inflation_keyrate.csv"


def fetch_inflation_table() -> pd.DataFrame:
    print(f"[fetch_inflation_history] GET {INFL_URL}")
    resp = requests.get(INFL_URL, timeout=30)
    resp.raise_for_status()

    # pandas.read_html сам распарсит таблицу
    from io import StringIO
    tables = pd.read_html(StringIO(resp.text), decimal=",", thousands=" ")


    if not tables:
        raise RuntimeError("Не удалось найти таблицу инфляции на странице ЦБ")

    df = tables[0].copy()
    print("[fetch_inflation_history] исходные колонки:", list(df.columns))

    # Ожидаемые русские названия колонок
    # На всякий случай приведём их к строкам без лишних пробелов
    df.columns = [str(c).strip() for c in df.columns]

    col_date = "Дата"
    col_key = "Ключевая ставка, % годовых"
    col_infl = "Инфляция, % г/г"
    col_target = "Цель по инфляции, %"

    # Проверка, что всё на месте
    for c in [col_date, col_key, col_infl, col_target]:
        if c not in df.columns:
            raise RuntimeError(f"Ожидалась колонка '{c}', но её нет в таблице ЦБ")

    # Парсим дату
    df["date"] = pd.to_datetime(df[col_date], dayfirst=True, errors="coerce")

    # Числовые поля: меняем запятую на точку и приводим к float
    def to_float(series):
        return (
            series.astype(str)
            .str.replace("\xa0", "", regex=False)
            .str.replace(" ", "", regex=False)
            .str.replace(",", ".", regex=False)
            .astype(float)
        )

    df["key_rate_monthly"] = to_float(df[col_key])
    df["inflation_yoy"] = to_float(df[col_infl])
    df["target_inflation"] = to_float(df[col_target])

    # Оставляем только нужные колонки и выбрасываем строки без даты
    df = df[["date", "key_rate_monthly", "inflation_yoy", "target_inflation"]]
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    print("[fetch_inflation_history] пример данных:")
    print(df.head())
    print(df.tail())

    return df


def main():
    df = fetch_inflation_table()

    out_path = Path(OUT_CSV)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"[fetch_inflation_history] OK, сохранено -> {out_path}, строк: {len(df)}")


if __name__ == "__main__":
    main()
