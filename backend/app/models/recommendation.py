"""Explainable recommendations (FR7). Hypothetical research output, not financial advice."""

from datetime import datetime

from pydantic import BaseModel


class Recommendation(BaseModel):
    asset_id: str
    asset_type: str
    action: str  # STOCK: BUY | HOLD | REDUCE; MF: INCREASE | HOLD | REDUCE | SWITCH
    final_score: float  # 0-100
    components: dict[str, float | None]  # 0-100 each; None = not available for this asset yet
    reasons: list[str]
    constraints_triggered: list[str]
    switch_to: str | None = None


class RecommendationReport(BaseModel):
    portfolio_id: str
    as_of: datetime
    disclaimer: str
    config_version: str
    items: list[Recommendation]
    notes: list[str]
