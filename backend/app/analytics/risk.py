"""Risk engine (Phase 4). Pure functions over daily return series; formulas follow the usual textbook forms.

Portfolio returns use *current* weights applied to historical asset returns ("how would today's portfolio
have behaved"), not the user's actual past trades. Annualisation: 252 trading days.
"""

from statistics import NormalDist

import numpy as np
import pandas as pd

from app.models.risk import Histogram, RiskReport, VaR

TRADING_DAYS = 252
MC_SIMS = 10_000


def asset_returns(prices: pd.DataFrame, navs: pd.DataFrame) -> pd.DataFrame:
    """Daily simple returns, date × asset_id, for stocks (adj_close) and funds (NAV) on the NSE calendar."""
    stock = prices.pivot(index="date", columns="symbol", values="adj_close")
    nav = navs.pivot(index="date", columns="scheme_code", values="nav").reindex(stock.index).ffill(limit=5)
    return pd.concat([stock, nav], axis=1, sort=True).pct_change(fill_method=None).iloc[1:]


def max_drawdown(r: pd.Series) -> float:
    wealth = pd.concat([pd.Series([1.0]), (1 + r).cumprod()], ignore_index=True)
    return float((wealth / wealth.cummax() - 1).min())


def var_historical(r: pd.Series, c: float) -> float:
    return float(-np.quantile(r, 1 - c))


def var_parametric(r: pd.Series, c: float) -> float:
    return float(-(r.mean() + NormalDist().inv_cdf(1 - c) * r.std()))


def var_monte_carlo(R: pd.DataFrame, w: pd.Series, c: float, n: int = MC_SIMS, seed: int = 0) -> float:
    """Simulate joint asset returns from a multivariate normal fitted to R (seeded: reproducible)."""
    sims = np.random.default_rng(seed).multivariate_normal(R.mean(), R.cov(), n) @ w.to_numpy()
    return float(-np.quantile(sims, 1 - c))


def cvar_historical(r: pd.Series, c: float) -> float:
    """Expected loss on the days at or beyond historical VaR."""
    return float(-r[r <= -var_historical(r, c)].mean())


def beta(r: pd.Series, market: pd.Series) -> float:
    both = pd.concat([r, market], axis=1, sort=True).dropna()
    return float(both.cov().iloc[0, 1] / both.iloc[:, 1].var())


def hhi(w: pd.Series) -> float:
    """Herfindahl index of risky weights renormalised to 1: 1/N for equal weights, 1 for a single asset."""
    return float(((w / w.sum()) ** 2).sum())


def diversification_ratio(R: pd.DataFrame, w: pd.Series) -> float:
    return float((w * R.std()).sum() / (R @ w).std())


def score_component(x: float, low: float, high: float) -> float:
    return float(np.clip((x - low) / (high - low), 0, 1) * 100)


def risk_score(metrics: dict[str, float], cfg: dict) -> tuple[int, str]:
    comps = cfg["components"]
    total_w = sum(c["weight"] for c in comps.values())
    score = (
        sum(c["weight"] * score_component(metrics[k], c["low"], c["high"]) for k, c in comps.items())
        / total_w
    )
    score = round(score)
    band = next(name for name, upper in cfg["bands"].items() if score <= upper)
    return score, band


def risk_report(
    R: pd.DataFrame,
    weights: pd.Series,
    market: pd.Series,
    *,
    lookback: int,
    confidence: float,
    rf: float | None,
    cfg: dict,
) -> RiskReport:
    """R: asset returns (date × asset_id); market: benchmark returns.

    weights: risky assets' share of total portfolio value. Cash is excluded, so weights may sum to < 1
    and cash dampens risk.
    """
    notes = []
    if weights.empty:
        raise ValueError("portfolio has no risky assets")
    R = R[weights.index].dropna().tail(lookback)
    if len(R) < 30:
        raise ValueError(f"only {len(R)} days of overlapping history; need at least 30")
    if len(R) < lookback:
        notes.append(
            f"only {len(R)} overlapping trading days (asset with a short history); lookback shortened"
        )
    if rf is None:
        notes.append("risk-free rate not set in config/universe.yaml; Sharpe and Sortino use 0")
    rf = rf or 0.0

    r = R @ weights
    rf_d = rf / TRADING_DAYS
    ret_ann = float(r.mean() * TRADING_DAYS)
    vol_ann = float(r.std() * np.sqrt(TRADING_DAYS))
    downside = float(np.sqrt((np.minimum(r - rf_d, 0) ** 2).mean()) * np.sqrt(TRADING_DAYS))
    corr = R.corr().to_numpy()[np.triu_indices(len(weights), 1)]
    dr = diversification_ratio(R, weights)

    metrics = dict(
        volatility_ann=vol_ann,
        max_drawdown=max_drawdown(r),
        var_1d_95=var_historical(r, 0.95),
        beta=beta(r, market),
        hhi=hhi(weights),
    )
    score, band = risk_score(metrics, cfg)
    counts, edges = np.histogram(r, bins=40)
    return RiskReport(
        as_of=R.index[-1].date(),
        lookback_days=lookback,
        observations=len(R),
        confidence=confidence,
        risk_free_rate=rf,
        return_ann=ret_ann,
        volatility_ann=vol_ann,
        sharpe=(ret_ann - rf) / vol_ann if vol_ann else 0.0,
        sortino=(ret_ann - rf) / downside if downside else 0.0,
        max_drawdown=metrics["max_drawdown"],
        var_1d=VaR(
            historical=var_historical(r, confidence),
            parametric=var_parametric(r, confidence),
            monte_carlo=var_monte_carlo(R, weights, confidence),
        ),
        cvar_1d=cvar_historical(r, confidence),
        beta=metrics["beta"],
        avg_correlation=float(corr.mean()) if corr.size else None,
        hhi_direct=metrics["hhi"],
        diversification_ratio=dr,
        diversification_score=round(float(np.clip(100 * (1 - 1 / dr), 0, 100))),
        risk_score=score,
        risk_band=band,
        score_weights_version=cfg["version"],
        return_histogram=Histogram(edges=edges.round(6).tolist(), counts=counts.tolist()),
        notes=notes,
    )
