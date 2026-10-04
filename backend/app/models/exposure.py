"""Look-through exposure, stress and fund analytics (FR4, FR8, FR11). Weights are fractions."""

from datetime import date

from pydantic import BaseModel, Field


class Via(BaseModel):
    fund: str
    contribution: float


class CompanyExposure(BaseModel):
    symbol: str
    sector: str
    direct: float
    indirect: float
    effective: float
    via: list[Via]


class SectorExposure(BaseModel):
    sector: str
    direct: float
    effective: float


class FundOverlap(BaseModel):
    fund_a: str
    fund_b: str
    overlap: float  # Σ_isin min(h_A, h_B)


class ExposureReport(BaseModel):
    portfolio_id: str
    as_of: date
    holdings_as_of: dict[str, str]  # scheme_code → disclosure month used (point-in-time)
    companies: list[CompanyExposure]
    sectors: list[SectorExposure]  # sums to 1 − cash, including "Other/Unmapped"
    overlap: list[FundOverlap]
    unmapped: (
        float  # fund weight not in universe stocks: non-universe stocks, debt, cash, missing disclosures
    )
    hhi_effective: float
    n_effective: float | None  # 1 / HHI
    notes: list[str]


class StressRequest(BaseModel):
    scenario: str = "custom"
    shocks: dict[str, float] = Field(description="sector → return shock, e.g. -0.10 for −10%")


class StressContributor(BaseModel):
    symbol: str
    loss: float


class StressResult(BaseModel):
    scenario: str
    estimated_loss: float  # fraction of portfolio value; negative = loss
    estimated_loss_inr: float
    top_contributors: list[StressContributor]
    unshocked_unmapped: float  # fund weight we can't see into and that no shock was applied to


class FundRisk(BaseModel):
    volatility_ann: float
    sharpe: float
    max_drawdown: float
    var_1d: float  # historical, 95%
    beta: float


class FundHolding(BaseModel):
    isin: str
    symbol: str | None
    name: str
    weight: float


class IndustryWeight(BaseModel):
    industry: str
    weight: float


class FundAnalytics(BaseModel):
    scheme_code: str
    name: str
    amc: str
    category: str
    as_of: date
    nav: float
    returns: dict[str, float | None]  # 1d, 1m, 3m, 6m (simple); cagr_1y, cagr_3y, cagr_5y
    risk: FundRisk  # last 252 trading days
    expense_ratio: float | None
    aum: float | None
    holdings_as_of: str | None
    top_holdings: list[FundHolding]
    sector_mix: list[IndustryWeight]  # AMC's own industry labels, all holdings
    notes: list[str]
