from datetime import UTC

import numpy as np
import pandas as pd
import pytest

from app.analytics.evaluation import demean_by_date, rank_ic, summarise, walk_forward_splits
from app.analytics.features import build_dataset, news_features

DATES = pd.bdate_range("2025-01-01", periods=300)


def prices(n_stocks=6):
    rng = np.random.default_rng(0)
    rows = []
    for s in [f"S{i}" for i in range(n_stocks)] + ["^NSEI", "^INDIAVIX"]:
        px = 100 * np.cumprod(1 + rng.normal(0, 0.01, len(DATES)))
        rows.append(
            pd.DataFrame(
                {"date": DATES, "symbol": s, "adj_close": px, "volume": rng.integers(1e5, 1e6, len(DATES))}
            )
        )
    return pd.concat(rows, ignore_index=True)


def test_features_use_only_the_past_and_targets_only_the_future():
    p = prices()
    d = build_dataset(p, pd.DataFrame()).set_index(["date", "symbol"])
    px = p[p.symbol == "S0"].set_index("date")["adj_close"]
    t = DATES[100]
    assert d.loc[(t, "S0"), "ret_5d"] == pytest.approx(px[t] / px[DATES[95]] - 1)
    assert d.loc[(t, "S0"), "fwd_5d"] == pytest.approx(px[DATES[105]] / px[t] - 1)
    assert np.isnan(d.loc[(DATES[-1], "S0"), "fwd_5d"])  # not knowable yet
    assert "^NSEI" not in d.index.get_level_values("symbol")


def test_news_after_the_close_counts_for_the_next_trading_day():
    ist = lambda s: pd.Timestamp(s, tz="Asia/Kolkata").tz_convert(UTC)  # noqa: E731
    news = pd.DataFrame(
        [
            {
                "published_at": ist("2025-01-06 10:00"),
                "symbols": ["A", "C"],  # one article, two companies
                "score": 0.8,
                "label": "positive",
            },  # Mon, pre-close
            {
                "published_at": ist("2025-01-06 16:00"),
                "symbols": ["A"],
                "score": -0.6,
                "label": "negative",
            },  # Mon, after close
            {
                "published_at": ist("2025-01-11 09:00"),
                "symbols": ["B"],
                "score": 0.5,
                "label": "positive",
            },  # Saturday
        ]
    )
    f = news_features(news, pd.bdate_range("2025-01-06", periods=6)).set_index(["date", "symbol"])
    mon, tue, next_mon = pd.Timestamp("2025-01-06"), pd.Timestamp("2025-01-07"), pd.Timestamp("2025-01-13")
    assert f.loc[(mon, "A"), "news_count_7d"] == 1 and f.loc[(mon, "A"), "news_score_3d"] == pytest.approx(
        0.8
    )
    assert f.loc[(tue, "A"), "news_count_7d"] == 2 and f.loc[(tue, "A"), "news_score_3d"] == pytest.approx(
        0.1
    )
    assert f.loc[(tue, "A"), "news_neg_share_7d"] == 0.5
    assert f.loc[(next_mon, "B"), "news_count_7d"] == 1  # weekend news lands on Monday
    assert f.loc[(mon, "B"), "news_count_7d"] == 0
    assert f.loc[(mon, "C"), "news_score_3d"] == pytest.approx(0.8)


def test_walk_forward_purges_the_horizon_before_each_test_year():
    dates = pd.bdate_range("2023-01-02", "2025-12-31")
    folds = list(walk_forward_splits(pd.DatetimeIndex(dates), [2024, 2025], horizon=20))
    train, test = folds[0]
    assert test[0].year == 2024 and train[-1] < test[0]
    assert dates.get_loc(test[0]) - dates.get_loc(train[-1]) == 21  # 20 dates purged between
    assert len(folds[1][0]) > len(train)  # expanding


def test_rank_ic_and_summary():
    d = pd.DataFrame(
        {
            "date": np.repeat(pd.bdate_range("2025-01-01", periods=4), 5),
            "pred": np.tile([1, 2, 3, 4, 5], 4),
            "y": np.tile([0.1, 0.2, 0.3, 0.4, 0.5], 4) - 0.25,
        }
    )
    assert rank_ic(d, "pred", "y").tolist() == pytest.approx([1, 1, 1, 1])
    d["y_dm"] = demean_by_date(d, "y")
    s = summarise(d, "pred", "y", horizon=1)
    assert s["rank_ic"] == pytest.approx(1) and s["dates"] == 4
    assert s["hit_rate"] == pytest.approx(0.6)  # pred always > 0; y > 0 for 3 of 5
