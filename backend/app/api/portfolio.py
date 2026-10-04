"""Portfolio routes (FR2, FR3): create, list, value, replace holdings. Contract: docs/api/openapi.yaml."""

from datetime import date
from functools import lru_cache
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends, HTTPException, Path

from app.analytics.portfolio import MissingPrice, value_portfolio
from app.config import get_settings
from app.models.portfolio import AssetType, Holding, Holdings, Portfolio, PortfolioCreate, PortfolioSnapshot
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


@lru_cache
def universe_assets() -> dict[AssetType, set[str]]:
    u = yaml.safe_load((get_settings().config_dir / "universe.yaml").read_text())
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


@router.get("/{portfolio_id}")
def get_portfolio(portfolio_id: PortfolioId, user: User, store: Store) -> PortfolioSnapshot:
    p = owned(store, user, portfolio_id)
    data_dir = get_settings().data_dir
    since = date(date.today().year - 1, 1, 1)  # valuation needs only the last two bars per asset
    try:
        return value_portfolio(p, load_prices(data_dir, since), load_navs(data_dir, since))
    except (FileNotFoundError, MissingPrice) as e:
        raise HTTPException(
            503, f"market data not loaded; run app.services.market_data and nav_data ({e})"
        ) from e


@router.put("/{portfolio_id}/holdings")
def replace_holdings(
    portfolio_id: PortfolioId, holdings: Holdings, user: User, store: Store
) -> dict[str, str]:
    p = owned(store, user, portfolio_id)
    check_universe(holdings)
    store.save(user, p.model_copy(update={"holdings": holdings}))
    return {"portfolio_id": p.portfolio_id}
