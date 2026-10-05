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
    assert r["INFY"].blocked_action == "BUY"


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


def test_model_prediction_is_shown_but_not_weighted():
    import json

    preds = pd.DataFrame(
        [
            {
                "symbol": "ITC",
                "horizon": 20,
                "pct": 0.9,
                "shap_top": json.dumps([{"feature": "ret_20d", "value": 0.05, "shap": 0.01}]),
            },
            {"symbol": "ITC", "horizon": 5, "pct": 0.1, "shap_top": "[]"},
        ]
    )
    s = snap({"ITC": ("STOCK", 0.05), "INR": ("CASH", 0.95)})
    exp = effective_exposure("p", s.as_of, {"ITC": 0.05}, {}, NO_HOLDINGS, SECTORS)
    empty = pd.DataFrame(columns=["symbol", "articles", "weight", "decayed_score"])
    with_model = recommend(s, exp, NO_HOLDINGS, pd.DataFrame(), empty, [], CFG, preds)
    without = recommend(s, exp, NO_HOLDINGS, pd.DataFrame(), empty, [], CFG)
    r = with_model.items[0]
    assert r.components["expected_return"] == 90  # 20-day horizon percentile
    assert r.shap_top[0]["feature"] == "ret_20d"
    assert any("20-day return (up)" in x for x in r.reasons)
    assert r.final_score == without.items[0].final_score  # weight 0: information only
    assert "information only" in with_model.notes[0]


def allocation(items, objective="min_variance"):
    from app.models.allocation import AllocationItem, AllocationReport, Stats

    rows = [
        AllocationItem(
            asset_id=a, asset_type=t, current=c, target=g, change=g - c, change_inr=(g - c) * 100_000
        )
        for a, t, c, g in items
    ]
    return AllocationReport(
        portfolio_id="p", as_of=date(2026, 10, 1), objective=objective, config_version="t",
        current=Stats(expected_return=0, volatility=0.1), target=Stats(expected_return=0, volatility=0.08),
        cash_current=0.0, cash_target=0.05, items=rows, sectors=[], binding=[], turnover=0.1, notes=[],
    )  # fmt: skip


CFG_FULL = {
    **CFG,
    "weights": {
        "expected_return": 0.0,
        "news": 0.20,
        "risk": 0.20,
        "portfolio_fit": 0.25,
        "allocation": 0.35,
    },
    "allocation_gap_scale": 0.10,
    "add_min_target": 0.03,
}


def run_full(weights, alloc, holdings=NO_HOLDINGS, funds_meta=()):
    s = snap(weights)
    direct = {a: w for a, (t, w) in weights.items() if t == "STOCK"}
    funds = {a: w for a, (t, w) in weights.items() if t == "MF"}
    exp = effective_exposure("p", s.as_of, direct, funds, holdings, SECTORS)
    sent = pd.DataFrame(columns=["symbol", "articles", "weight", "decayed_score"])
    return recommend(s, exp, holdings, pd.DataFrame(), sent, list(funds_meta), CFG_FULL, None, alloc)


def test_allocation_gap_enters_the_score():
    r = run_full({"ITC": ("STOCK", 0.05), "INR": ("CASH", 0.95)}, allocation([("ITC", "STOCK", 0.05, 0.0)]))
    i = r.items[0]
    # gap −0.05 / scale 0.10 → 50 − 25 = 25; news 50 (no news); fit 66.67; no risk data
    assert i.components["allocation"] == 25
    # (0.20·50 + 0.25·66.67 + 0.35·25) / 0.80 = 44.27
    assert i.final_score == pytest.approx(44.3, abs=0.05)
    assert any("Model allocation (lowest-risk): 0.0% target vs 5.0% now" in x for x in i.reasons)


def test_model_allocation_switches_a_dropped_fund_to_a_same_category_peer():
    meta = [{"scheme_code": f, "category": "Large Cap"} for f in ("F1", "F3")]
    alloc = allocation([("F1", "MF", 1.0, 0.0), ("F3", "MF", 0.0, 0.2)])
    i = run_full({"F1": ("MF", 1.0)}, alloc, funds_meta=meta).items[0]
    assert (i.action, i.switch_to) == ("SWITCH", "F3")
    assert any("moves this money into F3" in x for x in i.reasons)


def test_unheld_model_picks_are_listed_as_additions():
    alloc = allocation(
        [("ITC", "STOCK", 0.05, 0.05), ("TCS", "STOCK", 0.0, 0.06), ("INFY", "STOCK", 0.0, 0.02)]
    )
    r = run_full({"ITC": ("STOCK", 0.05), "INR": ("CASH", 0.95)}, alloc)
    assert [a.asset_id for a in r.additions] == ["TCS"]  # INFY's 2% is under the 3% bar
    assert r.additions[0].amount_inr == pytest.approx(6_000)
    assert r.allocation_objective == "min_variance"
