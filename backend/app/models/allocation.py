"""Model allocation (Phase 10). Hypothetical research output, not financial advice. Weights are fractions."""

from datetime import date

from pydantic import BaseModel


class AllocationItem(BaseModel):
    asset_id: str
    asset_type: str  # STOCK | MF
    current: float
    target: float
    change: float
    change_inr: float


class SectorShift(BaseModel):
    sector: str
    current: float  # effective (look-through) exposure
    target: float


class Stats(BaseModel):
    expected_return: float  # annual, under the model's μ
    volatility: float  # annual


class AllocationReport(BaseModel):
    portfolio_id: str
    as_of: date
    objective: str  # balanced | min_variance
    config_version: str
    current: Stats
    target: Stats
    cash_current: float
    cash_target: float
    items: list[AllocationItem]  # biggest changes first; assets at 0 in both are left out
    sectors: list[SectorShift]
    binding: list[str]  # constraints the target sits on, e.g. "company cap: HDFCBANK"
    turnover: float  # Σ|change| / 2: share of the portfolio that would change hands
    notes: list[str]
