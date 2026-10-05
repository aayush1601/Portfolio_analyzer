from datetime import UTC, date, datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.analytics.portfolio import MissingPrice, value_portfolio
from app.api import portfolio as api
from app.config import get_settings
from app.main import app
from app.models.portfolio import Portfolio
from app.services.market_data import save

D1, D2 = pd.Timestamp("2026-09-30"), pd.Timestamp("2026-10-01")
PRICES = pd.DataFrame(
    {"date": [D1, D2, D1, D2], "symbol": ["TCS", "TCS", "INFY", "INFY"], "close": [100.0, 110.0, 50.0, 45.0]}
)
NAVS = pd.DataFrame({"date": [D1], "scheme_code": ["120594"], "nav": [20.0]})  # NAV for D2 not published yet


def make(holdings):
    return Portfolio(portfolio_id="abc123abc123", name="t", created_at=datetime.now(UTC), holdings=holdings)


def test_valuation_hand_computed():
    p = make(
        [
            {"asset_type": "STOCK", "asset_id": "TCS", "quantity": 10, "avg_cost": 80},
            {"asset_type": "STOCK", "asset_id": "INFY", "quantity": 20, "avg_cost": 50},
            {"asset_type": "MF", "asset_id": "120594", "quantity": 50, "avg_cost": 10},
            {"asset_type": "CASH", "asset_id": "INR", "quantity": 1000},
        ]
    )
    s = value_portfolio(p, PRICES, NAVS)
    # values: TCS 1100, INFY 900, MF 1000, cash 1000 → total 4000
    assert s.as_of == date(2026, 10, 1)
    assert s.total_value == 4000
    assert [h.weight for h in s.holdings] == [0.275, 0.225, 0.25, 0.25]
    assert [h.pl for h in s.holdings] == [300, -100, 500, 0]
    assert s.total_pl == 700
    # TCS +100, INFY -100; MF NAV is from D1 (stale), so it adds 0 rather than yesterday's move
    assert [h.daily_pl for h in s.holdings] == [100, -100, 0, 0]
    assert s.holdings[2].price_date == date(2026, 9, 30)


def test_valuation_as_of_and_missing_price():
    s = value_portfolio(
        make([{"asset_type": "STOCK", "asset_id": "TCS", "quantity": 1}]), PRICES, NAVS, date(2026, 9, 30)
    )
    assert s.total_value == 100 and s.daily_pl == 0  # no earlier bar
    with pytest.raises(MissingPrice):
        value_portfolio(make([{"asset_type": "STOCK", "asset_id": "ITC", "quantity": 1}]), PRICES, NAVS)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    api.get_store.cache_clear()
    save(
        PRICES.assign(symbol=PRICES["symbol"].replace({"INFY": "HDFCBANK"})),
        tmp_path / "processed" / "market" / "prices",
    )
    save(NAVS, tmp_path / "processed" / "nav")
    yield TestClient(app)
    get_settings.cache_clear()
    api.get_store.cache_clear()


def test_new_user_gets_demos_and_can_create_value_and_edit(client):
    assert {p["name"] for p in client.get("/portfolio").json()} == {
        "Demo: stocks + IT fund",
        "Demo: funds only",
    }

    body = {
        "name": "Mine",
        "holdings": [{"asset_type": "STOCK", "asset_id": "TCS", "quantity": 2, "avg_cost": 100}],
    }
    pid = client.post("/portfolio", json=body).json()["portfolio_id"]
    snap = client.get(f"/portfolio/{pid}").json()
    assert snap["total_value"] == 220 and snap["total_pl"] == 20 and snap["daily_pl"] == 20

    r = client.put(
        f"/portfolio/{pid}/holdings", json=[{"asset_type": "CASH", "asset_id": "INR", "quantity": 5}]
    )
    assert r.status_code == 200
    assert client.get(f"/portfolio/{pid}").json()["total_value"] == 5


@pytest.mark.parametrize(
    "holdings",
    [
        [{"asset_type": "STOCK", "asset_id": "NOPE", "quantity": 1}],  # not in universe
        [{"asset_type": "STOCK", "asset_id": "TCS", "quantity": 0}],  # quantity must be > 0
        [{"asset_type": "CASH", "asset_id": "USD", "quantity": 1}],
        [{"asset_type": "STOCK", "asset_id": "TCS", "quantity": 1}] * 2,  # duplicate
    ],
)
def test_bad_holdings_rejected(client, holdings):
    assert client.post("/portfolio", json={"name": "x", "holdings": holdings}).status_code == 422


def test_unknown_or_malformed_id(client):
    assert client.get("/portfolio/000000000000").status_code == 404
    assert client.get("/portfolio/..%2F..%2Fetc").status_code in (404, 422)


def test_missing_market_data_is_503(client, tmp_path):
    pid = client.get("/portfolio").json()[0]["portfolio_id"]  # demo holds RELIANCE etc., not in test prices
    assert client.get(f"/portfolio/{pid}").status_code == 503


def test_exposure_and_stress_without_disclosures(client):
    body = {
        "name": "x",
        "holdings": [
            {"asset_type": "STOCK", "asset_id": "TCS", "quantity": 1},
            {"asset_type": "MF", "asset_id": "120594", "quantity": 11},  # 110 + 220 = 330 total
        ],
    }
    pid = client.post("/portfolio", json=body).json()["portfolio_id"]
    e = client.get(f"/portfolio/{pid}/exposure").json()
    assert e["companies"][0]["symbol"] == "TCS"
    assert e["unmapped"] == pytest.approx(220 / 330, abs=1e-6)  # fund has no disclosure yet
    assert "120594" in e["notes"][0]

    r = client.post(f"/portfolio/{pid}/stress", json={"shocks": {"Information Technology": -0.1}})
    assert r.json()["estimated_loss_inr"] == pytest.approx(-11)
    assert client.post(f"/portfolio/{pid}/stress", json={"shocks": {"Nope": -0.1}}).status_code == 422
    assert (
        client.post(f"/portfolio/{pid}/stress", json={"shocks": {"Information Technology": -5}}).status_code
        == 422
    )


def test_fund_not_in_universe_is_404(client):
    assert client.get("/mutual-funds/1").status_code == 404


def test_reference_lists_universe_and_caps(client):
    r = client.get("/reference").json()
    assert len(r["stocks"]) == 50 and len(r["funds"]) == 15
    assert r["caps"] == {"company": 0.15, "sector": 0.25}


def test_value_history_marks_todays_quantities_to_past_prices():
    from app.analytics.portfolio import value_history

    p = make(
        [
            {"asset_type": "STOCK", "asset_id": "TCS", "quantity": 2, "avg_cost": 90},
            {"asset_type": "MF", "asset_id": "120594", "quantity": 10, "avg_cost": 15},
            {"asset_type": "CASH", "asset_id": "INR", "quantity": 100},
        ]
    )
    h = value_history(p, PRICES, NAVS, date(2026, 9, 1))
    # D1: 2·100 + 10·20 + 100 = 500; D2: NAV carried forward → 2·110 + 10·20 + 100 = 520
    assert [(x.date, x.value) for x in h.points] == [(date(2026, 9, 30), 500), (date(2026, 10, 1), 520)]
    assert h.invested == 2 * 90 + 10 * 15 + 100
