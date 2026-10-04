"""Portfolio news view (FR6, FR10). Impact is a unitless signed score; negative = bad for this portfolio."""

from datetime import datetime

from pydantic import BaseModel


class Sentiment(BaseModel):
    label: str
    score: float
    confidence: float


class NewsImpactItem(BaseModel):
    news_id: str
    headline: str
    source: str
    url: str
    published_at: datetime
    symbols: list[str]
    sectors: list[str]
    sentiment: Sentiment
    importance: float
    reliability: float
    recency: float
    matched_via: str  # "company" or "sector"
    effective_exposure: float
    impact: float


class PortfolioNews(BaseModel):
    portfolio_id: str
    as_of: datetime
    lookback_hours: int
    portfolio_news_impact: float
    alert: bool
    alert_threshold: float
    items: list[NewsImpactItem]  # most impactful first
    notes: list[str]
