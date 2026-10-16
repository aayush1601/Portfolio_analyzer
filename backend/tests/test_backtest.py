"""Backtest engine checks with hand-computed numbers."""

import numpy as np
import pandas as pd
import pytest

from app.analytics import backtest as bt

D = pd.bdate_range("2026-01-05", periods=5)  # d0 … d4
R = pd.DataFrame({"a": [0.0, 0.10, 0.10, 0.10, 0.10], "b": 0.0}, index=D)
HALF = pd.Series({"a": 0.5, "b": 0.5})


def test_simulate_drift_rebalance_and_costs():
    out = bt.simulate(R, [D[0], D[2]], lambda t: HALF, cost_bps=10, end=D[-1])
    # d1: 0.5·10% = 5%, minus 10 bps on 100% bought from cash
    assert out.loc[D[1], "ret"] == pytest.approx(0.05 - 0.001)
    # weights drift: a = 0.5·1.1/1.05 = 0.52381 → d2 return 5.2381%
    assert out.loc[D[2], "ret"] == pytest.approx(0.5 * 1.1 / 1.05 * 0.10)
    # rebalance at d2's close: a drifted to 0.54752; trade back to 50/50 → Σ|Δw| = 0.09504
    wa = 0.5 * 1.1 / 1.05 * 1.1 / (1 + 0.5 * 1.1 / 1.05 * 0.10)
    traded = 2 * (wa - 0.5)
    assert out.loc[D[3], "turnover"] == pytest.approx(traded)
    assert out.loc[D[3], "ret"] == pytest.approx(0.05 - traded * 0.001)


def test_buy_and_hold_never_trades_again():
    out = bt.simulate(R, [D[0], D[2]], lambda t: HALF, cost_bps=10, end=D[-1], rebalance=False)
    assert out["turnover"].tolist() == [1.0, 0, 0, 0]
    # value of a grows 1.1^k, b stays: portfolio wealth = 0.5·1.1^k + 0.5 (before the one-off cost)
    assert (1 + out["ret"].iloc[1:]).prod() == pytest.approx((0.5 * 1.1**4 + 0.5) / (0.5 * 1.1 + 0.5))


def test_metrics():
    r = pd.Series([0.01, -0.01] * 126)  # one year, zero mean
    m = bt.metrics(r)
    assert m["sharpe"] == pytest.approx(0.0, abs=1e-12)
    # +1%/−1% loses ~0.01% per pair, so the trough is the last day: (1.01·0.99)^126 / 1.01 − 1 = −2.23%
    assert m["max_drawdown"] == pytest.approx((1.01 * 0.99) ** 126 / 1.01 - 1)
    assert m["cagr"] == pytest.approx((1.01 * 0.99) ** 126 - 1)
    assert m["volatility"] == pytest.approx(r.std() * np.sqrt(252))


def test_sharpe_difference_test():
    rng = np.random.default_rng(3)
    b = pd.Series(rng.normal(0.0002, 0.01, 1000))
    better = bt.sharpe_difference_test(b + 0.001, b, 500, 21, 0)
    assert better["sharpe_diff"] > 0 and better["p_value"] == 0.0  # same blocks: a always beats b
    same = bt.sharpe_difference_test(b, b, 500, 21, 0)
    assert same["sharpe_diff"] == 0 and same["p_value"] == 1.0


def test_bootstrap_indices_and_month_ends():
    idx = bt.stationary_bootstrap_indices(50, 20, 5, 0)
    assert idx.shape == (20, 50) and idx.min() >= 0 and idx.max() < 50
    steps = np.diff(idx, axis=1)
    assert ((steps == 1) | (steps == -49)).mean() > 0.6  # mostly consecutive (blocks of mean length 5)
    dates = pd.bdate_range("2026-01-28", "2026-03-04")
    assert bt.month_ends(dates).strftime("%m-%d").tolist() == ["01-30", "02-27", "03-04"]


def test_backtest_routes_read_stored_runs(tmp_path, monkeypatch):
    import json

    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        run = tmp_path / "backtests" / "bt_20261005_120000"
        run.mkdir(parents=True)
        (run / "results.json").write_text(json.dumps({"run_id": run.name, "status": "DONE", "metrics": {}}))
        c = TestClient(app)
        assert [r["run_id"] for r in c.get("/backtest").json()] == [run.name]
        assert c.get(f"/backtest/{run.name}").json()["status"] == "DONE"
        assert c.get("/backtest/bt_20000101_000000").status_code == 404
        assert c.get("/backtest/..%2Fsecrets").status_code in (404, 422)
        assert c.post("/backtest", json={"cost_bps": 999}).status_code == 422
    finally:
        get_settings.cache_clear()


def test_gross_returns_add_back_exactly_the_cost_charged():
    out = bt.simulate(R, [D[0], D[2]], lambda t: HALF, cost_bps=10, end=D[-1])
    free = bt.simulate(R, [D[0], D[2]], lambda t: HALF, cost_bps=0, end=D[-1])
    pd.testing.assert_series_equal(
        bt.gross_returns(out["ret"], out["turnover"], 10), free["ret"], check_names=False
    )


def test_news_window_starts_at_first_rebalance_with_evidence():
    hits = {D[0]: 0, D[1]: 0, D[2]: 3, D[3]: 0, D[4]: 1}
    assert bt.first_covered(hits) == D[2]
    assert bt.first_covered({D[0]: 0}) is None


def test_report_news_section_with_and_without_a_window():
    from app.services.backtest import news_section

    base = {"news_coverage": {"rebalances_with_news": 0, "rebalances": 10}}
    assert "cannot be answered" in news_section({**base, "news_window": None})

    m = {"cagr": 0.1, "volatility": 0.2, "sharpe": 0.5, "max_drawdown": -0.3, "turnover": 2.0}
    t = {"sharpe_diff": -0.02, "ci_low": -0.3, "ci_high": 0.2, "p_value": 0.6}
    w = {
        "start": "2022-01-03",
        "end": "2026-10-15",
        "rebalances": 57,
        "rebalances_with_news": 57,
        "metrics": {"C_mean_variance": m, "D_news_aware_mv": m},
        "gross": {"C_mean_variance": m, "D_news_aware_mv": m},
        "tests": [{"basis": "after costs", **t}, {"basis": "before costs", **t}],
        "sensitivity": [{"news_tilt": 0.1, "sharpe": 0.5, "sharpe_gross": 0.6, "cagr": 0.1, "turnover": 2.0}],
    }
    text = news_section({"news_coverage": {"rebalances_with_news": 57, "rebalances": 105}, "news_window": w})
    assert "57 of 105" in text and "D vs C, before costs" in text and "| 0.10 | 0.50 | 0.60 |" in text
