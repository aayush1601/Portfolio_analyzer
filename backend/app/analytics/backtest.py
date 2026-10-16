"""Walk-forward backtest engine (Phase 12). Pure functions over daily returns; no I/O.

Leakage rule: weights chosen at the close of rebalance date t use only returns dated ≤ t (and news published
≤ t's close, disclosures published ≤ t); they earn returns from the next trading day. Between rebalances the
weights drift with prices. Trading cost = cost_bps × value traded (Σ|Δw|), charged on the first day of each
period; turnover is reported as value traded per year.
"""

from collections.abc import Callable

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def month_ends(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last trading day of each calendar month."""
    s = pd.Series(dates, index=dates)
    return pd.DatetimeIndex(s.groupby([dates.year, dates.month]).max().to_numpy())


def simulate(
    R: pd.DataFrame,
    rebalances: list[pd.Timestamp],
    weights_at: Callable[[pd.Timestamp], pd.Series],
    cost_bps: float,
    end: pd.Timestamp,
    rebalance: bool = True,
) -> pd.DataFrame:
    """Daily portfolio return and turnover. weights_at(t) → risky weights (cash = 1 − Σw, earning 0).

    rebalance=False sets weights once (buy and hold) and lets them drift to the end.
    """
    rows = []
    w = pd.Series(dtype=float)  # current drifted weights
    for k, t in enumerate(rebalances):
        nxt = rebalances[k + 1] if rebalance and k + 1 < len(rebalances) else end
        days = R.index[(R.index > t) & (R.index <= nxt)]
        if days.empty:
            continue
        if k == 0 or rebalance:
            target = weights_at(t)
            traded = float(
                target.sub(w, fill_value=0).abs().sum()
            )  # value bought + sold; cash is the residual
            w = target.copy()
        else:
            traded = 0.0
        cost = traded * cost_bps / 1e4
        for i, d in enumerate(days):
            r = R.loc[d, w.index].fillna(0.0)
            rp = float(w @ r)
            rows.append(
                {"date": d, "ret": rp - (cost if i == 0 else 0.0), "turnover": traded if i == 0 else 0.0}
            )
            w = w * (1 + r) / (1 + rp)  # cash share drifts implicitly: 1 − Σw
        if not rebalance:
            break
    return pd.DataFrame(rows).set_index("date")


def gross_returns(ret: pd.Series, turnover: pd.Series, cost_bps: float) -> pd.Series:
    """Returns before trading costs; simulate() charges turnover × cost on the day it reports turnover."""
    return ret + turnover.reindex(ret.index).fillna(0.0) * cost_bps / 1e4


def first_covered(hits: dict[pd.Timestamp, int]) -> pd.Timestamp | None:
    """First rebalance date at which the news layer had any evidence (start of the news window)."""
    covered = sorted(t for t, n in hits.items() if n)
    return covered[0] if covered else None


def metrics(r: pd.Series, turnover: pd.Series | None = None, rf: float = 0.0) -> dict[str, float]:
    """Annualised performance of a daily return series."""
    years = len(r) / TRADING_DAYS
    wealth = (1 + r).cumprod()
    cagr = float(wealth.iloc[-1] ** (1 / years) - 1) if years > 0 else 0.0
    vol = float(r.std() * np.sqrt(TRADING_DAYS))
    downside = float(np.sqrt((np.minimum(r - rf / TRADING_DAYS, 0) ** 2).mean()) * np.sqrt(TRADING_DAYS))
    mdd = float((wealth / wealth.cummax() - 1).min())
    ann = float(r.mean() * TRADING_DAYS)
    var95 = float(-np.quantile(r, 0.05))
    return {
        "cagr": cagr,
        "volatility": vol,
        "sharpe": (ann - rf) / vol if vol else 0.0,
        "sortino": (ann - rf) / downside if downside else 0.0,
        "max_drawdown": mdd,
        "calmar": cagr / -mdd if mdd < 0 else 0.0,
        "cvar_95": float(-r[r <= -var95].mean()),
        "turnover": float(turnover.sum() / years) if turnover is not None and years > 0 else 0.0,
    }


def sharpe(r: np.ndarray) -> np.ndarray:
    """Annualised Sharpe along the last axis."""
    sd = r.std(axis=-1, ddof=1)
    return np.where(sd > 0, r.mean(axis=-1) / np.where(sd > 0, sd, 1) * np.sqrt(TRADING_DAYS), 0.0)


def stationary_bootstrap_indices(T: int, resamples: int, block: float, seed: int) -> np.ndarray:
    """Politis-Romano stationary bootstrap: blocks of geometric length (mean `block`), wrapping around."""
    rng = np.random.default_rng(seed)
    idx = np.empty((resamples, T), dtype=np.int64)
    idx[:, 0] = rng.integers(T, size=resamples)
    jump = rng.random((resamples, T)) < 1 / block
    fresh = rng.integers(T, size=(resamples, T))
    for t in range(1, T):
        idx[:, t] = np.where(jump[:, t], fresh[:, t], (idx[:, t - 1] + 1) % T)
    return idx


def sharpe_difference_test(a: pd.Series, b: pd.Series, resamples: int, block: float, seed: int) -> dict:
    """H1: Sharpe(a) > Sharpe(b). Both series are resampled with the same blocks (keeps their correlation).

    p-value: share of bootstrap differences ≤ 0. Returns the observed difference and a 95% interval.
    """
    both = pd.concat([a, b], axis=1, join="inner").dropna().to_numpy().T
    obs = float(sharpe(both[0]) - sharpe(both[1]))
    idx = stationary_bootstrap_indices(both.shape[1], resamples, block, seed)
    diff = sharpe(both[0][idx]) - sharpe(both[1][idx])
    return {
        "sharpe_diff": obs,
        "p_value": float((diff <= 0).mean()),
        "ci_low": float(np.quantile(diff, 0.025)),
        "ci_high": float(np.quantile(diff, 0.975)),
    }


def regimes(market: pd.Series, vix: pd.Series, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Label each day by the regime known the day before: market trend (6-month return) and volatility (VIX
    above or below its full-sample median; descriptive, used only to split results, never to trade)."""
    trend = (1 + market).rolling(126).apply(np.prod, raw=True).sub(1).shift(1)
    v = vix.shift(1)
    out = pd.DataFrame(index=index)
    out["trend"] = np.where(trend.reindex(index) >= 0, "Rising market", "Falling market")
    out["volatility"] = np.where(v.reindex(index) > v.median(), "High volatility", "Low volatility")
    return out
