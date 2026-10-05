"""Portfolio routes (FR2–FR8, FR10): holdings, valuation, risk, exposure, stress, news, recommendations.

Contract: docs/api/openapi.yaml.
"""

from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from typing import Annotated

import pandas as pd
import yaml
from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.analytics.exposure import UNMAPPED, effective_exposure, latest_holdings, stress
from app.analytics.impact import portfolio_news
from app.analytics.optimizer import (
    effective_sectors,
    lookthrough_matrix,
    optimize,
    shrunk_cov,
    shrunk_mu,
    stats,
)
from app.analytics.portfolio import MissingPrice, value_history, value_portfolio
from app.analytics.recommend import recommend
from app.analytics.risk import asset_returns, risk_report
from app.analytics.sentiment import ticker_sentiment
from app.config import get_settings
from app.models.allocation import AllocationItem, AllocationReport, SectorShift, Stats
from app.models.exposure import ExposureReport, StressRequest, StressResult
from app.models.news import PortfolioNews
from app.models.portfolio import (
    AssetType,
    Holding,
    Holdings,
    Portfolio,
    PortfolioCreate,
    PortfolioSnapshot,
    ValueHistory,
)
from app.models.recommendation import RecommendationReport
from app.models.risk import RiskReport
from app.services.cas_import import load_registry
from app.services.fund_holdings import load_holdings
from app.services.market_data import load_prices
from app.services.nav_data import load_navs
from app.services.portfolio_store import PID_PATTERN, PortfolioStore
from app.services.sentiment import news_with_sentiment

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
PortfolioId = Annotated[str, Path(pattern=PID_PATTERN)]


def current_user() -> str:
    return "local"  # local stub (FR1); Phase 17 takes this from the verified Cognito JWT `sub`


@lru_cache
def get_store() -> PortfolioStore:
    """JSON files locally; DynamoDB on AWS (same methods)."""
    s = get_settings()
    demo = s.config_dir / "demo_portfolios.yaml"
    if s.storage == "s3":
        from app.aws.ddb_store import DynamoPortfolioStore

        return DynamoPortfolioStore(s.ddb_table, demo)  # type: ignore[return-value]
    return PortfolioStore(s.data_dir / "portfolios", demo)


def read_config(name: str) -> dict:
    return yaml.safe_load((get_settings().config_dir / name).read_text())


def universe_assets() -> dict[AssetType, set[str]]:
    """Holdable assets: the research universe plus any fund registered by a CAS import."""
    u = read_config("universe.yaml")
    return {
        AssetType.STOCK: {s["symbol"] for s in u["stocks"]},
        AssetType.MF: {str(f["scheme_code"]) for f in u["mutual_funds"]}
        | set(load_registry(get_settings().data_dir)),
        AssetType.CASH: {"INR"},
    }


def check_universe(holdings: list[Holding]) -> None:
    unknown = [
        f"{h.asset_type}:{h.asset_id}" for h in holdings if h.asset_id not in universe_assets()[h.asset_type]
    ]
    if unknown:
        raise HTTPException(422, f"not in the research universe (config/universe.yaml): {', '.join(unknown)}")


User = Annotated[str, Depends(current_user)]
Store = Annotated[PortfolioStore, Depends(get_store)]


def owned(store: PortfolioStore, user: str, portfolio_id: str) -> Portfolio:
    p = store.get(user, portfolio_id)
    if p is None:
        raise HTTPException(404, "portfolio not found")
    return p


@router.post("", status_code=201)
def create_portfolio(body: PortfolioCreate, user: User, store: Store) -> dict[str, str]:
    check_universe(body.holdings)
    return {"portfolio_id": store.create(user, body).portfolio_id}


@router.get("")
def list_portfolios(user: User, store: Store) -> list[dict]:
    return [p.model_dump(include={"portfolio_id", "name", "created_at"}) for p in store.list(user)]


def load_market(since: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    data_dir = get_settings().data_dir
    try:
        return load_prices(data_dir, since), load_navs(data_dir, since)
    except FileNotFoundError as e:
        raise HTTPException(503, "market data not loaded; run app.services.market_data and nav_data") from e


def snapshot(p: Portfolio, prices: pd.DataFrame, navs: pd.DataFrame) -> PortfolioSnapshot:
    try:
        return value_portfolio(p, prices, navs)
    except MissingPrice as e:
        raise HTTPException(503, f"{e}; re-run app.services.market_data and nav_data") from e


@router.get("/{portfolio_id}")
def get_portfolio(portfolio_id: PortfolioId, user: User, store: Store) -> PortfolioSnapshot:
    p = owned(store, user, portfolio_id)
    # valuation needs only the last two bars per asset
    return snapshot(p, *load_market(date.today() - timedelta(days=400)))


@router.get("/{portfolio_id}/history")
def get_history(
    portfolio_id: PortfolioId,
    user: User,
    store: Store,
    days: Annotated[int, Query(ge=7, le=3660)] = 365,
) -> ValueHistory:
    p = owned(store, user, portfolio_id)
    since = date.today() - timedelta(days=days)
    prices, navs = load_market(since - timedelta(days=10))
    try:
        return value_history(p, prices, navs, since)
    except MissingPrice as e:
        raise HTTPException(503, f"{e}; re-run app.services.market_data and nav_data") from e


@router.get("/{portfolio_id}/risk")
def get_risk(
    portfolio_id: PortfolioId,
    user: User,
    store: Store,
    confidence: Annotated[float, Query(ge=0.8, le=0.995)] = 0.95,
    lookback_days: Annotated[int, Query(ge=60, le=1260)] = 252,
) -> RiskReport:
    p = owned(store, user, portfolio_id)
    cfg = read_config("risk_score.yaml")
    # ~1.5 calendar days per trading day, plus holidays; the score and holding view need longer history
    days = max(lookback_days, cfg["drawdown_window_days"], cfg["holding_period"]["history_days"])
    prices, navs = load_market(date.today() - timedelta(days=int(days * 1.5) + 30))
    snap = snapshot(p, prices, navs)
    weights = pd.Series({h.asset_id: h.weight for h in snap.holdings if h.asset_type is not AssetType.CASH})
    R = asset_returns(prices, navs)
    try:
        report = risk_report(
            R,
            weights,
            R["^NSEI"],
            lookback=lookback_days,
            confidence=confidence,
            rf=read_config("universe.yaml")["risk_free"]["annual_rate"],
            cfg=cfg,
            portfolio_value=snap.total_value,
        )
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return report.model_copy(update={"hhi_effective": exposure_for(p, snap).hhi_effective})


def stock_sectors() -> dict[str, str]:
    return {s["symbol"]: s["sector"] for s in read_config("universe.yaml")["stocks"]}


def exposure_for(p: Portfolio, snap: PortfolioSnapshot) -> ExposureReport:
    weights = {t: {h.asset_id: h.weight for h in snap.holdings if h.asset_type is t} for t in AssetType}
    holdings = latest_holdings(load_holdings(get_settings().data_dir), snap.as_of)
    return effective_exposure(
        p.portfolio_id, snap.as_of, weights[AssetType.STOCK], weights[AssetType.MF], holdings, stock_sectors()
    )


@router.get("/{portfolio_id}/exposure")
def get_exposure(portfolio_id: PortfolioId, user: User, store: Store) -> ExposureReport:
    p = owned(store, user, portfolio_id)
    return exposure_for(p, snapshot(p, *load_market(date.today() - timedelta(days=400))))


@router.post("/{portfolio_id}/stress")
def run_stress(portfolio_id: PortfolioId, body: StressRequest, user: User, store: Store) -> StressResult:
    valid = set(stock_sectors().values()) | {UNMAPPED}
    if unknown := sorted(set(body.shocks) - valid):
        raise HTTPException(422, f"unknown sectors {unknown}; valid: {sorted(valid)}")
    if any(not -1 <= v <= 1 for v in body.shocks.values()):
        raise HTTPException(422, "shocks are returns between -1 and 1 (e.g. -0.10 for -10%)")
    p = owned(store, user, portfolio_id)
    snap = snapshot(p, *load_market(date.today() - timedelta(days=400)))
    return stress(exposure_for(p, snap), body.shocks, snap.total_value, body.scenario)


@router.get("/{portfolio_id}/news")
def get_news(
    portfolio_id: PortfolioId,
    user: User,
    store: Store,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PortfolioNews:
    p = owned(store, user, portfolio_id)
    exp = exposure_for(p, snapshot(p, *load_market(date.today() - timedelta(days=400))))
    cfg = read_config("news_sources.yaml")
    return portfolio_news(
        scored_news(), exp, datetime.now(UTC), cfg["impact"], cfg["recency_half_life_hours"], limit
    )


def scored_news() -> pd.DataFrame:
    try:
        return news_with_sentiment(get_settings().data_dir)
    except FileNotFoundError:  # pipeline not run yet: callers degrade to "no news"
        return pd.DataFrame(columns=["published_at", "symbols", "score", "confidence"])


@router.get("/{portfolio_id}/optimize")
def get_allocation(
    portfolio_id: PortfolioId,
    user: User,
    store: Store,
    objective: Annotated[str, Query(pattern="^(balanced|min_variance)$")] = "min_variance",
) -> AllocationReport:
    """Model allocation over the universe plus held funds, with caps on look-through exposure (Phase 10)."""
    p = owned(store, user, portfolio_id)
    prices, navs = load_market(allocation_since())
    try:
        return allocation_for(p, snapshot(p, prices, navs), prices, navs, objective)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


def allocation_since() -> date:
    return date.today() - timedelta(days=int(read_config("optimizer.yaml")["lookback_days"] * 1.5) + 30)


def allocation_for(
    p: Portfolio, snap: PortfolioSnapshot, prices: pd.DataFrame, navs: pd.DataFrame, objective: str
) -> AllocationReport:
    """Raises ValueError when no allocation can satisfy every cap."""
    cfg = read_config("optimizer.yaml")
    caps = read_config("recommendations.yaml")["caps"]
    u = read_config("universe.yaml")
    sector_of = {s["symbol"]: s["sector"] for s in u["stocks"]}
    held = {h.asset_id: h for h in snap.holdings if h.asset_type is not AssetType.CASH}
    candidates = set(sector_of) | {str(f["scheme_code"]) for f in u["mutual_funds"]} | set(held)

    R_all = asset_returns(prices, navs)
    R = R_all[[c for c in R_all.columns if c in candidates]].tail(cfg["lookback_days"])
    coverage = R.notna().mean()
    keep = sorted(coverage[coverage >= cfg["min_history_share"]].index)
    excluded = sorted(candidates - set(keep))
    R = R[keep].dropna()
    notes = []
    if dropped_held := [a for a in excluded if a in held]:
        notes.append(f"Kept out for short price history, so held as they are: {', '.join(dropped_held)}")

    mu, Sigma = shrunk_mu(R, cfg["mu_shrinkage"]), shrunk_cov(R, cfg["cov_shrinkage"])
    holdings = latest_holdings(load_holdings(get_settings().data_dir), snap.as_of)
    H, unknown = lookthrough_matrix(keep, set(sector_of), holdings)
    if unknown:
        notes.append(
            f"{len(unknown)} funds have no holdings disclosure yet, so the caps can't see inside them"
        )
    mode = cfg["objectives"][objective]
    w, binding = optimize(
        mu,
        Sigma,
        H,
        sector_of,
        risk_aversion=mode["risk_aversion"],
        max_asset=cfg["max_asset_weight"],
        cash_floor=cfg["cash_floor"],
        caps=caps,
    )

    w0 = pd.Series({a: held[a].weight for a in keep if a in held}).reindex(keep, fill_value=0.0)
    cash0 = sum(h.weight for h in snap.holdings if h.asset_type is AssetType.CASH)
    rf = cfg["risk_free_rate"]
    cur, tgt = stats(w0, mu, Sigma, cash0, rf), stats(w, mu, Sigma, cfg["cash_floor"], rf)
    shown = cfg["min_weight_shown"]
    items = [
        AllocationItem(
            asset_id=a,
            asset_type="STOCK" if a in sector_of else "MF",
            current=round(float(w0[a]), 6),
            target=round(float(w[a]) if w[a] >= shown else 0.0, 6),
            change=round(float((w[a] if w[a] >= shown else 0.0) - w0[a]), 6),
            change_inr=round(float((w[a] if w[a] >= shown else 0.0) - w0[a]) * snap.total_value, 2),
        )
        for a in keep
        if w0[a] >= shown or w[a] >= shown
    ]
    s0, s1 = effective_sectors(w0, H, sector_of), effective_sectors(w, H, sector_of)
    sectors = [
        SectorShift(sector=k, current=round(float(s0.get(k, 0.0)), 6), target=round(float(s1.get(k, 0.0)), 6))
        for k in sorted(set(s0.index) | set(s1.index), key=lambda k: -max(s0.get(k, 0), s1.get(k, 0)))
        if max(s0.get(k, 0), s1.get(k, 0)) >= shown
    ]
    return AllocationReport(
        portfolio_id=p.portfolio_id,
        as_of=snap.as_of,
        objective=objective,
        config_version=cfg["version"],
        current=Stats(expected_return=cur[0], volatility=cur[1]),
        target=Stats(expected_return=tgt[0], volatility=tgt[1]),
        cash_current=round(cash0, 6),
        cash_target=cfg["cash_floor"],
        items=sorted(items, key=lambda i: -abs(i.change)),
        sectors=sectors,
        binding=binding,
        turnover=round(float(((w - w0).abs().sum() + abs(cfg["cash_floor"] - cash0)) / 2), 6),
        notes=notes,
    )


@router.get("/{portfolio_id}/recommendations")
def get_recommendations(portfolio_id: PortfolioId, user: User, store: Store) -> RecommendationReport:
    p = owned(store, user, portfolio_id)
    prices, navs = load_market(min(allocation_since(), date.today() - timedelta(days=420)))
    snap = snapshot(p, prices, navs)
    u = read_config("universe.yaml")
    cfg = read_config("recommendations.yaml")
    try:
        allocation = allocation_for(p, snap, prices, navs, cfg["allocation_objective"])
    except ValueError:
        allocation = None  # recommendations still work from the other components
    sent = ticker_sentiment(
        scored_news(), datetime.now(UTC), read_config("news_sources.yaml")["recency_half_life_hours"]
    )
    return recommend(
        snap,
        exposure_for(p, snap),
        latest_holdings(load_holdings(get_settings().data_dir), snap.as_of),
        asset_returns(prices, navs),
        sent,
        u["mutual_funds"],
        cfg,
        load_predictions(),
        allocation,
    )


def load_predictions() -> pd.DataFrame | None:
    f = get_settings().data_dir / "processed" / "predictions.parquet"
    return pd.read_parquet(f) if f.exists() else None


@router.put("/{portfolio_id}/holdings")
def replace_holdings(
    portfolio_id: PortfolioId, holdings: Holdings, user: User, store: Store
) -> dict[str, str]:
    p = owned(store, user, portfolio_id)
    check_universe(holdings)
    store.save(user, p.model_copy(update={"holdings": holdings}))
    return {"portfolio_id": p.portfolio_id}
