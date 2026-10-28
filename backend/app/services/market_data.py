"""Market data (Phase 2): yfinance → clean → Parquet price panel, plus returns.

Run daily after market close:  uv run python -m app.services.market_data   (from backend/)
Output: data/raw/market/YYYY/MM/DD/yfinance.parquet  (untouched download, for reproducibility, NFR5)
        data/processed/market/prices/year=YYYY/…parquet  (cleaned PriceBar rows, see docs/data_model.md)
"""

import logging
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import yaml
import yfinance as yf

from app.config import get_settings

log = logging.getLogger(__name__)
START = date(2015, 1, 1)
CLOSE_IST = pd.Timedelta(hours=15, minutes=30)  # NSE close; a daily bar is knowable from then (NFR7)
MAX_FILL_DAYS = 5  # forward-fill at most a trading week; longer gaps are real suspensions, left missing
JUMP = 0.4  # |daily adj return| above this is more likely a bad tick / unadjusted split than news
PRICE_COLS = ["open", "high", "low", "close", "adj_close"]


def load_tickers(config_dir: Path) -> dict[str, str]:
    """Yahoo ticker → our symbol, for the universe stocks plus benchmark index and VIX."""
    u = yaml.safe_load((config_dir / "universe.yaml").read_text())
    tickers = {s["yahoo"]: s["symbol"] for s in u["stocks"]}
    tickers.update({t: t for t in u["benchmark"].values()})  # ^NSEI, ^INDIAVIX keep their Yahoo names
    return tickers


def history_starts(config_dir: Path) -> dict[str, pd.Timestamp]:
    """Yahoo ticker → first usable date, for stocks whose earlier Yahoo history is a different business."""
    u = yaml.safe_load((config_dir / "universe.yaml").read_text())
    return {s["yahoo"]: pd.Timestamp(s["history_start"]) for s in u["stocks"] if "history_start" in s}


def download(tickers: list[str], start: date = START) -> pd.DataFrame:
    """Raw daily bars in long form: date, ticker, open, high, low, close, adj_close, volume."""
    wide = yf.download(tickers, start=start, auto_adjust=False, actions=False, progress=False, threads=True)
    raw = wide.stack(level="Ticker").reset_index()
    raw.columns = [str(c).lower().replace(" ", "_") for c in raw.columns]
    return raw.rename(columns={"price": "date"}).sort_values(["ticker", "date"], ignore_index=True)


def trading_calendar(raw: pd.DataFrame, stock_tickers: set[str]) -> pd.DatetimeIndex:
    """NSE trading days = dates on which at least half the stocks have a bar.

    Derived from the data instead of a holiday list: a stray row for one ticker on a holiday
    doesn't create a session, and an index's missing day doesn't remove one.
    """
    stocks = raw[raw["ticker"].isin(stock_tickers) & raw["close"].notna()]
    counts = stocks.groupby("date")["ticker"].nunique()
    return pd.DatetimeIndex(counts[counts >= len(stock_tickers) / 2].index).sort_values()


def clean(
    raw: pd.DataFrame, tickers: dict[str, str], starts: dict[str, pd.Timestamp] | None = None
) -> pd.DataFrame:
    """Raw long bars → PriceBar rows on the trading calendar, small gaps forward-filled and flagged."""
    raw = raw[raw["ticker"].isin(tickers.keys())]
    cal = trading_calendar(raw, {t for t, s in tickers.items() if t != s})
    raw = raw[(raw[PRICE_COLS] > 0).all(axis=1)]  # also drops NaN rows
    for ticker, start in (starts or {}).items():
        raw = raw[(raw["ticker"] != ticker) | (raw["date"] >= start)]

    frames = []
    for ticker, g in raw.groupby("ticker"):
        g = g.drop_duplicates("date", keep="last").set_index("date")
        g = g.reindex(cal[cal >= g.index.min()])
        g["filled"] = g["close"].isna()
        g[PRICE_COLS] = g[PRICE_COLS].ffill(limit=MAX_FILL_DAYS)
        g["volume"] = g["volume"].fillna(0)
        g = g.dropna(subset=PRICE_COLS)  # gap longer than MAX_FILL_DAYS: leave it missing
        g["symbol"] = tickers[ticker]
        frames.append(g.reset_index(names="date"))

    prices = pd.concat(frames, ignore_index=True)
    prices["volume"] = prices["volume"].astype("int64")
    prices["available_at"] = (prices["date"] + CLOSE_IST).dt.tz_localize("Asia/Kolkata").dt.tz_convert(UTC)
    prices = prices[["date", "symbol", *PRICE_COLS, "volume", "filled", "available_at"]]

    # VIX genuinely jumps 40%+ on crash days; it is a volatility level, not a price.
    jumps = returns(prices).drop(columns="^INDIAVIX", errors="ignore").abs().gt(JUMP).stack()
    for d, sym in jumps[jumps].index:
        log.warning("suspicious jump", extra={"fields": {"symbol": sym, "date": str(d.date())}})
    return prices.sort_values(["symbol", "date"], ignore_index=True)


def returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Daily simple returns from adj_close, wide (date × symbol). Log returns: np.log1p(returns(...))."""
    panel = prices.pivot(index="date", columns="symbol", values="adj_close")
    return panel.pct_change(fill_method=None).iloc[1:]


def save(prices: pd.DataFrame, out_dir: Path) -> None:
    """Rewrite the whole year-partitioned dataset (partition writes append, so a re-run would duplicate)."""
    shutil.rmtree(out_dir, ignore_errors=True)
    prices.assign(year=prices["date"].dt.year).to_parquet(out_dir, partition_cols=["year"], index=False)


def read(path: Path, key: str, since: date | None = None) -> pd.DataFrame:
    """Read a dataset written by save(); `since` skips whole year partitions before it."""
    df = pd.read_parquet(path, filters=[("year", ">=", since.year)] if since else None).drop(columns="year")
    if since:
        df = df[df["date"] >= pd.Timestamp(since)]
    return df.sort_values([key, "date"], ignore_index=True)


def load_prices(data_dir: Path, since: date | None = None) -> pd.DataFrame:
    # One row per symbol and day even if a dataset was ever written twice (e.g. two copies in S3).
    df = read(data_dir / "processed" / "market" / "prices", "symbol", since)
    return df.drop_duplicates(["symbol", "date"], keep="last", ignore_index=True)


def refresh(settings=None):
    """One run of this job; called by the CLI below and by the scheduled Lambda (app/aws/handlers.py)."""
    settings = settings or get_settings()
    tickers = load_tickers(settings.config_dir)
    raw = download(list(tickers))

    raw_dir = settings.data_dir / "raw" / "market" / datetime.now(UTC).strftime("%Y/%m/%d")
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(raw_dir / "yfinance.parquet", index=False)

    prices = clean(raw, tickers, history_starts(settings.config_dir))
    save(prices, settings.data_dir / "processed" / "market" / "prices")
    missing = sorted(set(tickers.values()) - set(prices["symbol"]))
    log.info(
        "market data done",
        extra={
            "fields": {
                "symbols": prices["symbol"].nunique(),
                "rows": len(prices),
                "from": str(prices["date"].min().date()),
                "to": str(prices["date"].max().date()),
                "filled_rows": int(prices["filled"].sum()),
                "missing_symbols": missing,
            }
        },
    )
    return str(prices["date"].max().date())


def main() -> None:
    from app.utils.log import setup_logging

    setup_logging(get_settings().log_level)
    refresh()


if __name__ == "__main__":
    main()
