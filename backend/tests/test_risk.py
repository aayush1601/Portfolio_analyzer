"""Every formula against a hand-computed example (NFR6). Working shown in comments."""

import numpy as np
import pandas as pd
import pytest

from app.analytics import risk

# r = 1%, -2%, 3%, -1%, 2%
R5 = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02])
CFG = {
    "version": "t",
    "components": {
        "volatility_ann": {"weight": 1, "low": 0.0, "high": 0.5},
        "hhi": {"weight": 3, "low": 0.0, "high": 1.0},
    },
    "bands": {"Low": 33, "Moderate": 66, "High": 100},
    "drawdown_window_days": 300,
    "holding_period": {"history_days": 300, "horizons": {"1 month": 21}, "bad_case_quantile": 0.05},
}


def test_max_drawdown():
    # wealth 1, 1.01, 0.9898, 1.0195, 1.0093, 1.0295 → worst fall 1.01 → 0.9898 = -2%
    assert risk.max_drawdown(R5) == pytest.approx(-0.02)


def test_historical_var_and_cvar():
    # sorted -0.02, -0.01, 0.01, 0.02, 0.03; 20% quantile (linear) at position 0.8 → -0.02 + 0.8·0.01 = -0.012
    assert risk.var_historical(R5, 0.80) == pytest.approx(0.012)
    # days with r ≤ -0.012: only -0.02
    assert risk.cvar_historical(R5, 0.80) == pytest.approx(0.02)


def test_parametric_var():
    # mean 0.006; sample sd = sqrt(0.00172 / 4) = 0.0207364; z(5%) = -1.6448536
    # VaR = -(0.006 - 1.6448536 · 0.0207364) = 0.0281082
    assert risk.var_parametric(R5, 0.95) == pytest.approx(0.0281082, abs=1e-6)


def test_beta():
    # market = 2·r → cov(r, 2r) / var(2r) = 2σ² / 4σ² = 0.5
    assert risk.beta(R5, 2 * R5) == pytest.approx(0.5)


def test_hhi():
    # risky weights 0.3, 0.1 → renormalised 0.75, 0.25 → 0.5625 + 0.0625
    assert risk.hhi(pd.Series([0.3, 0.1])) == pytest.approx(0.625)


def test_diversification_ratio_uncorrelated_equal_vol_is_sqrt2():
    R = pd.DataFrame({"a": [0.01, -0.01, 0.01, -0.01], "b": [0.01, 0.01, -0.01, -0.01]})  # corr 0, same σ
    assert risk.diversification_ratio(R, pd.Series({"a": 0.5, "b": 0.5})) == pytest.approx(np.sqrt(2))


def test_risk_score_is_clipped_weighted_mean():
    # vol 1.0 is above high → 100; hhi 0.0 → 0; weights 1:3 → (100·1 + 0·3) / 4 = 25 → Low
    assert risk.risk_score({"volatility_ann": 1.0, "hhi": 0.0}, CFG) == (25, "Low")
    # vol 0.25 → 50; hhi 0.6 → 60 → (50 + 180) / 4 = 57.5 → 58 → Moderate
    assert risk.risk_score({"volatility_ann": 0.25, "hhi": 0.6}, CFG) == (58, "Moderate")


def test_monte_carlo_var_is_seeded_and_near_parametric_for_normal_data():
    rng = np.random.default_rng(1)
    R = pd.DataFrame(rng.normal(0.0005, 0.01, (2000, 2)), columns=["a", "b"])
    w = pd.Series({"a": 0.6, "b": 0.4})
    mc = risk.var_monte_carlo(R, w, 0.95)
    assert mc == risk.var_monte_carlo(R, w, 0.95)
    assert mc == pytest.approx(risk.var_parametric(R @ w, 0.95), rel=0.05)


def report(R, weights, **kw):
    args = dict(
        lookback=252, confidence=0.95, rf=None, cfg={**CFG, "components": {"hhi": CFG["components"]["hhi"]}}
    )
    return risk.risk_report(R, pd.Series(weights), R["a"], **(args | kw))


def test_risk_report_end_to_end():
    rng = np.random.default_rng(2)
    idx = pd.bdate_range("2025-01-01", periods=300)
    R = pd.DataFrame(rng.normal(0, 0.01, (300, 2)), index=idx, columns=["a", "b"])
    r = report(R, {"a": 0.5, "b": 0.3}, rf=0.06)  # 20% cash
    window = R.tail(252)
    port = window @ pd.Series({"a": 0.5, "b": 0.3})
    assert r.observations == 252 and r.as_of == idx[-1].date()
    assert r.volatility_ann == pytest.approx(port.std() * np.sqrt(252))
    assert r.sharpe == pytest.approx((port.mean() * 252 - 0.06) / r.volatility_ann)
    assert r.beta == pytest.approx(port.cov(window["a"]) / window["a"].var())
    assert r.hhi_direct == pytest.approx(0.625**2 + 0.375**2)
    assert r.notes == []
    assert sum(r.return_histogram.counts) == 252 and len(r.return_histogram.edges) == 41


def test_risk_report_notes_and_errors():
    idx = pd.bdate_range("2025-01-01", periods=100)
    R = pd.DataFrame({"a": np.tile([0.01, -0.01], 50), "b": np.nan}, index=idx)
    R.loc[idx[40:], "b"] = np.tile([0.02, -0.01], 30)  # b listed later: 60 overlapping days
    r = report(R, {"a": 0.5, "b": 0.5})
    assert r.observations == 60
    assert len(r.notes) == 4  # shortened lookback, short scoring window, b stood in for, unset risk-free rate
    with pytest.raises(ValueError, match="no risky assets"):
        report(R, {})
    with pytest.raises(ValueError, match="overlapping history"):
        report(R.tail(20), {"a": 1.0})


def test_holding_period_stats_hand_computed():
    # daily log returns N(0.0004, 0.01), 252 days → N(0.1008, 0.0100·√252 = 0.158745)
    p, median, bad = risk.holding_period_stats(0.0004, 0.01, 252)
    assert p == pytest.approx(0.2627, abs=1e-4)  # Φ(−0.1008 / 0.158745) = Φ(−0.63498)
    assert median == pytest.approx(np.expm1(0.1008))  # 10.61%
    assert bad == pytest.approx(np.expm1(0.1008 - 1.6448536 * 0.158745), abs=1e-6)  # −14.81%


def test_time_diversification_cuts_both_ways():
    up = [risk.holding_period_stats(0.0004, 0.01, h) for h in (21, 252, 1260)]
    assert up[0][0] > up[1][0] > up[2][0]  # positive drift: a loss gets less likely the longer you hold
    assert up[0][2] > up[1][2]  # but a 1-year bad case is a bigger loss than a 1-month one
    down = [risk.holding_period_stats(-0.0004, 0.01, h)[0] for h in (21, 252, 1260)]
    assert down[0] < down[1] < down[2]  # negative drift: holding longer makes a loss more likely


def test_observed_holding_windows():
    r = pd.Series([0.1, -0.05, 0.1, -0.05])
    p, bad, n = risk.observed_holding(r, 2)
    # every 2-day window: 1.1 × 0.95 − 1 = 4.5%, so none ended down
    assert (p, n) == (0.0, 3) and bad == pytest.approx(0.045)
    assert risk.observed_holding(r, 3) == (None, None, 0)  # needs 2h days


def test_score_drawdown_uses_the_fixed_window_not_the_chosen_one():
    idx = pd.bdate_range("2024-01-01", periods=300)
    a = np.r_[np.full(10, -0.05), np.tile([0.002, -0.001], 145)]  # crash early, gently up since
    R = pd.DataFrame({"a": a}, index=idx)
    r = report(R, {"a": 1.0}, lookback=60)
    assert r.max_drawdown > -0.01  # the last 60 days look calm
    assert r.score_drawdown == pytest.approx(0.95**10 - 1, abs=1e-6)  # the score still sees the crash
    assert r.score_drawdown_days == 300


def test_young_asset_does_not_shorten_the_score_drawdown_window():
    idx = pd.bdate_range("2024-01-01", periods=300)
    old = np.r_[np.full(10, -0.05), np.tile([0.002, -0.001], 145)]  # crash early, gently up since
    young = np.r_[np.full(200, np.nan), np.tile([0.001, -0.001], 50)]  # launched after the crash
    r = report(pd.DataFrame({"a": old, "b": young}, index=idx), {"a": 0.5, "b": 0.5}, lookback=60)
    assert r.score_drawdown_days == 300  # not cut to b's 100 days
    assert r.score_drawdown == pytest.approx(0.95**10 - 1, abs=1e-6)  # a stands in for b during the crash
    assert any("started later" in n for n in r.notes)
