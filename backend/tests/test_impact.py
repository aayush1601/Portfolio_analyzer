from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest

from app.analytics.exposure import effective_exposure
from app.analytics.impact import portfolio_news
from tests.test_exposure import SECTORS, H

NOW = datetime(2026, 10, 4, 12, tzinfo=UTC)
CFG = {"lookback_hours": 72, "sector_discount": 0.5, "alert_threshold": 0.02}
# Worked-example exposure: TCS 23.2% effective (20% direct + 3.2% via funds), INFY 2.8%, IT sector 26%
EXP = effective_exposure("p", date(2026, 10, 4), {"TCS": 0.2}, {"A": 0.3, "B": 0.2}, H, SECTORS)


def article(news_id, hours_ago, symbols, sectors, score, importance=1.0, reliability=1.0):
    return dict(
        news_id=news_id,
        headline=news_id,
        source="s",
        url="u",
        published_at=NOW - timedelta(hours=hours_ago),
        symbols=symbols,
        sectors=sectors,
        label="x",
        score=score,
        confidence=1.0,
        importance=importance,
        reliability=reliability,
    )


def test_impact_formula_and_routing():
    news = pd.DataFrame(
        [
            article("tcs", 0, ["TCS"], ["Information Technology"], -0.5, importance=0.8, reliability=0.5),
            article("peer", 24, ["HCLTECH"], ["Information Technology"], 0.4),  # not held: sector spillover
            article("other", 0, ["SBIN"], ["Financial Services"], -1.0),  # no exposure at all: dropped
            article("old", 100, ["TCS"], ["Information Technology"], -1.0),  # outside 72 h
        ]
    )
    r = portfolio_news(news, EXP, NOW, CFG, half_life_hours=24)
    items = {i.news_id: i for i in r.items}
    assert set(items) == {"tcs", "peer"}
    # tcs: −0.5 · 0.8 · 1 (fresh) · 0.5 · 0.232 = −0.0464
    assert items["tcs"].impact == pytest.approx(-0.0464)
    assert items["tcs"].matched_via == "company"
    # peer: 0.4 · 1 · 0.5 (one half-life) · 1 · (0.5 · 0.26) = 0.026
    assert items["peer"].impact == pytest.approx(0.026)
    assert items["peer"].matched_via == "sector" and items["peer"].effective_exposure == pytest.approx(0.13)
    assert r.portfolio_news_impact == pytest.approx(-0.0204)
    assert r.alert  # −0.0204 ≤ −0.02
    assert [i.news_id for i in r.items] == ["tcs", "peer"]  # by |impact|


def test_empty_window_has_note():
    r = portfolio_news(pd.DataFrame(columns=["published_at"]), EXP, NOW, CFG, 24)
    assert r.items == [] and not r.alert and "collector" in r.notes[0]
