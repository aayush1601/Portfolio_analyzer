from datetime import UTC, datetime

import pandas as pd
import pytest

from app.services.market_data import clean, load_prices, returns, save

TICKERS = {"AAA.NS": "AAA", "BBB.NS": "BBB", "^NSEI": "^NSEI"}
DAYS = pd.to_datetime(["2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01"])


def bars(ticker, closes, days=DAYS):
    return pd.DataFrame(
        {
            "date": days,
            "ticker": ticker,
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "adj_close": closes,
            "volume": [100.0] * len(days),
        }
    )


@pytest.fixture
def raw():
    return pd.concat(
        [
            bars("AAA.NS", [100.0, 110.0, 99.0, 99.0]),
            bars("BBB.NS", [50.0, 50.0, 50.0, 50.0]),
            # index misses 29 Sep; stray holiday bar on 27 Sep (a Sunday) must not become a session
            bars("^NSEI", [1000.0, 1010.0, 1020.0, 1030.0], pd.to_datetime(["2026-09-27", *DAYS[[0, 2, 3]]])),
            bars("XXX.NS", [1.0, 1.0, 1.0, 1.0]),  # not in the universe
        ]
    )


def test_clean_fills_index_gap_on_stock_calendar_and_flags_it(raw):
    p = clean(raw, TICKERS)
    nsei = p[p["symbol"] == "^NSEI"].set_index("date")
    assert list(nsei.index) == list(DAYS)  # 27 Sep dropped, 29 Sep added
    assert nsei.loc["2026-09-29", "close"] == 1010.0  # forward-filled from 28 Sep
    assert nsei.loc["2026-09-29", "volume"] == 0
    assert nsei["filled"].tolist() == [False, True, False, False]
    assert set(p["symbol"]) == {"AAA", "BBB", "^NSEI"}


def test_clean_drops_bad_prices_and_sets_available_at_to_close_ist(raw):
    raw.loc[(raw["ticker"] == "BBB.NS") & (raw["date"] == DAYS[1]), "close"] = 0.0
    p = clean(raw, TICKERS)
    bbb = p[p["symbol"] == "BBB"].set_index("date")
    assert bbb.loc["2026-09-29", "filled"]  # zero close treated as missing, then filled
    # 15:30 IST = 10:00 UTC, same calendar day
    assert bbb.loc["2026-09-28", "available_at"] == datetime(2026, 9, 28, 10, 0, tzinfo=UTC)


def test_history_start_cuts_earlier_rows(raw):
    p = clean(raw, TICKERS, {"AAA.NS": DAYS[2]})
    assert p[p["symbol"] == "AAA"]["date"].tolist() == list(DAYS[2:])


def test_returns_are_simple_daily_from_adj_close(raw):
    r = returns(clean(raw, TICKERS))
    assert r["AAA"].round(4).tolist() == [0.1, -0.1, 0.0]
    assert (r["BBB"] == 0).all()


def test_save_load_roundtrip_and_rerun_does_not_duplicate(raw, tmp_path):
    p = clean(raw, TICKERS)
    out = tmp_path / "processed" / "market" / "prices"
    save(p, out)
    save(p, out)
    back = load_prices(tmp_path)
    assert len(back) == len(p)
    cols = ["symbol", "date", "close"]
    pd.testing.assert_frame_equal(back[cols], p[cols], check_dtype=False)


def test_load_prices_drops_duplicate_days(tmp_path):
    """Two copies of a partition (as happened in S3) must not duplicate rows: pivots downstream would fail."""
    import pandas as pd

    from app.services.market_data import load_prices

    day = pd.Timestamp("2026-10-27")
    row = {"symbol": "TCS", "date": day, "close": 1.0, "adj_close": 1.0, "year": 2026}
    part = tmp_path / "processed" / "market" / "prices" / "year=2026"
    part.mkdir(parents=True)
    for name in ("a.parquet", "b.parquet"):
        pd.DataFrame([row]).drop(columns="year").to_parquet(part / name, index=False)
    assert len(load_prices(tmp_path)) == 1
