"""Mutual fund analytics route (FR11)."""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from app.analytics.exposure import fund_analytics, latest_holdings
from app.api.portfolio import load_market, read_config
from app.config import get_settings
from app.models.exposure import FundAnalytics
from app.services.fund_holdings import load_holdings
from app.services.market_data import returns

router = APIRouter(prefix="/mutual-funds", tags=["mutual funds"])


@router.get("/{scheme_code}")
def get_fund(scheme_code: str) -> FundAnalytics:
    u = read_config("universe.yaml")
    meta = next((f for f in u["mutual_funds"] if str(f["scheme_code"]) == scheme_code), None)
    if meta is None:
        raise HTTPException(404, "fund not in the research universe")
    prices, navs = load_market(date.today() - timedelta(days=5 * 366 + 30))  # enough for 5Y CAGR
    nav = navs[navs["scheme_code"] == scheme_code].set_index("date")["nav"]
    if nav.empty:
        raise HTTPException(503, "no NAVs for this fund; run app.services.nav_data")
    holdings = latest_holdings(load_holdings(get_settings().data_dir), date.today())
    return fund_analytics(
        meta,
        nav,
        returns(prices)["^NSEI"],
        u["risk_free"]["annual_rate"],
        holdings[holdings["scheme_code"] == scheme_code],
    )
