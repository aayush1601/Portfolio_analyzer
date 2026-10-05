"""Walk-forward splits and forecast metrics for the expected-return models (Phase 9). Model-free, testable."""

import numpy as np
import pandas as pd


def walk_forward_splits(dates: pd.DatetimeIndex, test_years: list[int], horizon: int):
    """Yield (train_dates, test_dates) per calendar year, expanding window.

    Train stops `horizon` trading days before the test year starts: a training row's target looks h days
    ahead, so anything closer would overlap the test period (purging, López de Prado).
    """
    dates = pd.DatetimeIndex(sorted(dates.unique()))
    for y in test_years:
        test = dates[dates.year == y]
        if test.empty:
            continue
        cut = dates.searchsorted(test[0]) - horizon
        if cut <= 0:
            continue
        yield dates[:cut], test


def rank_ic(df: pd.DataFrame, pred: str, target: str) -> pd.Series:
    """Spearman correlation between prediction and realised return across stocks, one value per date."""
    d = df.dropna(subset=[pred, target])
    d = d.groupby("date").filter(lambda g: len(g) >= 5)
    return d.groupby("date").apply(lambda g: g[pred].rank().corr(g[target].rank()), include_groups=False)


def summarise(df: pd.DataFrame, pred: str, target: str, horizon: int) -> dict:
    """Mean rank IC, its t-stat on non-overlapping dates (h-day targets overlap), and hit rate."""
    ic = rank_ic(df, pred, target).dropna()
    spaced = ic.iloc[::horizon]
    t = (
        spaced.mean() / spaced.std(ddof=1) * np.sqrt(len(spaced))
        if len(spaced) > 2 and spaced.std() > 0
        else np.nan
    )
    d = df.dropna(subset=[pred, target])
    hit = float((np.sign(d[pred]) == np.sign(d[target])).mean()) if len(d) else np.nan
    return {
        "rank_ic": float(ic.mean()) if len(ic) else np.nan,
        "ic_tstat": float(t),
        "hit_rate": hit,
        "dates": int(len(ic)),
        "ic_positive_share": float((ic > 0).mean()) if len(ic) else np.nan,
    }


def demean_by_date(df: pd.DataFrame, col: str) -> pd.Series:
    """Return minus that date's cross-sectional mean: the part of a stock's move a ranking can earn."""
    return df[col] - df.groupby("date")[col].transform("mean")
