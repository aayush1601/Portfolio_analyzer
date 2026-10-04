"""Sentiment maths (Phase 7). No model dependency, so the API and later phases can import it without torch.

Per article: score = P(pos) − P(neg) ∈ [−1, 1]; confidence = max(P). Aggregates are point-in-time: only news
published at or before `as_of` counts.
"""

from datetime import datetime

import numpy as np
import pandas as pd

LABELS = ["positive", "neutral", "negative"]


def to_scores(probs: np.ndarray, labels: list[str]) -> pd.DataFrame:
    """Model softmax rows (in the model's label order) → p_pos, p_neu, p_neg, score, label, confidence."""
    p = pd.DataFrame(probs, columns=[f"p_{lab[:3]}" for lab in labels])[["p_pos", "p_neu", "p_neg"]]
    p["score"] = p["p_pos"] - p["p_neg"]
    p["label"] = p[["p_pos", "p_neu", "p_neg"]].to_numpy().argmax(axis=1)
    p["label"] = p["label"].map(dict(enumerate(LABELS)))
    p["confidence"] = p[["p_pos", "p_neu", "p_neg"]].max(axis=1)
    return p


def ticker_sentiment(news: pd.DataFrame, as_of: datetime, half_life_hours: float) -> pd.DataFrame:
    """Time-decayed sentiment per symbol at as_of.

    news: one row per article with published_at, symbols (list), score, confidence.
    decayed_score = Σ wᵢ·scoreᵢ / Σ wᵢ, with wᵢ = 0.5^(ageᵢ / half_life) · confidenceᵢ, so a fresh confident
    article dominates and a week-old one barely counts. `weight` (Σ wᵢ) says how much evidence there is.
    """
    n = news[news["published_at"] <= pd.Timestamp(as_of)].explode("symbols").dropna(subset=["symbols"])
    if n.empty:
        return pd.DataFrame(columns=["symbol", "articles", "weight", "decayed_score"])
    age_h = (pd.Timestamp(as_of) - n["published_at"]).dt.total_seconds() / 3600
    n = n.assign(w=0.5 ** (age_h / half_life_hours) * n["confidence"])
    n = n.assign(ws=n["w"] * n["score"])
    g = n.groupby("symbols").agg(articles=("score", "size"), weight=("w", "sum"), ws=("ws", "sum"))
    g["decayed_score"] = g["ws"] / g["weight"]
    return g.drop(columns="ws").rename_axis("symbol").reset_index().sort_values("symbol", ignore_index=True)


def daily_ticker_sentiment(news: pd.DataFrame) -> pd.DataFrame:
    """Per symbol and IST day: article count, mean score, share of negative articles (Phase 9 features)."""
    n = news.explode("symbols").dropna(subset=["symbols"])
    return (
        n.assign(neg=n["label"].eq("negative"))
        .groupby(["symbols", "date"])
        .agg(articles=("score", "size"), mean_score=("score", "mean"), neg_share=("neg", "mean"))
        .rename_axis(["symbol", "date"])
        .reset_index()
    )


def evaluate(gold: pd.Series, pred: pd.Series) -> dict:
    """Accuracy, macro-F1 and confusion matrix (rows = gold, columns = predicted) over the three labels."""
    cm = pd.crosstab(gold, pred).reindex(index=LABELS, columns=LABELS, fill_value=0)
    f1 = []
    for lab in LABELS:
        tp = cm.loc[lab, lab]
        prec = tp / cm[lab].sum() if cm[lab].sum() else 0.0
        rec = tp / cm.loc[lab].sum() if cm.loc[lab].sum() else 0.0
        f1.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return {
        "n": int(len(gold)),
        "accuracy": float((gold == pred).mean()),
        "macro_f1": float(np.mean(f1)),
        "confusion": cm.to_dict(orient="index"),
    }
