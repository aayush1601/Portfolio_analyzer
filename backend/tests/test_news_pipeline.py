from datetime import UTC, datetime

import pandas as pd
import pytest

from app.config import REPO_ROOT
from app.services.news_pipeline import Mapper, process, recency


@pytest.fixture(scope="module")
def m():
    return Mapper.from_config(REPO_ROOT / "config")  # the real alias/stop-list config


@pytest.mark.parametrize(
    "text, expected",
    [
        ("SBI Life Q2 profit rises; SBI shares flat", ["SBILIFE", "SBIN"]),  # longest match first
        ("SBI Card hikes fees", []),  # stop phrase blocks SBI
        ("Tech Mahindra and Mahindra & Mahindra rally", ["M&M", "TECHM"]),
        ("Reliance Power slumps while Reliance gains", ["RELIANCE"]),
        ("BSE Sensex falls 500 points", []),  # the exchange, not BSE Ltd
        ("BSE shares hit record on F&O volumes", ["BSE"]),
        ("An eternal question for the titan of trade", []),  # case-sensitive aliases
        ("L&T bags order; Dr. Reddy's recalls drug", ["DRREDDY", "LT"]),
        ("L&T Finance raises funds", []),
        ("TCStock is not a company", []),
        ("says an analyst at SBI Securities", []),
        ("held at ITC Maratha in Mumbai", []),
        ("Larsen & Toubro Technology Services (LTTS) gains", []),
    ],
)
def test_symbols(m, text, expected):
    assert m.symbols(text) == expected


def test_sectors_from_companies_and_keywords(m):
    assert m.sectors("IT stocks drag Nifty; Infosys down", ["INFY"]) == ["Information Technology"]
    assert m.sectors("Banking stocks and FMCG names rise", []) == [
        "Fast Moving Consumer Goods",
        "Financial Services",
    ]
    assert m.sectors("it stocks", []) == []  # "IT" keyword is case-sensitive


def test_importance(m):
    # base 0.2 + headline subject 0.4 + event 0.2 + focused 0.1 = 0.9
    assert m.score("Infosys Q2 results beat estimates", "")["importance"] == pytest.approx(0.9)
    # market round-up: base only
    assert m.score("Markets end flat ahead of Diwali", "")["importance"] == pytest.approx(0.2)
    # sector keyword only: 0.2 + 0.1
    assert m.score("Banking stocks look stretched", "")["importance"] == pytest.approx(0.3)


def test_tidy_fixes_feed_escaping():
    from app.services.news_pipeline import tidy

    assert tidy("Larsen &amp;amp; Toubro #39;UPI#39;") == "Larsen & Toubro 'UPI'"


def test_recency_halves_every_half_life():
    assert recency(0, 24) == 1
    assert recency(24, 24) == pytest.approx(0.5)
    assert recency(-5, 24) == 1  # clock skew never boosts


def test_process_dedupes_and_fixes_timestamps(m):
    t = lambda h: datetime(2026, 10, 4, h, tzinfo=UTC)  # noqa: E731
    raw = pd.DataFrame(
        [
            dict(
                news_id="a",
                source="economictimes_markets",
                url="u1",
                headline="TCS wins deal",
                summary="",
                published_at=t(5),
                ingested_at=t(6),
            ),
            dict(
                news_id="a",
                source="economictimes_markets",
                url="u1",
                headline="TCS wins deal",
                summary="",
                published_at=t(5),
                ingested_at=t(7),
            ),  # same id, later run
            dict(
                news_id="b",
                source="livemint_markets",
                url="u2",
                headline="TCS wins deal!",
                summary="",
                published_at=t(5),
                ingested_at=t(8),
            ),  # same story, other site
            dict(
                news_id="c",
                source="livemint_markets",
                url="u3",
                headline="Future dated",
                summary="",
                published_at=t(23),
                ingested_at=t(9),
            ),
            dict(
                news_id="d",
                source="livemint_markets",
                url="u4",
                headline="No date",
                summary="",
                published_at=pd.NaT,
                ingested_at=t(10),
            ),
        ]
    )
    out = process(raw, m).set_index("news_id")
    assert list(out.index) == ["a", "c", "d"]
    assert out.loc["a", "symbols"] == ["TCS"] and out.loc["a", "reliability"] == 0.85
    assert out.loc["c", "published_at"] == t(9) and out.loc["c", "published_at_estimated"]
    assert out.loc["d", "published_at"] == t(10)
    assert out.loc["a", "date"] == pd.Timestamp("2026-10-04")  # 05:00 UTC = 10:30 IST, same day
