"""Backtest and ablation runner (Phase 12): answers RQ3/RQ4 and stores reproducible results (FR9, NFR5).

  uv run python -m app.services.backtest        (from backend/; ~1 minute)

Strategies (config/backtest.yaml) run over the research universe with monthly rebalancing and trading costs.
Each run writes data/backtests/<run_id>/{results.json, returns.parquet, config.yaml}; the CLI also refreshes
docs/backtest_report.md from the run.
"""

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import yaml

from app.analytics import backtest as bt
from app.analytics.exposure import latest_holdings
from app.analytics.optimizer import lookthrough_matrix, optimize, shrunk_cov, shrunk_mu
from app.analytics.recommend import shrunk_sentiment
from app.analytics.risk import asset_returns
from app.analytics.sentiment import ticker_sentiment
from app.config import REPO_ROOT, get_settings
from app.services.fund_holdings import load_holdings
from app.services.market_data import load_prices
from app.services.nav_data import load_navs

log = logging.getLogger(__name__)
CLOSE_IST = pd.Timedelta(hours=15, minutes=30)
TESTS = [  # (strategy, compared with, the question it answers)
    ("B_min_variance", "A_equal_weight", "RQ4: does the risk layer help?"),
    ("C_mean_variance", "B_min_variance", "RQ4: do return estimates help beyond risk?"),
    ("D_news_aware_mv", "C_mean_variance", "RQ3: does news help the optimiser?"),
    ("D_news_aware_mv", "buy_and_hold", "RQ3: news-aware optimiser vs buy and hold"),
    ("C_mean_variance", "buy_and_hold", "RQ3: plain mean-variance vs buy and hold"),
    ("D_news_aware_mv", "benchmark", "News-aware optimiser vs the NIFTY 50"),
]


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def run_dir(data_dir: Path, run_id: str) -> Path:
    return data_dir / "backtests" / run_id


def news_scores(data_dir: Path) -> pd.DataFrame:
    from app.services.sentiment import news_with_sentiment

    try:
        return news_with_sentiment(data_dir)
    except FileNotFoundError:
        return pd.DataFrame(columns=["published_at", "symbols", "score", "confidence"])


def run(overrides: dict | None = None, run_id: str | None = None) -> dict:
    s = get_settings()
    cfg = {**read_yaml(s.config_dir / "backtest.yaml"), **(overrides or {})}
    opt = read_yaml(s.config_dir / "optimizer.yaml")
    rec = read_yaml(s.config_dir / "recommendations.yaml")
    u = read_yaml(s.config_dir / "universe.yaml")
    run_id = run_id or datetime.now(UTC).strftime("bt_%Y%m%d_%H%M%S")
    out = run_dir(s.data_dir, run_id)
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    (out / "results.json").write_text(json.dumps({"run_id": run_id, "status": "RUNNING"}))

    prices, navs = load_prices(s.data_dir), load_navs(s.data_dir)
    stocks = {x["symbol"] for x in u["stocks"]}
    sector_of = {x["symbol"]: x["sector"] for x in u["stocks"]}
    universe = sorted(stocks | {str(f["scheme_code"]) for f in u["mutual_funds"]})
    R_all = asset_returns(prices, navs)
    R = R_all[[c for c in universe if c in R_all.columns]]
    market, vix = R_all[cfg["benchmark"]], R_all["^INDIAVIX"]
    end = pd.Timestamp(cfg["end"]) if cfg.get("end") else R.index[-1]
    rebal = [t for t in bt.month_ends(R.index) if pd.Timestamp(cfg["start"]) <= t < end]
    holdings = load_holdings(s.data_dir)
    news = news_scores(s.data_dir)
    news_hits: dict[pd.Timestamp, int] = {}

    def investable(t: pd.Timestamp) -> pd.DataFrame:
        hist = R.loc[:t].tail(cfg["lookback_days"])
        cover = hist.notna().mean()
        return hist[cover[cover >= cfg["min_history_share"]].index].dropna()

    def sentiment_at(t: pd.Timestamp) -> pd.Series:
        as_of = (t + CLOSE_IST).tz_localize("Asia/Kolkata").tz_convert("UTC")
        sent = ticker_sentiment(news, as_of.to_pydatetime(), cfg["news_half_life_hours"])
        s_eff = shrunk_sentiment(sent, rec["news_evidence_k"])
        news_hits[t] = sum(1 for v, n in s_eff.values() if n and abs(v) > 1e-9)
        return pd.Series({k: v for k, (v, _) in s_eff.items()}, dtype=float)

    def weights_fn(spec: dict):
        def at(t: pd.Timestamp) -> pd.Series:
            hist = investable(t)
            if spec["kind"] in ("equal_weight", "buy_and_hold"):
                return pd.Series(1 / hist.shape[1], index=hist.columns)
            mu, Sigma = shrunk_mu(hist, opt["mu_shrinkage"]), shrunk_cov(hist, opt["cov_shrinkage"])
            if spec.get("news"):
                mu = mu.add(cfg["news_tilt"] * sentiment_at(t), fill_value=0).reindex(mu.index)
            H, _ = lookthrough_matrix(list(hist.columns), stocks, latest_holdings(holdings, t.date()))
            w, _ = optimize(
                mu,
                Sigma,
                H,
                sector_of,
                risk_aversion=opt["objectives"][spec["objective"]]["risk_aversion"],
                max_asset=opt["max_asset_weight"],
                cash_floor=cfg["cash_floor"],
                caps=rec["caps"],
            )
            return w

        return at

    sims = {}
    for name, spec in cfg["strategies"].items():
        sims[name] = bt.simulate(
            R, rebal, weights_fn(spec), cfg["cost_bps"], end, rebalance=spec["kind"] != "buy_and_hold"
        )
        log.info("strategy done", extra={"fields": {"strategy": name, "days": len(sims[name])}})
    days = sims[next(iter(sims))].index
    returns = pd.DataFrame({n: s["ret"] for n, s in sims.items()}).reindex(days)
    returns["benchmark"] = market.reindex(days).fillna(0.0)

    metrics = {n: bt.metrics(returns[n], sims[n]["turnover"] if n in sims else None) for n in returns.columns}
    b = cfg["bootstrap"]
    tests = [
        {"strategy": a, "versus": v, "question": q, **bt.sharpe_difference_test(returns[a], returns[v], b["resamples"], b["block_days"], b["seed"])}
        for a, v, q in TESTS
        if a in returns and v in returns
    ]  # fmt: skip
    labels = bt.regimes(market, vix, days)
    regime_rows = []
    for dim in ("trend", "volatility"):
        for label, idx in labels.groupby(dim).groups.items():
            sub = returns.loc[idx]
            regime_rows.append(
                {"dimension": dim, "regime": label, "days": len(sub), **{n: float(bt.sharpe(sub[n].to_numpy())) for n in returns.columns}}
            )  # fmt: skip
    wealth = (1 + returns).cumprod()
    monthly = wealth.groupby([wealth.index.year, wealth.index.month]).tail(1)
    news_rebalances = sum(1 for n in news_hits.values() if n)

    fingerprint = hashlib.sha256(
        json.dumps(
            [str(prices["date"].max()), len(prices), len(navs), len(news), cfg, opt, rec["caps"]], default=str
        ).encode()
    ).hexdigest()[:16]
    results = {
        "run_id": run_id,
        "status": "DONE",
        "created_at": datetime.now(UTC).isoformat(),
        "config": cfg,
        "data_fingerprint": fingerprint,
        "period": {"start": str(days[0].date()), "end": str(days[-1].date()), "rebalances": len(rebal)},
        "metrics": metrics,
        "tests": tests,
        "regimes": regime_rows,
        "news_coverage": {"rebalances_with_news": news_rebalances, "rebalances": len(news_hits)},
        "equity": {
            "dates": [str(d.date()) for d in monthly.index],
            **{n: monthly[n].round(5).tolist() for n in monthly.columns},
        },
    }
    returns.to_parquet(out / "returns.parquet")
    (out / "results.json").write_text(json.dumps(results, indent=2, default=float))
    log.info("backtest done", extra={"fields": {"run_id": run_id, "fingerprint": fingerprint}})
    return results


def load_run(data_dir: Path, run_id: str) -> dict | None:
    f = run_dir(data_dir, run_id) / "results.json"
    return json.loads(f.read_text()) if f.exists() else None


def list_runs(data_dir: Path) -> list[dict]:
    root = data_dir / "backtests"
    runs = (
        [load_run(data_dir, p.name) for p in sorted(root.glob("bt_*"), reverse=True)] if root.exists() else []
    )
    return [
        {k: r.get(k) for k in ("run_id", "status", "created_at", "period", "data_fingerprint")}
        for r in runs
        if r
    ]


NAMES = {
    "A_equal_weight": "A · Equal weight",
    "B_min_variance": "B · + Risk (min variance)",
    "C_mean_variance": "C · + Returns (mean-variance)",
    "D_news_aware_mv": "D · + News (news-aware)",
    "buy_and_hold": "Buy and hold",
    "benchmark": "NIFTY 50",
}


def report(results: dict) -> str:
    m = results["metrics"]
    rows = "\n".join(
        f"| {NAMES.get(n, n)} | {v['cagr']:.1%} | {v['volatility']:.1%} | {v['sharpe']:.2f} | {v['sortino']:.2f} | "
        f"{v['max_drawdown']:.1%} | {v['calmar']:.2f} | {v['cvar_95']:.2%} | {v['turnover']:.2f} |"
        for n, v in m.items()
    )
    tests = "\n".join(
        f"| {NAMES.get(t['strategy'])} vs {NAMES.get(t['versus'])} | {t['question']} | {t['sharpe_diff']:+.2f} | "
        f"[{t['ci_low']:+.2f}, {t['ci_high']:+.2f}] | {t['p_value']:.3f} |"
        for t in results["tests"]
    )
    cols = list(m)
    regimes = "\n".join(
        f"| {r['regime']} | {r['days']} | " + " | ".join(f"{r[c]:.2f}" for c in cols) + " |"
        for r in results["regimes"]
    )
    nc = results["news_coverage"]
    c = results["config"]
    return f"""# Backtest report (Phase 12)

_Generated by `app.services.backtest` from run `{results["run_id"]}` (data fingerprint `{results["data_fingerprint"]}`).
Re-run to refresh; do not edit by hand. Research output, not financial advice._

**Period:** {results["period"]["start"]} to {results["period"]["end"]}, {results["period"]["rebalances"]} monthly rebalances.
**Universe:** 50 NIFTY stocks + 15 research funds. **Costs:** {c["cost_bps"]} bps on every rupee traded.
**Estimates:** point-in-time, {c["lookback_days"]} trading days of returns before each rebalance.

## Performance
| Strategy | CAGR | Volatility | Sharpe | Sortino | Max drawdown | Calmar | CVaR 95% (1d) | Turnover / yr |
|---|---|---|---|---|---|---|---|---|
{rows}

## Is the difference real? (stationary block bootstrap, {c["bootstrap"]["resamples"]} resamples, {c["bootstrap"]["block_days"]}-day blocks)
One-sided test of H1: the first strategy has the higher Sharpe ratio. p < 0.05 would be significant.

| Comparison | Question | Sharpe difference | 95% interval | p-value |
|---|---|---|---|---|
{tests}

## RQ3 caveat: news coverage
The news layer had evidence on **{nc["rebalances_with_news"]} of {nc["rebalances"]}** rebalances. Without historical news the
news-aware strategy (D) is the mean-variance strategy (C), so D vs C cannot answer RQ3 yet. It becomes
answerable once a historical news source is backfilled (ADR 0001) or enough RSS history accumulates.

## Sharpe ratio by regime (RQ4)
| Regime | Days | {" | ".join(NAMES.get(x, x) for x in cols)} |
|---|---|{"---|" * len(cols)}
{regimes}

## Limitations
- Survivorship bias: today's NIFTY 50 constituents and today's funds are used throughout, which flatters results.
- Fund look-through is limited to funds with ingested disclosures; others are capped only per asset.
- Costs are a flat estimate; no taxes (STCG/LTCG), exit loads or market impact beyond it.
- Regimes are labelled with the full-sample VIX median: a descriptive split, not a tradable signal.
"""


def main() -> None:
    from app.utils.log import setup_logging

    setup_logging(get_settings().log_level)
    results = run()
    (REPO_ROOT / "docs" / "backtest_report.md").write_text(report(results))
    for n, v in results["metrics"].items():
        print(
            f"{NAMES.get(n, n):32s} CAGR {v['cagr']:6.1%}  vol {v['volatility']:5.1%}  Sharpe {v['sharpe']:5.2f}  MDD {v['max_drawdown']:6.1%}  turnover {v['turnover']:5.2f}"
        )
    for t in results["tests"]:
        print(f"  {t['strategy']} vs {t['versus']}: ΔSharpe {t['sharpe_diff']:+.2f}  p={t['p_value']:.3f}")
    print("news coverage:", results["news_coverage"])


if __name__ == "__main__":
    main()
