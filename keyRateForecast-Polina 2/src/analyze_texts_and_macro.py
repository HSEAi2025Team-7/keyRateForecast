

import os
import re
from collections import Counter

import matplotlib.pyplot as plt
import pandas as pd
from pandas.tseries.offsets import MonthEnd

# Пути к данным
DATASET_TIMELINE = "data/processed/dataset_timeline.csv"
KEYRATE_CSV = "data/labels/key_rate_history.csv"
INFL_CSV = "data/macro/inflation_keyrate.csv"
USDRUB_CSV = "data/macro/usd_rub_daily.csv"
REPORTS_DIR = "reports"

# Очень грубый набор русских стоп-слов + слова про Банк России
RUS_STOPWORDS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
    "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
    "бы", "по", "ее", "мне", "есть", "если", "или", "ни", "они", "такой",
    "этот", "тот", "для", "чтобы", "это", "при", "мы", "от", "о", "из",
    "что", "который", "также", "таких", "такие", "их", "же", "года", "году",
    "банка", "россии", "банк", "россия",
}


def ensure_reports_dir():
    os.makedirs(REPORTS_DIR, exist_ok=True)


def tokenize(text: str):
    text = text.lower()
    tokens = re.findall(r"[а-яёa-z]+", text)
    tokens = [t for t in tokens if t not in RUS_STOPWORDS and len(t) > 2]
    return tokens


# ---------- TOP WORDS ----------

def top_words_overall():
    """Топ слов по всем пресс-релизам."""
    print("[EDA] считаю ОБЩИЙ топ слов в пресс-релизах...")
    df = pd.read_csv(DATASET_TIMELINE)
    texts = df["text_clean"].fillna("").tolist()

    cnt = Counter()
    for t in texts:
        cnt.update(tokenize(t))

    top100 = cnt.most_common(100)
    out_path = os.path.join(REPORTS_DIR, "top_words_overall.csv")
    pd.DataFrame(top100, columns=["word", "count"]).to_csv(out_path, index=False)
    print(f"[EDA] общий top_words -> {out_path}")


def _top_words_for_subset(df_subset: pd.DataFrame):
    cnt = Counter()
    for t in df_subset["text_clean"].fillna(""):
        cnt.update(tokenize(t))
    return cnt.most_common(100)


def top_words_by_decision():
    """
    Топ слов отдельно:
      - перед повышением ставки (decision == 1)
      - перед понижением ставки (decision == -1)
      - перед сохранением ставки (decision == 0)

    Берём только релизы с is_between == True,
    то есть находящиеся МЕЖДУ двумя решениями.
    """
    print("[EDA] считаю топ слов по типу будущего решения (decision)...")
    df = pd.read_csv(DATASET_TIMELINE)

    # оставляем только строки, где известен decision
    df = df.dropna(subset=["decision"]).copy()

    # decision может быть float -> приводим к int
    df["decision"] = df["decision"].astype(int)

    # если колонки is_between нет (на всякий случай) — считаем, что все релизы учитываем
    if "is_between" in df.columns:
        base = df[df["is_between"] == True].copy()
    else:
        base = df.copy()

    # Подмножества
    hikes = base[base["decision"] == 1]    # перед повышением
    cuts = base[base["decision"] == -1]    # перед понижением
    holds = base[base["decision"] == 0]    # перед сохранением

    print(f"[EDA] релизов перед повышением: {len(hikes)}")
    print(f"[EDA] релизов перед понижением: {len(cuts)}")
    print(f"[EDA] релизов перед сохранением: {len(holds)}")

    # считаем топы
    hikes_top = _top_words_for_subset(hikes)
    cuts_top = _top_words_for_subset(cuts)
    holds_top = _top_words_for_subset(holds)

    pd.DataFrame(hikes_top, columns=["word", "count"]).to_csv(
        os.path.join(REPORTS_DIR, "top_words_before_hike.csv"), index=False
    )
    pd.DataFrame(cuts_top, columns=["word", "count"]).to_csv(
        os.path.join(REPORTS_DIR, "top_words_before_cut.csv"), index=False
    )
    pd.DataFrame(holds_top, columns=["word", "count"]).to_csv(
        os.path.join(REPORTS_DIR, "top_words_before_hold.csv"), index=False
    )

    print("[EDA] топы слов по decision сохранены в:")
    print("  - reports/top_words_before_hike.csv")
    print("  - reports/top_words_before_cut.csv")
    print("  - reports/top_words_before_hold.csv")


# макра

def build_macro():
    """
    Собираем единый датафрейм macro с колонками: дата инфляция ставка обменный курс
    """

    # 1) История ставки
    keyrate = pd.read_csv(KEYRATE_CSV, parse_dates=["date"])
    keyrate = keyrate.sort_values("date").reset_index(drop=True)

    # 2) Курс USD/RUB (дневной)
    usdrub = pd.read_csv(USDRUB_CSV, parse_dates=["date"])
    usdrub = usdrub.sort_values("date").reset_index(drop=True)

    # 3) Инфляция + ставка помесячно
    infl = pd.read_csv(INFL_CSV)
    infl_dates_parsed = pd.to_datetime(infl["date"], errors="coerce")
    min_year = infl_dates_parsed.dt.year.min()

    # если инфляция с кривыми датами (1970 и т.п.) — подставляем последние N месяцев
    if pd.isna(min_year) or min_year < 1990:
        n = len(infl)
        last_calendar_date = keyrate["date"].max()
        last_month_end = (last_calendar_date + MonthEnd(0)).normalize()
        months = [last_month_end - MonthEnd(n - 1 - i) for i in range(n)]
        infl["date"] = pd.to_datetime(months)
        print(
            f"[EDA] инфляция: некорректные даты в CSV, "
            f"подставляю {n} последних месяцев до {last_month_end.date()}"
        )
    else:
        infl["date"] = infl_dates_parsed

    if "inflation_yoy" not in infl.columns:
        raise RuntimeError(
            f"[EDA] В {INFL_CSV} нет колонки 'inflation_yoy' — посмотри структуру файла"
        )

    # --- ресемплинг по месяцам ---

    # ключевая ставка: последнее значение в каждом месяце
    keyrate_m = (
        keyrate.set_index("date")["rate"]
        .resample("M")
        .last()
        .reset_index()
        .rename(columns={"rate": "key_rate_m"})
    )
    keyrate_m["month"] = keyrate_m["date"].dt.to_period("M")

    # курс usd/rub: средний за месяц
    usdrub_m = (
        usdrub.set_index("date")["usd_rub"]
        .resample("M")
        .mean()
        .reset_index()
        .rename(columns={"usd_rub": "usd_rub_m"})
    )
    usdrub_m["month"] = usdrub_m["date"].dt.to_period("M")

    # инфляция: месяцы → период
    infl["month"] = pd.to_datetime(infl["date"]).dt.to_period("M")

    macro = (
        infl.merge(keyrate_m[["month", "key_rate_m"]], on="month", how="left")
        .merge(usdrub_m[["month", "usd_rub_m"]], on="month", how="left")
    )

    macro["date"] = macro["month"].dt.to_timestamp("M")
    macro = macro.dropna(subset=["inflation_yoy", "key_rate_m", "usd_rub_m"])

    print("[EDA] macro preview:")
    print(macro[["date", "inflation_yoy", "key_rate_m", "usd_rub_m"]])

    return macro


def plot_macro(macro: pd.DataFrame):
    print("[EDA] строю макро-графики...")

    # Тайм-серия: ключевая ставка и инфляция
    plt.figure(figsize=(10, 5))
    plt.plot(macro["date"], macro["key_rate_m"], label="Key rate, %")
    plt.plot(macro["date"], macro["inflation_yoy"], label="Inflation, % YoY")
    plt.legend()
    plt.title("Ключевая ставка и инфляция (помесячно)")
    plt.grid(True)
    out_ts1 = os.path.join(REPORTS_DIR, "keyrate_vs_inflation_timeseries.png")
    plt.savefig(out_ts1, bbox_inches="tight")
    plt.close()
    print(f"[EDA] сохранён график {out_ts1}")

    # Тайм-серия: USD/RUB
    plt.figure(figsize=(10, 5))
    plt.plot(macro["date"], macro["usd_rub_m"])
    plt.title("USD/RUB (средний курс за месяц)")
    plt.grid(True)
    out_ts2 = os.path.join(REPORTS_DIR, "usd_rub_timeseries.png")
    plt.savefig(out_ts2, bbox_inches="tight")
    plt.close()
    print(f"[EDA] сохранён график {out_ts2}")

    # Scatter: key rate vs inflation
    plt.figure(figsize=(6, 6))
    plt.scatter(macro["key_rate_m"], macro["inflation_yoy"])
    plt.xlabel("Key rate, %")
    plt.ylabel("Inflation, % YoY")
    plt.title("Ключевая ставка vs инфляция")
    plt.grid(True)
    out_sc1 = os.path.join(REPORTS_DIR, "scatter_keyrate_inflation.png")
    plt.savefig(out_sc1, bbox_inches="tight")
    plt.close()
    print(f"[EDA] сохранён график {out_sc1}")

    # Scatter: key rate vs USD/RUB
    plt.figure(figsize=(6, 6))
    plt.scatter(macro["key_rate_m"], macro["usd_rub_m"])
    plt.xlabel("Key rate, %")
    plt.ylabel("USD/RUB")
    plt.title("Ключевая ставка vs курс USD/RUB")
    plt.grid(True)
    out_sc2 = os.path.join(REPORTS_DIR, "scatter_keyrate_usdrub.png")
    plt.savefig(out_sc2, bbox_inches="tight")
    plt.close()
    print(f"[EDA] сохранён график {out_sc2}")

    # Корреляции
    corr = macro[["key_rate_m", "inflation_yoy", "usd_rub_m"]].corr()
    out_corr = os.path.join(REPORTS_DIR, "macro_correlations.csv")
    corr.to_csv(out_corr)
    print(f"[EDA] корреляции сохранены в {out_corr}")
    print(corr)


def main():
    ensure_reports_dir()
    # 1. Общий топ слов
    top_words_overall()
    # 2. Топ слов по типу решения (перед повышением / понижением / сохранением)
    top_words_by_decision()
    # 3. Макро-графики
    macro = build_macro()
    if macro.empty:
        print("[EDA] ВНИМАНИЕ: macro пустой — проверь файлы макро-данных.")
    else:
        plot_macro(macro)
    plot_word_hist_hike_vs_cut(top_n=25)

import networkx as nx

def plot_word_hist_hike_vs_cut(top_n: int = 25):
    """
    Строит зеркальную гистограмму для слов перед повышением и понижением ставки.

    Берём топ-N слов по максимальной частоте среди двух классов:
        - top_words_before_hike.csv
        - top_words_before_cut.csv
    """
    print("[EDA] строю зеркальную гистограмму слов для hike vs cut...")

    hike_path = os.path.join(REPORTS_DIR, "top_words_before_hike.csv")
    cut_path = os.path.join(REPORTS_DIR, "top_words_before_cut.csv")

    if not (os.path.exists(hike_path) and os.path.exists(cut_path)):
        print("[EDA] Нет файлов top_words_before_hike/cut — сначала запусти top_words_by_decision().")
        return

    hike = pd.read_csv(hike_path)
    cut = pd.read_csv(cut_path)

    # Приводим к словарь: слово -> count
    hike_dict = dict(zip(hike["word"], hike["count"]))
    cut_dict = dict(zip(cut["word"], cut["count"]))

    # Общее множество слов
    all_words = set(hike_dict.keys()) | set(cut_dict.keys())

    # Для каждого слова берём максимум частоты между двумя классами
    rows = []
    for w in all_words:
        c_h = hike_dict.get(w, 0)
        c_c = cut_dict.get(w, 0)
        max_c = max(c_h, c_c)
        rows.append((w, c_h, c_c, max_c))

    df = pd.DataFrame(rows, columns=["word", "count_hike", "count_cut", "max_count"])
    # Берём топ-N слов по max_count
    df = df.sort_values("max_count", ascending=False).head(top_n)

    # Индекс по x
    x = range(len(df))
    hike_vals = df["count_hike"].tolist()
    cut_vals = df["count_cut"].tolist()

    # Рисуем зеркальную гистограмму
    plt.figure(figsize=(12, 6))

    # Верхняя гистограмма (повышение)
    plt.bar(x, hike_vals, width=0.8, label="Перед повышением (decision=1)")

    # Нижняя гистограмма (понижение) — просто отрицательные значения
    plt.bar(x, [-v for v in cut_vals], width=0.8, label="Перед понижением (decision=-1)")

    # Линия нуля
    plt.axhline(0, color="black", linewidth=1)

    # Подписи по оси X — слова
    plt.xticks(x, df["word"].tolist(), rotation=45, ha="right")

    plt.ylabel("Частота слова")
    plt.title(f"Частотность слов перед повышением и понижением ставки (топ-{top_n})")
    plt.legend()
    plt.tight_layout()

    out_path = os.path.join(REPORTS_DIR, "word_hist_hike_vs_cut.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"[EDA] зеркальная гистограмма сохранена -> {out_path}")




if __name__ == "__main__":
    main()
