"""News → portfolio impact (Phase 8). Formula in config/news_sources.yaml (`impact`)."""

from datetime import datetime, timedelta

import pandas as pd

from app.analytics.exposure import UNMAPPED
from app.models.exposure import ExposureReport
from app.models.news import NewsImpactItem, PortfolioNews, Sentiment
from app.services.news_pipeline import recency


def article_exposure(
    symbols: list[str], sectors: list[str], e_s: dict[str, float], e_k: dict[str, float], discount: float
) -> tuple[float, str]:
    held = [s for s in symbols if e_s.get(s)]
    if held:
        return sum(e_s[s] for s in held), "company"
    return discount * sum(e_k.get(k, 0.0) for k in sectors), "sector"


def portfolio_news(
    news: pd.DataFrame,
    exp: ExposureReport,
    as_of: datetime,
    cfg: dict,
    half_life_hours: float,
    limit: int = 50,
) -> PortfolioNews:
    """news: processed news joined to sentiment (app.services.sentiment.news_with_sentiment)."""
    lookback = cfg["lookback_hours"]
    e_s = {c.symbol: c.effective for c in exp.companies}
    e_k = {s.sector: s.effective for s in exp.sectors if s.sector != UNMAPPED}
    window = news[
        (news["published_at"] <= pd.Timestamp(as_of))
        & (news["published_at"] >= pd.Timestamp(as_of - timedelta(hours=lookback)))
    ]
    items = []
    for r in window.itertuples():
        exposure, via = article_exposure(list(r.symbols), list(r.sectors), e_s, e_k, cfg["sector_discount"])
        if not exposure:
            continue
        rec = recency((pd.Timestamp(as_of) - r.published_at).total_seconds() / 3600, half_life_hours)
        impact = r.score * r.importance * rec * r.reliability * exposure
        items.append(
            NewsImpactItem(
                news_id=r.news_id,
                headline=r.headline,
                source=r.source,
                url=r.url,
                published_at=r.published_at,
                symbols=list(r.symbols),
                sectors=list(r.sectors),
                sentiment=Sentiment(label=r.label, score=r.score, confidence=r.confidence),
                importance=r.importance,
                reliability=r.reliability,
                recency=round(rec, 4),
                matched_via=via,
                effective_exposure=round(exposure, 6),
                impact=round(impact, 6),
            )
        )
    total = sum(i.impact for i in items)
    notes = [] if len(window) else [f"no scored news in the last {lookback} h (is the collector running?)"]
    return PortfolioNews(
        portfolio_id=exp.portfolio_id,
        as_of=as_of,
        lookback_hours=lookback,
        portfolio_news_impact=round(total, 6),
        alert=total <= -cfg["alert_threshold"],
        alert_threshold=cfg["alert_threshold"],
        items=sorted(items, key=lambda i: -abs(i.impact))[:limit],
        notes=notes + exp.notes,
    )
