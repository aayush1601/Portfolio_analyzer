"""Risk report (FR5). Returns and losses are daily fractions; VaR/CVaR are positive losses (0.021 = 2.1%)."""

from datetime import date

from pydantic import BaseModel


class VaR(BaseModel):
    historical: float
    parametric: float
    monte_carlo: float


class Histogram(BaseModel):
    edges: list[float]  # bin edges, daily return fractions (len = len(counts) + 1)
    counts: list[int]


class HoldingPeriod(BaseModel):
    """How today's mix might end up after holding it for `days` trading days."""

    label: str
    days: int
    prob_loss: float  # chance of ending below today's value
    median_return: float  # typical outcome
    bad_return: float  # 1-in-20 bad outcome (5% quantile)
    bad_inr: float
    observed_prob_loss: float | None  # share of past windows of this length that ended down
    observed_bad_return: float | None
    observed_windows: int  # overlapping windows behind the observed figures (0 = not enough history)


class RiskReport(BaseModel):
    as_of: date
    lookback_days: int
    observations: int  # days actually used; fewer than lookback when an asset has a short history
    confidence: float
    risk_free_rate: float
    return_ann: float
    volatility_ann: float
    sharpe: float
    sortino: float
    max_drawdown: float  # within the chosen window
    score_drawdown: float  # over the fixed scoring window (what the risk score uses)
    score_drawdown_days: int
    var_1d: VaR
    cvar_1d: float
    beta: float  # vs NIFTY 50 (^NSEI)
    avg_correlation: float | None  # mean pairwise correlation of risky assets; None with one asset
    hhi_direct: float  # on direct risky weights renormalised to 1 (this one feeds the risk score)
    hhi_effective: float | None = None  # Σ E_s² over look-through company exposure (Phase 5)
    diversification_ratio: float  # Σ wᵢσᵢ / σₚ ≥ 1
    diversification_score: int
    risk_score: int
    risk_band: str
    score_weights_version: str
    holding_periods: list[HoldingPeriod]
    holding_history_days: int  # daily history the holding-period estimates use
    holding_mean_return_ann: float  # the average return they assume continues
    return_histogram: Histogram  # the portfolio's daily returns over the window, for the tail chart
    notes: list[str]


class RiskSnapshot(BaseModel):
    """One stored risk_refresh result (AP4); newest first in /risk/history."""

    as_of: date
    risk_score: int
    risk_band: str
    volatility_ann: float
    var_1d: float  # historical 1-day VaR
    weights_version: str
