from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.analytics.sentiment import daily_ticker_sentiment, evaluate, ticker_sentiment, to_scores

NOW = datetime(2026, 10, 4, 12, tzinfo=UTC)


def test_to_scores_uses_model_label_order():
    # ProsusAI/finbert's id2label order is positive, negative, neutral
    s = to_scores(np.array([[0.7, 0.1, 0.2], [0.1, 0.6, 0.3]]), ["positive", "negative", "neutral"])
    assert s["score"].round(6).tolist() == [0.6, -0.5]
    assert s["label"].tolist() == ["positive", "negative"]
    assert s["confidence"].tolist() == [0.7, 0.6]


def news(rows):
    return pd.DataFrame(rows, columns=["published_at", "symbols", "score", "confidence", "label", "date"])


def test_ticker_sentiment_decays_and_is_point_in_time():
    n = news(
        [
            (NOW - timedelta(hours=24), ["TCS"], 1.0, 1.0, "positive", None),  # one half-life old: w = 0.5
            (NOW, ["TCS", "INFY"], -0.5, 1.0, "negative", None),  # fresh: w = 1
            (NOW + timedelta(hours=1), ["TCS"], -1.0, 1.0, "negative", None),  # future: ignored
        ]
    )
    s = ticker_sentiment(n, NOW, half_life_hours=24).set_index("symbol")
    # TCS: (0.5·1 + 1·−0.5) / (0.5 + 1) = 0
    assert s.loc["TCS", "decayed_score"] == pytest.approx(0.0)
    assert s.loc["TCS", "articles"] == 2 and s.loc["TCS", "weight"] == pytest.approx(1.5)
    assert s.loc["INFY", "decayed_score"] == pytest.approx(-0.5)
    assert ticker_sentiment(n, NOW - timedelta(days=9), 24).empty


def test_daily_ticker_sentiment():
    d = pd.Timestamp("2026-10-04")
    n = news(
        [
            (NOW, ["TCS"], 0.4, 1, "positive", d),
            (NOW, ["TCS"], -0.8, 1, "negative", d),
            (NOW, [], 0.9, 1, "positive", d),
        ]
    )
    row = daily_ticker_sentiment(n).iloc[0]
    assert (row["symbol"], row["articles"], row["mean_score"], row["neg_share"]) == (
        "TCS",
        2,
        pytest.approx(-0.2),
        0.5,
    )


def test_evaluate():
    gold = pd.Series(["positive", "negative", "neutral", "neutral"])
    pred = pd.Series(["positive", "neutral", "neutral", "neutral"])
    r = evaluate(gold, pred)
    assert r["accuracy"] == 0.75
    # F1: positive 1, negative 0, neutral 2·(2/3·1)/(2/3+1) = 0.8 → mean 0.6
    assert r["macro_f1"] == pytest.approx(0.6)
    assert r["confusion"]["negative"]["neutral"] == 1
