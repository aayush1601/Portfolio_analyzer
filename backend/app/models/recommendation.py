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
    blocked_action: str | None = None  # what the scores proposed before a safety rule overrode it
    shap_top: list[dict] = []  # model drivers behind expected_return: feature, value, shap


class RecommendationReport(BaseModel):
    portfolio_id: str
    as_of: datetime
    disclaimer: str
    config_version: str
    weights: dict[str, float]  # component weights used for final_score (0 = shown for information only)
    items: list[Recommendation]
    notes: list[str]
