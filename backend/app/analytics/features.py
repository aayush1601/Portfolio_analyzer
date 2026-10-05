"""Point-in-time features and forward-return targets (Phase 9). Pure pandas, no model dependencies.

Leakage rule (NFR7): a row dated t uses only data knowable at t's 15:30 IST close. Prices: bars up to and
including t. News: published at or before 15:30 IST on t; anything later counts toward the next trading day.
Targets: adj_close(t+h) / adj_close(t) − 1, so they start strictly after every feature's information set.
"""

import numpy as np
import pandas as pd

MARKET_FEATURES = [
    "ret_1d", "ret_5d", "ret_20d", "ret_60d", "rel_ret_20d", "vol_20d", "vol_60d",
    "dist_52w_high", "volume_z_20d", "beta_60d", "mkt_ret_5d", "mkt_ret_20d", "vix", "vix_chg_5d",
]  # fmt: skip
NEWS_FEATURES = ["news_count_7d", "news_score_3d", "news_score_7d", "news_neg_share_7d"]
HORIZONS = (5, 20)
FEATURE_LABELS = {
    "ret_1d": "1-day return",
    "ret_5d": "5-day return",
    "ret_20d": "20-day return",
    "ret_60d": "60-day return",
    "rel_ret_20d": "20-day return vs NIFTY",
    "vol_20d": "20-day volatility",
    "vol_60d": "60-day volatility",
    "dist_52w_high": "distance from 52-week high",
    "volume_z_20d": "unusual volume",
    "beta_60d": "60-day beta",
    "mkt_ret_5d": "NIFTY 5-day return",
    "mkt_ret_20d": "NIFTY 20-day return",
    "vix": "India VIX",
    "vix_chg_5d": "VIX 5-day change",
    "news_count_7d": "news volume (7d)",
    "news_score_3d": "news sentiment (3d)",
    "news_score_7d": "news sentiment (7d)",
    "news_neg_share_7d": "share of negative news (7d)",
}
INDEX, VIX = "^NSEI", "^INDIAVIX"
CLOSE_IST = pd.Timedelta(hours=15, minutes=30)


def _stack(wide: pd.DataFrame, name: str) -> pd.Series:
    return wide.stack(future_stack=True).rename(name)


def market_features(prices: pd.DataFrame) -> pd.DataFrame:
    """One row per (date, symbol) for every stock (index and VIX supply market-wide columns only)."""
    px = prices.pivot(index="date", columns="symbol", values="adj_close").sort_index()
    vol = prices.pivot(index="date", columns="symbol", values="volume").sort_index()
    stocks = [c for c in px.columns if c not in (INDEX, VIX)]
    r = px[stocks].pct_change(fill_method=None)
    mkt = px[INDEX].pct_change(fill_method=None)

    cols = {
        "ret_1d": r,
        "ret_5d": px[stocks].pct_change(5, fill_method=None),
        "ret_20d": px[stocks].pct_change(20, fill_method=None),
        "ret_60d": px[stocks].pct_change(60, fill_method=None),
        "vol_20d": r.rolling(20).std() * np.sqrt(252),
        "vol_60d": r.rolling(60).std() * np.sqrt(252),
        "dist_52w_high": px[stocks] / px[stocks].rolling(252, min_periods=60).max() - 1,
        "beta_60d": r.rolling(60).cov(mkt).div(mkt.rolling(60).var(), axis=0),
    }
    lv = np.log1p(vol[stocks].where(vol[stocks] > 0))
    cols["volume_z_20d"] = (lv - lv.rolling(20).mean()) / lv.rolling(20).std()
    mkt_20 = px[INDEX].pct_change(20, fill_method=None)
    cols["rel_ret_20d"] = cols["ret_20d"].sub(mkt_20, axis=0)

    df = pd.concat([_stack(v, k) for k, v in cols.items()], axis=1)
    df.index.names = ["date", "symbol"]
    df = df.reset_index()
    market = pd.DataFrame(
        {
            "mkt_ret_5d": px[INDEX].pct_change(5, fill_method=None),
            "mkt_ret_20d": mkt_20,
            "vix": px[VIX],
            "vix_chg_5d": px[VIX].pct_change(5, fill_method=None),
        }
    )
    return df.merge(market, left_on="date", right_index=True, how="left")


def news_features(news: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Per (trading date, symbol): article count and mean FinBERT score over trailing 3/7 trading days.

    news: one row per article with published_at (UTC), symbols (list), score, label. Rows with no news get
    count 0 and score 0 (neutral), so the model can tell "no news" from "neutral news" via the count.
    """
    if news.empty:
        return pd.DataFrame(columns=["date", "symbol", *NEWS_FEATURES])
    n = news.explode("symbols").dropna(subset=["symbols"]).reset_index(drop=True)
    ist = n["published_at"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    after_close = ist - ist.dt.normalize() > CLOSE_IST
    day = ist.dt.normalize() + pd.to_timedelta(after_close.astype(int), unit="D")
    # first trading date on or after that day; news after the last known date falls off
    pos = dates.searchsorted(day)
    n = n.assign(date=dates[np.minimum(pos, len(dates) - 1)], keep=pos < len(dates))
    n = n[n["keep"]].assign(neg=n["label"].eq("negative").astype(float))

    daily = n.groupby(["symbols", "date"]).agg(
        cnt=("score", "size"), ssum=("score", "sum"), nsum=("neg", "sum")
    )
    out = []
    for sym, g in daily.groupby(level=0):
        g = g.droplevel(0).reindex(dates, fill_value=0)
        c3, c7 = g["cnt"].rolling(3, min_periods=1).sum(), g["cnt"].rolling(7, min_periods=1).sum()
        out.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "symbol": sym,
                    "news_count_7d": c7.to_numpy(),
                    "news_score_3d": (g["ssum"].rolling(3, min_periods=1).sum() / c3.replace(0, np.nan))
                    .fillna(0)
                    .to_numpy(),
                    "news_score_7d": (g["ssum"].rolling(7, min_periods=1).sum() / c7.replace(0, np.nan))
                    .fillna(0)
                    .to_numpy(),
                    "news_neg_share_7d": (g["nsum"].rolling(7, min_periods=1).sum() / c7.replace(0, np.nan))
                    .fillna(0)
                    .to_numpy(),
                }
            )
        )
    return pd.concat(out, ignore_index=True)


def targets(prices: pd.DataFrame, horizons: tuple[int, ...] = HORIZONS) -> pd.DataFrame:
    px = prices.pivot(index="date", columns="symbol", values="adj_close").sort_index()
    px = px.drop(columns=[c for c in (INDEX, VIX) if c in px.columns])
    cols = [_stack(px.shift(-h) / px - 1, f"fwd_{h}d") for h in horizons]
    df = pd.concat(cols, axis=1)
    df.index.names = ["date", "symbol"]
    return df.reset_index()


def build_dataset(prices: pd.DataFrame, news: pd.DataFrame) -> pd.DataFrame:
    """Features + targets, one row per (date, symbol). Targets are NaN for the last h days (not yet known)."""
    f = market_features(prices)
    dates = pd.DatetimeIndex(sorted(f["date"].unique()))
    nf = news_features(news, dates)
    f = f.merge(nf, on=["date", "symbol"], how="left")
    f[NEWS_FEATURES] = f[NEWS_FEATURES].fillna(0.0)
    return f.merge(targets(prices), on=["date", "symbol"], how="left").sort_values(
        ["date", "symbol"], ignore_index=True
    )
