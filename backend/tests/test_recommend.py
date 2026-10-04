from datetime import date

import pandas as pd
import pytest

from app.analytics.exposure import effective_exposure
from app.analytics.recommend import recommend
from app.models.portfolio import HoldingValue, PortfolioSnapshot

CFG = {
    "version": "t",
    "disclaimer": "d",
    "weights": {"expected_return": 0.0, "news": 0.35, "risk": 0.30, "portfolio_fit": 0.35},
    "thresholds": {"buy": 65, "reduce": 35},
    "caps": {"company": 0.15, "sector": 0.25},
    "risk_volatility": {"low": 0.10, "high": 0.50},
    "news_evidence_k": 1.0,
    "switch_overlap": 0.5,
    "min_components_to_add": 2,
}
SECTORS = {"TCS": "IT", "INFY": "IT", "ITC": "FMCG"}
COLS = ["scheme_code", "as_of_month", "published_at", "isin", "symbol", "weight"]
NO_HOLDINGS = pd.DataFrame(columns=COLS)


def snap(weights):
    hv = [
        HoldingValue(
            asset_type=t,
            asset_id=a,
            quantity=1,
            price=1,
            price_date=None,
            value=w,
            weight=w,
            pl=0,
            daily_pl=0,
        )
        for a, (t, w) in weights.items()
    ]
    return PortfolioSnapshot(
        portfolio_id="p", as_of=date(2026, 10, 1), total_value=1, daily_pl=0, total_pl=0, holdings=hv
    )


def run(weights, holdings=NO_HOLDINGS, sent=None, R=None, funds_meta=()):
    s = snap(weights)
    direct = {a: w for a, (t, w) in weights.items() if t == "STOCK"}
    funds = {a: w for a, (t, w) in weights.items() if t == "MF"}
    exp = effective_exposure("p", s.as_of, direct, funds, holdings, SECTORS)
    sent = (
        sent if sent is not None else pd.DataFrame(columns=["symbol", "articles", "weight", "decayed_score"])
    )
    R = R if R is not None else pd.DataFrame()
    return {i.asset_id: i for i in recommend(s, exp, holdings, R, sent, list(funds_meta), CFG).items}


def test_final_score_hand_computed():
    sent = pd.DataFrame([{"symbol": "ITC", "articles": 1, "weight": 1.0, "decayed_score": 0.5}])
    r = run({"ITC": ("STOCK", 0.05), "INR": ("CASH", 0.95)}, sent=sent)["ITC"]
    # news: 0.5 · 1/(1+1) = 0.25 → 62.5; fit: 1 − max(0.05/0.15, 0.05/0.25) = 2/3 → 66.67; no risk data
    # final = (0.35·62.5 + 0.35·66.67) / 0.70 = 64.58 → HOLD (below 65)
    assert r.components["news"] == 62.5 and r.components["risk"] is None
    assert r.final_score == pytest.approx(64.6) and r.action == "HOLD"


def test_company_cap_forces_reduce_and_sector_cap_blocks_buy():
    sent = pd.DataFrame(
        [{"symbol": s, "articles": 9, "weight": 99.0, "decayed_score": 1.0} for s in ("TCS", "INFY")]
    )
    R = pd.DataFrame({"TCS": [0.001, -0.001] * 50, "INFY": [0.001, -0.001] * 50})  # very low vol → risk 100
    CFG["thresholds"]["buy"] = 60  # fit is already 0 at the cap; a lower bar isolates the safety gate
    try:
        r = run({"TCS": ("STOCK", 0.2), "INFY": ("STOCK", 0.1), "INR": ("CASH", 0.7)}, sent=sent, R=R)
    finally:
        CFG["thresholds"]["buy"] = 65
    assert r["TCS"].action == "REDUCE"
    assert r["TCS"].constraints_triggered == ["max_company_exposure", "max_sector_exposure"]
    assert any("exceeds 15% single-company cap" in x for x in r["TCS"].reasons)
    # INFY scores high but IT is at 30% > 25%: BUY is downgraded to HOLD
    assert r["INFY"].final_score >= 60 and r["INFY"].action == "HOLD"
    assert r["INFY"].constraints_triggered == ["max_sector_exposure"]


def holdings(rows):
    return pd.DataFrame(
        [(f, "2026-08", date(2026, 9, 10), isin, None, w) for f, isin, w in rows], columns=COLS
    )


def test_switch_smaller_of_two_overlapping_funds_to_low_overlap_peer():
    h = holdings(
        [
            ("F1", "X", 0.3),
            ("F1", "Y", 0.3),
            ("F1", "Z", 0.4),
            ("F2", "X", 0.3),
            ("F2", "Y", 0.3),
            ("F2", "W", 0.4),  # 60% overlap with F1
            ("F3", "W", 0.1),
            ("F3", "V", 0.9),  # same category, not held: 0% with F1, 10% with F2
        ]
    )
    meta = [{"scheme_code": f, "category": "Large Cap"} for f in ("F1", "F2", "F3")]
    r = run({"F1": ("MF", 0.6), "F2": ("MF", 0.4)}, holdings=h, funds_meta=meta)
    assert r["F2"].action == "SWITCH" and r["F2"].switch_to == "F3"  # smaller holding switches
    assert r["F1"].action != "SWITCH"
    assert r["F1"].components["portfolio_fit"] == pytest.approx(40)


def test_single_component_cannot_justify_adding():
    R = pd.DataFrame({"F9": [0.001, -0.001] * 50})  # very low vol: risk 100, but nothing else known
    r = run({"F9": ("MF", 1.0)}, R=R)["F9"]
    assert r.final_score == 100 and r.action == "HOLD"
    assert "Not enough evidence" in r.reasons[-1]


def test_fund_without_disclosure_says_so():
    r = run({"F9": ("MF", 1.0)})["F9"]
    assert r.components["news"] is None and r.components["portfolio_fit"] is None
    assert r.final_score == 50 and r.action == "HOLD"
    assert "No holdings disclosure" in r.reasons[0]
