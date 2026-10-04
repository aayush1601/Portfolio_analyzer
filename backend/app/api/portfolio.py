"""Portfolio routes (FR2–FR5, FR8): create, list, value, replace holdings, risk, exposure, stress.

Contract: docs/api/openapi.yaml.
"""

from datetime import date, timedelta
from functools import lru_cache
from typing import Annotated

import pandas as pd
import yaml
from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.analytics.exposure import UNMAPPED, effective_exposure, latest_holdings, stress
from app.analytics.portfolio import MissingPrice, value_portfolio
from app.analytics.risk import asset_returns, risk_report
from app.config import get_settings
from app.models.exposure import ExposureReport, StressRequest, StressResult
from app.models.portfolio import AssetType, Holding, Holdings, Portfolio, PortfolioCreate, PortfolioSnapshot
from app.models.risk import RiskReport
from app.services.fund_holdings import load_holdings
from app.services.market_data import load_prices
from app.services.nav_data import load_navs
from app.services.portfolio_store import PID_PATTERN, PortfolioStore

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
PortfolioId = Annotated[str, Path(pattern=PID_PATTERN)]


def current_user() -> str:
    return "local"  # local stub (FR1); Phase 17 takes this from the verified Cognito JWT `sub`


@lru_cache
def get_store() -> PortfolioStore:
    s = get_settings()
    return PortfolioStore(s.data_dir / "portfolios", s.config_dir / "demo_portfolios.yaml")


def read_config(name: str) -> dict:
    return yaml.safe_load((get_settings().config_dir / name).read_text())


@lru_cache
def universe_assets() -> dict[AssetType, set[str]]:
    u = read_config("universe.yaml")
    return {
        AssetType.STOCK: {s["symbol"] for s in u["stocks"]},
        AssetType.MF: {str(f["scheme_code"]) for f in u["mutual_funds"]},
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


@router.get("/{portfolio_id}/risk")
def get_risk(
    portfolio_id: PortfolioId,
    user: User,
    store: Store,
    confidence: Annotated[float, Query(ge=0.8, le=0.995)] = 0.95,
    lookback_days: Annotated[int, Query(ge=60, le=1260)] = 252,
) -> RiskReport:
    p = owned(store, user, portfolio_id)
    # ~1.5 calendar days per trading day, plus holidays
    prices, navs = load_market(date.today() - timedelta(days=int(lookback_days * 1.5) + 30))
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
            cfg=read_config("risk_score.yaml"),
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


@router.put("/{portfolio_id}/holdings")
def replace_holdings(
    portfolio_id: PortfolioId, holdings: Holdings, user: User, store: Store
) -> dict[str, str]:
    p = owned(store, user, portfolio_id)
    check_universe(holdings)
    store.save(user, p.model_copy(update={"holdings": holdings}))
    return {"portfolio_id": p.portfolio_id}
