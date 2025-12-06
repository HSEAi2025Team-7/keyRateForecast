

import pandas as pd

INP = "data/processed/dataset_labeled.csv"
OUT = "data/processed/dataset_timeline.csv"


def detect_announcements(df: pd.DataFrame) -> pd.Series:
    """
    детект анаунсмен - это функция для определения пресс-релизов, где объявлено решение по ключевой ставке.
    Логика:
        - заголовок содержит что-то про "ключевую ставку"
        - или URL содержит характерные куски "/keypr/", "keyrate", "key.htm" и т.п.
    """
    title = df["title"].fillna("").str.lower()
    url = df["url"].fillna("").str.lower()

    mask_title = (
        title.str.contains("ключев", na=False) &
        title.str.contains("ставк", na=False)
    )

    mask_url = url.str.contains(
        r"keyrate|key_rate|/keypr/|key\.htm",
        regex=True,
        na=False
    )

    return mask_title | mask_url


def main():
    print(f"[build_timeline_flags] читаю датасет из {INP}...")
    df = pd.read_csv(INP)

    df["press_date"] = pd.to_datetime(df["press_date"])

    if "meeting_date" in df.columns:
        df["meeting_date"] = pd.to_datetime(df["meeting_date"], errors="coerce")

    df = df.sort_values("press_date").reset_index(drop=True)

    print("[build_timeline_flags] определяю is_announcement по title/url...")
    df["is_announcement"] = detect_announcements(df)

    print("[build_timeline_flags] считаю prev_announcement_date / next_announcement_date...")

    ann_dates = df["press_date"].where(df["is_announcement"])

    # предыдущий анонс (ffill)
    df["prev_announcement_date"] = ann_dates.ffill()

    # следующий анонс (bfill)
    df["next_announcement_date"] = ann_dates.bfill()

    df["is_between"] = (
        (~df["is_announcement"]) &
        df["prev_announcement_date"].notna() &
        df["next_announcement_date"].notna()
    )

    # prev/next как строки формата YYYY-MM-DD
    df["prev_announcement_date"] = df["prev_announcement_date"].dt.date.astype("string")
    df["next_announcement_date"] = df["next_announcement_date"].dt.date.astype("string")

    base_cols = ["press_date", "meeting_date", "decision", "title", "url", "text_clean"]
    flag_cols = ["is_announcement", "is_between", "prev_announcement_date", "next_announcement_date"]

    cols = [c for c in base_cols + flag_cols if c in df.columns]
    df_out = df[cols].copy()

    df_out.to_csv(OUT, index=False)
    print(f"[build_timeline_flags] OK, сохранено -> {OUT}; строк: {len(df_out)}")
    print(df_out.head(5))


if __name__ == "__main__":
    main()
