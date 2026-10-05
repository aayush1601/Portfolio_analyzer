"""Optimiser checks against closed-form answers."""

import numpy as np
import pandas as pd
import pytest

from app.analytics.optimizer import lookthrough_matrix, optimize, shrunk_cov, shrunk_mu

LOOSE = {"company": 1.0, "sector": 1.0}


def setup(var, mu=None, H=None, sector_of=None):
    assets = [f"S{i}" for i in range(len(var))]
    Sigma = pd.DataFrame(np.diag(var), index=assets, columns=assets)
    mu = pd.Series(mu if mu is not None else np.zeros(len(var)), index=assets)
    H = H if H is not None else pd.DataFrame(np.eye(len(var)), index=assets, columns=assets)
    sector_of = sector_of or {c: f"K{c}" for c in H.index}
    return mu, Sigma, H, sector_of


def test_min_variance_is_inverse_variance_for_uncorrelated_assets():
    # variances 0.04 and 0.01 → weights ∝ 25 : 100 → 0.2, 0.8
    w, binding = optimize(*setup([0.04, 0.01]), risk_aversion=None, max_asset=1, cash_floor=0, caps=LOOSE)
    assert w.round(4).tolist() == [0.2, 0.8] and binding == []


def test_balanced_matches_the_lagrange_solution():
    # maximise μ·w − λ/2 wᵀΣw, Σw = 1: 0.2 − 5·0.04·w1 = 0.1 − 5·0.04·w2 → w1 − w2 = 0.5 → 0.75, 0.25
    w, _ = optimize(
        *setup([0.04, 0.04], mu=[0.2, 0.1]), risk_aversion=5, max_asset=1, cash_floor=0, caps=LOOSE
    )
    assert w.round(4).tolist() == [0.75, 0.25]


def test_asset_cap_and_cash_floor_bind():
    w, binding = optimize(*setup([0.04, 0.01]), risk_aversion=None, max_asset=0.7, cash_floor=0.1, caps=LOOSE)
    assert w.sum() == pytest.approx(0.9)  # 10% cash floor
    assert w["S1"] == pytest.approx(0.7, abs=1e-6) and "max 70% per asset: S1" in binding


def test_company_cap_binds_through_a_fund():
    # stock A; fund F holding 50% A (the calmest asset); fund G with no disclosure (no look-through row).
    # Min variance wants mostly F, but A's effective exposure wA + 0.5·wF must stay ≤ 15%, so wF ≤ 0.3.
    assets = ["A", "F", "G"]
    H = pd.DataFrame([[1, 0.5, 0]], index=["A"], columns=assets, dtype=float)
    Sigma = pd.DataFrame(np.diag([0.04, 0.005, 0.04]), index=assets, columns=assets)
    mu = pd.Series(0.0, index=assets)
    caps = {"company": 0.15, "sector": 1.0}
    w, binding = optimize(mu, Sigma, H, {"A": "IT"}, risk_aversion=None, max_asset=1, cash_floor=0, caps=caps)
    assert w["A"] + 0.5 * w["F"] <= 0.15 + 1e-6
    assert "company cap: A" in binding
    # var(F=0.3, G=0.7) = 0.000450 + 0.0196 beats any mix that trades F for A
    assert w.round(3).tolist() == [0.0, 0.3, 0.7]


def test_caps_that_cannot_all_hold_are_reported():
    with pytest.raises(ValueError, match="no allocation can satisfy every cap"):
        optimize(
            *setup([0.04, 0.01]),
            risk_aversion=None,
            max_asset=1,
            cash_floor=0,
            caps={"company": 0.15, "sector": 1},
        )


def test_infeasible_budget_is_reported():
    with pytest.raises(ValueError, match="cannot fill"):
        optimize(*setup([0.04, 0.01]), risk_aversion=None, max_asset=0.3, cash_floor=0, caps=LOOSE)


def test_shrinkage_and_lookthrough_matrix():
    R = pd.DataFrame({"a": [0.01, 0.03, -0.01, 0.01], "b": [0.0, 0.0, 0.02, -0.02]})
    m = R.mean() * 252
    assert shrunk_mu(R, 0.5)["a"] == pytest.approx(0.5 * m["a"] + 0.5 * m.mean())
    C = shrunk_cov(R, 0.2)
    assert C.loc["a", "b"] == pytest.approx(0.8 * R.cov().loc["a", "b"] * 252)  # off-diagonal shrinks
    assert C.loc["a", "a"] == pytest.approx(R.var()["a"] * 252)  # diagonal unchanged
    holdings = pd.DataFrame({"scheme_code": ["F", "F"], "symbol": ["A", None], "weight": [0.4, 0.5]})
    H, unknown = lookthrough_matrix(["A", "F", "G"], {"A", "B"}, holdings)
    assert H.loc["A", "F"] == 0.4 and H.loc["A", "A"] == 1 and unknown == ["G"]
