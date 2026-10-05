"""Expected-return models (Phase 9). Needs the `ml` dependency group (scikit-learn, xgboost, shap).

  uv run --group ml python -m app.services.ml      (from backend/)

1. Builds point-in-time features and 5d/20d forward-return targets (app.analytics.features).
2. Walk-forward evaluation, one test year at a time with a purge gap: historical mean, ridge regression,
   random forest and XGBoost, each with market-only and market+news features (RQ2).
3. Fits the final XGBoost per horizon on all labelled data, predicts the latest date, explains with SHAP.

Writes data/processed/{ml_metrics.json, predictions.parquet}, models/xgb_<h>d.json and docs/model_card.md.
Models rank stocks: the target is the forward return minus that date's cross-sectional mean.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from app.analytics.evaluation import demean_by_date, summarise, walk_forward_splits
from app.analytics.features import HORIZONS, MARKET_FEATURES, NEWS_FEATURES, build_dataset
from app.config import REPO_ROOT, get_settings
from app.services.market_data import load_prices

log = logging.getLogger(__name__)
FIRST_TEST_YEAR = 2019
MIN_NEWS_DATES = 60  # below this the news ablation is reported as not yet answerable
FEATURE_SETS = {"market": MARKET_FEATURES, "market+news": MARKET_FEATURES + NEWS_FEATURES}


def make_model(name: str):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from xgboost import XGBRegressor

    return {
        "ridge": lambda: make_pipeline(StandardScaler(), Ridge(alpha=10.0)),
        "random_forest": lambda: RandomForestRegressor(
            n_estimators=150, max_depth=8, min_samples_leaf=100, max_features=0.5, n_jobs=-1, random_state=0
        ),
        "xgboost": lambda: XGBRegressor(
            n_estimators=300, max_depth=4, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8,
            min_child_weight=50, n_jobs=-1, random_state=0,
        ),
    }[name]()  # fmt: skip


def prepare(ds: pd.DataFrame) -> pd.DataFrame:
    ds = ds.dropna(subset=MARKET_FEATURES).copy()
    for h in HORIZONS:
        ds[f"y_{h}d"] = demean_by_date(ds, f"fwd_{h}d")
    # Baseline "model": a stock's own average daily return over the past year, scaled to the horizon.
    mean_252 = ds.groupby("symbol")["ret_1d"].transform(lambda s: s.rolling(252, min_periods=120).mean())
    ds["hist_mean"] = mean_252
    return ds


def walk_forward(ds: pd.DataFrame, horizon: int, features: list[str]) -> pd.DataFrame:
    """Out-of-sample predictions for every test year, one column per model."""
    y = f"y_{horizon}d"
    labelled = ds.dropna(subset=[y])
    years = list(range(FIRST_TEST_YEAR, labelled["date"].max().year + 1))
    out = []
    for train_dates, test_dates in walk_forward_splits(pd.DatetimeIndex(labelled["date"]), years, horizon):
        train = labelled[labelled["date"].isin(train_dates)]
        test = labelled[labelled["date"].isin(test_dates)].copy()
        test["hist_mean"] = test["hist_mean"] * horizon - (test["hist_mean"] * horizon).groupby(
            test["date"]
        ).transform("mean")
        for name in ("ridge", "random_forest", "xgboost"):
            m = make_model(name).fit(train[features], train[y])
            test[name] = m.predict(test[features])
        out.append(test[["date", "symbol", y, "hist_mean", "ridge", "random_forest", "xgboost"]])
        log.info(
            "fold done",
            extra={"fields": {"h": horizon, "test_year": int(test_dates[0].year), "train_rows": len(train)}},
        )
    return pd.concat(out, ignore_index=True)


def evaluate(ds: pd.DataFrame, news_start: pd.Timestamp | None) -> list[dict]:
    rows = []
    for h in HORIZONS:
        y = f"y_{h}d"
        for fs, feats in FEATURE_SETS.items():
            preds = walk_forward(ds, h, feats)
            for model in ("hist_mean", "ridge", "random_forest", "xgboost"):
                if model == "hist_mean" and fs != "market":
                    continue  # the baseline uses no features
                rows.append(
                    {
                        "horizon": h,
                        "features": fs,
                        "model": model,
                        "window": "all",
                        **summarise(preds, model, y, h),
                    }
                )
                if news_start is not None:
                    recent = preds[preds["date"] >= news_start]
                    rows.append(
                        {
                            "horizon": h,
                            "features": fs,
                            "model": model,
                            "window": "news era",
                            **summarise(recent, model, y, h),
                        }
                    )
    return rows


def fit_final_and_predict(ds: pd.DataFrame, models_dir: Path) -> pd.DataFrame:
    """XGBoost on market+news features per horizon; predict the latest date; top-3 SHAP drivers per stock."""
    import shap

    feats = FEATURE_SETS["market+news"]
    latest = ds[ds["date"] == ds["date"].max()]
    frames = []
    models_dir.mkdir(parents=True, exist_ok=True)
    for h in HORIZONS:
        train = ds.dropna(subset=[f"y_{h}d"])
        m = make_model("xgboost").fit(train[feats], train[f"y_{h}d"])
        m.save_model(models_dir / f"xgb_{h}d.json")
        pred = m.predict(latest[feats])
        sv = shap.TreeExplainer(m).shap_values(latest[feats])
        drivers = []
        for row_sv, row_x in zip(sv, latest[feats].to_numpy(), strict=True):
            top = np.argsort(-np.abs(row_sv))[:3]
            drivers.append(
                json.dumps(
                    [{"feature": feats[i], "value": float(row_x[i]), "shap": float(row_sv[i])} for i in top]
                )
            )
        frames.append(
            pd.DataFrame(
                {
                    "symbol": latest["symbol"].to_numpy(),
                    "date": latest["date"].to_numpy(),
                    "horizon": h,
                    "pred": pred,
                    "pct": pd.Series(pred).rank(pct=True).to_numpy(),
                    "shap_top": drivers,
                    "model": f"xgboost_{h}d",
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def model_card(metrics: list[dict], info: dict) -> str:
    def table(window: str) -> str:
        rows = [m for m in metrics if m["window"] == window]
        lines = [
            "| Horizon | Features | Model | Rank IC | IC t-stat | Hit rate | IC > 0 | Dates |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for m in rows:
            lines.append(
                f"| {m['horizon']}d | {m['features']} | {m['model']} | {m['rank_ic']:.4f} | {m['ic_tstat']:.2f} | "
                f"{m['hit_rate']:.3f} | {m['ic_positive_share']:.2f} | {m['dates']} |"
            )
        return "\n".join(lines)

    news_section = (
        table("news era")
        if info["news_dates"] >= MIN_NEWS_DATES
        else f"Not answerable yet: news history covers only {info['news_dates']} trading days "
        f"(since {info['news_start']}); at least {MIN_NEWS_DATES} are needed. Market+news rows in the table above "
        "are effectively market-only because news features are zero before collection began."
    )
    return f"""# Model card: expected-return models (Phase 9)

_Generated by `app.services.ml` on {info["generated"]}. Re-run to refresh; do not edit by hand._

## Purpose
Rank the NIFTY 50 universe by expected {", ".join(f"{h}" for h in HORIZONS)}-day return relative to the cross-sectional average,
as one input (`expected_return`) to the recommendation engine. Research output, not financial advice.

## Data
- Prices: NSE daily closes (Yahoo, split- and dividend-adjusted) {info["price_start"]} to {info["price_end"]}; {info["rows"]:,} labelled stock-days.
- News: FinBERT-scored RSS headlines from {info["news_start"]} ({info["news_dates"]} trading days with any news).
- Universe: today's NIFTY 50 constituents (survivorship bias: backtests are flattered; see universe.yaml).

## Features (point-in-time, known by 15:30 IST on the feature date)
Market: {", ".join(MARKET_FEATURES)}.
News: {", ".join(NEWS_FEATURES)} (articles published after the close count toward the next trading day).

## Target
Forward return over h trading days minus that date's mean across the universe (what a ranking can earn).

## Method
Expanding-window walk-forward, one test year at a time from {FIRST_TEST_YEAR}, with an h-day purge gap before each
test year. Models: historical mean (baseline), ridge regression, random forest, XGBoost. Metrics: mean daily
rank IC (Spearman), its t-stat on non-overlapping dates (every h-th), hit rate (sign of predicted vs realised
excess return), share of dates with positive IC.

## Results: all test years
{table("all")}

## RQ2: does news help? (test dates since news collection began)
{news_section}

## Limitations
- News history is short; RQ2 cannot be answered until enough news has accumulated (see ADR 0001 for backfill).
- Survivorship bias from using today's constituents; no transaction costs in these forecast metrics.
- Hit rate is measured on excess returns, so 0.5 is the no-skill level.
- Hyperparameters are fixed defaults, not tuned, to avoid fitting the test years.
"""


def main() -> None:
    from app.services.sentiment import news_with_sentiment
    from app.utils.log import setup_logging

    settings = get_settings()
    setup_logging(settings.log_level)
    prices = load_prices(settings.data_dir)
    try:
        news = news_with_sentiment(settings.data_dir)
    except FileNotFoundError:
        news = pd.DataFrame()
    ds = prepare(build_dataset(prices, news))
    has_news = ds[ds["news_count_7d"] > 0]
    news_start = has_news["date"].min() if len(has_news) else None
    metrics = evaluate(ds, news_start)

    out = settings.data_dir / "processed"
    (out / "ml_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    preds = fit_final_and_predict(ds, REPO_ROOT / "models")
    preds.to_parquet(out / "predictions.parquet", index=False)

    info = {
        "generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "price_start": str(prices["date"].min().date()),
        "price_end": str(prices["date"].max().date()),
        "rows": int(ds["y_20d"].notna().sum()),
        "news_start": str(news_start.date()) if news_start is not None else "n/a",
        "news_dates": int(has_news["date"].nunique()),
    }
    (REPO_ROOT / "docs" / "model_card.md").write_text(model_card(metrics, info))
    log.info("ml done", extra={"fields": info})


if __name__ == "__main__":
    main()
