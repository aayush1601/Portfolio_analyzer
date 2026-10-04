"""Risk report (FR5). Returns and losses are daily fractions; VaR/CVaR are positive losses (0.021 = 2.1%)."""

from datetime import date

from pydantic import BaseModel


class VaR(BaseModel):
    historical: float
    parametric: float
    monte_carlo: float


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
    max_drawdown: float
    var_1d: VaR
    cvar_1d: float
    beta: float  # vs NIFTY 50 (^NSEI)
    avg_correlation: float | None  # mean pairwise correlation of risky assets; None with one asset
    hhi_direct: float  # on direct risky weights; look-through hhi_effective arrives in Phase 5
    diversification_ratio: float  # Σ wᵢσᵢ / σₚ ≥ 1
    diversification_score: int
    risk_score: int
    risk_band: str
    score_weights_version: str
    notes: list[str]
