
import os
import re
from collections import Counter

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import LatentDirichletAllocation

# Пути
DATASET_TIMELINE = "data/processed/dataset_timeline.csv"
REPORTS_DIR = "reports"

# Стоп-слова (можешь расширять)
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
    text = str(text).lower()
    tokens = re.findall(r"[а-яёa-z]+", text)
    tokens = [t for t in tokens if t not in RUS_STOPWORDS and len(t) > 2]
    return tokens


def load_base_dataframe():
    """
    Загружаем датасет и оставляем релизы:
      - с известным decision
      - лежащие между заседаниями (is_between == True)
    """
    df = pd.read_csv(DATASET_TIMELINE)
    df = df.dropna(subset=["decision"]).copy()
    df["decision"] = df["decision"].astype(int)

    if "is_between" in df.columns:
        df = df[df["is_between"] == True].copy()

    df["text_clean"] = df["text_clean"].fillna("")
    print(f"[NLP] загружено {len(df)} релизов с decision и is_between=True")
    return df


# ---------------------------------------------------------------------
# 1) Лог-odds слова для hike vs cut + визуализация
# ---------------------------------------------------------------------

def compute_log_odds_hike_vs_cut(df, alpha: float = 0.01, top_n: int = 50):
    """
    Считаем log-odds для слов перед повышением и понижением ставки.

    decision == 1 -> hike
    decision == -1 -> cut

    Возвращаем два датафрейма:
      top_hike, top_cut (по log-odds)
    и сохраняем CSV.
    """
    hikes = df[df["decision"] == 1]
    cuts = df[df["decision"] == -1]

    print(f"[NLP] лог-odds: релизов hike={len(hikes)}, cut={len(cuts)}")

    cnt_h = Counter()
    cnt_c = Counter()

    for t in hikes["text_clean"]:
        cnt_h.update(tokenize(t))
    for t in cuts["text_clean"]:
        cnt_c.update(tokenize(t))

    all_words = set(cnt_h.keys()) | set(cnt_c.keys())
    V = len(all_words)
    N_h = sum(cnt_h.values())
    N_c = sum(cnt_c.values())

    rows = []
    for w in all_words:
        fh = cnt_h.get(w, 0)
        fc = cnt_c.get(w, 0)
        p_h = (fh + alpha) / (N_h + alpha * V)
        p_c = (fc + alpha) / (N_c + alpha * V)
        log_odds = np.log(p_h) - np.log(p_c)
        rows.append((w, fh, fc, p_h, p_c, log_odds))

    out = pd.DataFrame(
        rows,
        columns=["word", "freq_hike", "freq_cut", "p_hike", "p_cut", "log_odds"],
    )

    out = out.sort_values("log_odds", ascending=False)

    out_path_all = os.path.join(REPORTS_DIR, "logodds_hike_vs_cut.csv")
    out.to_csv(out_path_all, index=False)

    top_hike = out.head(top_n)
    top_cut = out.tail(top_n).iloc[::-1]

    top_hike.to_csv(
        os.path.join(REPORTS_DIR, "logodds_top_hike.csv"), index=False
    )
    top_cut.to_csv(
        os.path.join(REPORTS_DIR, "logodds_top_cut.csv"), index=False
    )

    print(f"[NLP] log-odds сохранён -> {out_path_all}")
    print("[NLP] top_hike пример:")
    print(top_hike.head(10))
    print("[NLP] top_cut пример:")
    print(top_cut.head(10))

    return top_hike, top_cut


def plot_log_odds(top_hike: pd.DataFrame, top_cut: pd.DataFrame, k: int = 20):
    """
    Визуализация log-odds:
      - отдельный график для top-k hike слов
      - отдельный график для top-k cut слов
    """

    # --- top hike ---
    th = top_hike.head(k)
    y_pos = range(len(th))
    plt.figure(figsize=(10, 6))
    plt.barh(y_pos, th["log_odds"].values)
    plt.yticks(y_pos, th["word"].tolist())
    plt.gca().invert_yaxis()
    plt.xlabel("log-odds (hike vs cut)")
    plt.title(f"Слова, ассоциированные с ПОВЫШЕНИЕМ ставки (top-{k})")
    plt.tight_layout()
    out_path_h = os.path.join(REPORTS_DIR, "logodds_top_hike.png")
    plt.savefig(out_path_h, dpi=300)
    plt.close()
    print(f"[NLP] график log-odds hike -> {out_path_h}")

    # --- top cut ---
    tc = top_cut.head(k)
    y_pos = range(len(tc))
    plt.figure(figsize=(10, 6))
    # лог-odds тут отрицательные, для читабельности берём модуль
    plt.barh(y_pos, (-tc["log_odds"]).values)
    plt.yticks(y_pos, tc["word"].tolist())
    plt.gca().invert_yaxis()
    plt.xlabel("|log-odds| (cut vs hike)")
    plt.title(f"Слова, ассоциированные с ПОНИЖЕНИЕМ ставки (top-{k})")
    plt.tight_layout()
    out_path_c = os.path.join(REPORTS_DIR, "logodds_top_cut.png")
    plt.savefig(out_path_c, dpi=300)
    plt.close()
    print(f"[NLP] график log-odds cut -> {out_path_c}")


# ---------------------------------------------------------------------
# 2) Кластеризация релизов + визуализация распределения решений
# ---------------------------------------------------------------------

def cluster_releases(df, n_clusters: int = 8, max_features: int = 5000):
    """
    Кластеризация текстов по TF-IDF + KMeans.
    Анализируем, какие решения (decision) доминируют в кластерах.
    Возвращаем df_clusters и crosstab.
    """

    print("[NLP] кластеризация релизов по TF-IDF + KMeans...")

    texts = df["text_clean"].tolist()

    vectorizer = TfidfVectorizer(
        tokenizer=tokenize,
        max_features=max_features,
        min_df=3,
        max_df=0.7,
    )
    X = vectorizer.fit_transform(texts)

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
    labels = km.fit_predict(X)

    df_clusters = df.copy()
    df_clusters["cluster"] = labels

    crosstab = pd.crosstab(df_clusters["cluster"], df_clusters["decision"])
    crosstab_path = os.path.join(REPORTS_DIR, "clusters_decision_crosstab.csv")
    crosstab.to_csv(crosstab_path)
    print(f"[NLP] распределение decision по кластерам -> {crosstab_path}")
    print(crosstab)

    # overview по кластерам (топ-слова по центроидам)
    terms = np.array(vectorizer.get_feature_names_out())
    cluster_rows = []
    for cl in range(n_clusters):
        center = km.cluster_centers_[cl]
        top_idx = center.argsort()[::-1][:15]
        top_terms = ", ".join(terms[top_idx])
        n_docs = (df_clusters["cluster"] == cl).sum()
        cluster_rows.append(
            {
                "cluster": cl,
                "n_docs": n_docs,
                "top_terms": top_terms,
            }
        )

    clusters_overview = pd.DataFrame(cluster_rows)
    clusters_overview_path = os.path.join(REPORTS_DIR, "clusters_overview.csv")
    clusters_overview.to_csv(clusters_overview_path, index=False)
    print(f"[NLP] overview кластеров -> {clusters_overview_path}")

    return df_clusters, crosstab


def plot_clusters_decision(crosstab: pd.DataFrame):
    """
    Строим stacked bar: по оси X — кластер,
    по оси Y — доли решений (-1, 0, 1) внутри кластера.
    """

    print("[NLP] визуализация распределения решений по кластерам...")

    # нормируем по строкам (получаем доли)
    ctab = crosstab.copy().astype(float)
    ctab = ctab.div(ctab.sum(axis=1), axis=0)

    clusters = ctab.index.tolist()
    decisions = sorted(ctab.columns.tolist())  # [-1,0,1]

    x = np.arange(len(clusters))
    bottoms = np.zeros(len(clusters))

    plt.figure(figsize=(10, 6))

    for d in decisions:
        vals = ctab[d].values
        plt.bar(x, vals, bottom=bottoms, label=f"decision={d}")
        bottoms += vals

    plt.xticks(x, [str(c) for c in clusters])
    plt.ylabel("Доля внутри кластера")
    plt.xlabel("Кластер")
    plt.title("Распределение решений по кластерам (stacked)")
    plt.legend()
    plt.tight_layout()

    out_path = os.path.join(REPORTS_DIR, "clusters_decision_stacked.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"[NLP] график кластеров -> {out_path}")


# ---------------------------------------------------------------------
# 3) Тематическое моделирование (LDA)
# ---------------------------------------------------------------------

def build_topics_lda(df, n_topics: int = 10, max_features: int = 5000):
    """
    Строим LDA-темы по корпусу текстов.
    """

    print("[NLP] тематическое моделирование LDA...")

    texts = df["text_clean"].tolist()

    vectorizer = CountVectorizer(
        tokenizer=tokenize,
        max_features=max_features,
        min_df=5,
        max_df=0.8,
    )
    X = vectorizer.fit_transform(texts)

    lda = LatentDirichletAllocation(
        n_components=n_topics,
        learning_method="batch",
        random_state=42,
    )
    lda.fit(X)

    terms = np.array(vectorizer.get_feature_names_out())
    topic_rows = []

    for topic_idx, topic in enumerate(lda.components_):
        top_idx = topic.argsort()[::-1][:20]
        top_terms = ", ".join(terms[top_idx])
        topic_rows.append(
            {
                "topic_id": topic_idx,
                "top_terms": top_terms,
            }
        )

    topics_df = pd.DataFrame(topic_rows)
    topics_path = os.path.join(REPORTS_DIR, "topics_lda.csv")
    topics_df.to_csv(topics_path, index=False)
    print(f"[NLP] темы LDA -> {topics_path}")
    print(topics_df.head())


# ---------------------------------------------------------------------
# 4) PMI bigrams + визуализация
# ---------------------------------------------------------------------

def compute_pmi_bigrams(df, min_count: int = 5, top_n: int = 200):
    """
    Считаем PMI для биграмм во всём корпусе.

    Возвращаем top_n биграмм по PMI.
    """

    print("[NLP] считаю PMI bigrams...")

    tokenized_docs = [tokenize(t) for t in df["text_clean"]]
    word_counts = Counter()
    bigram_counts = Counter()

    total_tokens = 0
    for toks in tokenized_docs:
        word_counts.update(toks)
        total_tokens += len(toks)
        for i in range(len(toks) - 1):
            bigram = (toks[i], toks[i + 1])
            bigram_counts[bigram] += 1

    rows = []
    for (w1, w2), f_xy in bigram_counts.items():
        if f_xy < min_count:
            continue
        f_x = word_counts[w1]
        f_y = word_counts[w2]
        p_x = f_x / total_tokens
        p_y = f_y / total_tokens
        p_xy = f_xy / max(1, total_tokens - 1)
        pmi = np.log(p_xy / (p_x * p_y))
        rows.append((w1, w2, f_xy, f_x, f_y, pmi))

    if not rows:
        print("[NLP] мало биграмм для PMI (rows=0) — проверь корпус.")
        return pd.DataFrame()

    out = pd.DataFrame(
        rows,
        columns=["w1", "w2", "freq_bigram", "freq_w1", "freq_w2", "pmi"],
    )
    out = out.sort_values("pmi", ascending=False).head(top_n)

    out_path = os.path.join(REPORTS_DIR, "bigrams_pmi.csv")
    out.to_csv(out_path, index=False)
    print(f"[NLP] PMI bigrams -> {out_path}")
    print(out.head(20))

    return out


def plot_pmi_bigrams(bi_df: pd.DataFrame, k: int = 20):
    """
    Визуализация top-k биграмм по PMI (горизонтальный барчарт).
    """
    if bi_df.empty:
        print("[NLP] нет биграмм для визуализации.")
        return

    b = bi_df.head(k).copy()
    labels = [f"{w1} {w2}" for w1, w2 in zip(b["w1"], b["w2"])]
    y_pos = range(len(b))

    plt.figure(figsize=(10, 6))
    plt.barh(y_pos, b["pmi"].values)
    plt.yticks(y_pos, labels)
    plt.gca().invert_yaxis()
    plt.xlabel("PMI")
    plt.title(f"Top-{k} биграмм по PMI")
    plt.tight_layout()

    out_path = os.path.join(REPORTS_DIR, "bigrams_pmi_top.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"[NLP] график биграмм PMI -> {out_path}")


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    ensure_reports_dir()
    df = load_base_dataframe()

    # 1) Лог-odds слова: какие слова ассоциированы с hike vs cut + графики
    top_hike, top_cut = compute_log_odds_hike_vs_cut(df, alpha=0.01, top_n=50)
    plot_log_odds(top_hike, top_cut, k=20)

    # 2) Кластеризация релизов и анализ decision по кластерам + график
    df_clusters, crosstab = cluster_releases(df, n_clusters=8, max_features=5000)
    plot_clusters_decision(crosstab)

    # 3) Тематическое моделирование LDA (пока только CSV)
    build_topics_lda(df, n_topics=10, max_features=5000)

    # 4) PMI биграммы + график
    bi_df = compute_pmi_bigrams(df, min_count=5, top_n=200)
    plot_pmi_bigrams(bi_df, k=20)


if __name__ == "__main__":
    main()
