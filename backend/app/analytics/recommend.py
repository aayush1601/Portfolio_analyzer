"""Recommendation engine, basic version (Phase 11). Weights, caps and thresholds: config/recommendations.yaml.

Each held asset gets 0-100 component scores (higher = more attractive), a weighted final score, an action from
thresholds, then safety rules on look-through exposure that can only make the action more cautious.
"""

import json

import numpy as np
import pandas as pd

from app.analytics.exposure import UNMAPPED, fund_overlap
from app.analytics.features import FEATURE_LABELS
from app.analytics.risk import TRADING_DAYS, score_component
from app.models.exposure import ExposureReport
from app.models.portfolio import AssetType, PortfolioSnapshot
from app.models.recommendation import Recommendation, RecommendationReport


def shrunk_sentiment(sent: pd.DataFrame, k: float) -> dict[str, tuple[float, int]]:
    """symbol → (decayed score shrunk toward 0 by evidence, article count). sent: ticker_sentiment(...)."""
    return {r.symbol: (r.decayed_score * r.weight / (r.weight + k), r.articles) for r in sent.itertuples()}


def fund_sentiment(hf: pd.DataFrame, s_eff: dict[str, tuple[float, int]]) -> float | None:
    """Holdings-weighted sentiment of a fund's universe stocks; None without a disclosure."""
    mapped = hf[hf["symbol"].notna()]
    if mapped.empty:
        return None
    return float(
        sum(r.weight * s_eff.get(r.symbol, (0.0, 0))[0] for r in mapped.itertuples()) / mapped["weight"].sum()
    )


def news_reason(score: float, articles: int) -> str:
    if not articles:
        return "No recent company news"
    tone = "positive" if score > 0.1 else "negative" if score < -0.1 else "mixed/neutral"
    return f"Recent news sentiment {tone} ({score:+.2f}, {articles} article{'s' * (articles != 1)})"


def recommend(
    snap: PortfolioSnapshot,
    exp: ExposureReport,
    holdings: pd.DataFrame,
    R: pd.DataFrame,
    sent: pd.DataFrame,
    funds_meta: list[dict],
    cfg: dict,
    predictions: pd.DataFrame | None = None,
) -> RecommendationReport:
    """holdings: latest disclosures for all universe funds; R: asset returns; sent: ticker_sentiment(...)."""
    caps, th = cfg["caps"], cfg["thresholds"]
    e_s = {c.symbol: c.effective for c in exp.companies}
    e_k = {s.sector: s.effective for s in exp.sectors if s.sector != UNMAPPED}
    sector_of = {c.symbol: c.sector for c in exp.companies}
    s_eff = shrunk_sentiment(sent, cfg["news_evidence_k"])
    isins = {f: g.groupby("isin")["weight"].sum() for f, g in holdings.groupby("scheme_code")}
    held_funds = [h.asset_id for h in snap.holdings if h.asset_type is AssetType.MF]
    category = {str(f["scheme_code"]): f["category"] for f in funds_meta}
    vol = R.tail(TRADING_DAYS).std() * np.sqrt(TRADING_DAYS)
    weight = {h.asset_id: h.weight for h in snap.holdings}
    # Phase 9 model output for the 20-day horizon: percentile rank and SHAP drivers per stock.
    model = {}
    if predictions is not None and len(predictions):
        p20 = predictions[predictions["horizon"] == 20]
        model = {r.symbol: (r.pct, json.loads(r.shap_top)) for r in p20.itertuples()}

    def max_overlap(f: str, others: list[str]) -> tuple[float, str | None]:
        pairs = [
            (fund_overlap(isins[f], isins[o]), o) for o in others if o != f and f in isins and o in isins
        ]
        return max(pairs, default=(0.0, None))

    items = []
    for h in snap.holdings:
        if h.asset_type is AssetType.CASH:
            continue
        a, reasons, constraints, switch_to = h.asset_id, [], [], None
        comp: dict[str, float | None] = {"expected_return": None}
        drivers: list[dict] = []
        if h.asset_type is AssetType.STOCK and a in model:
            pct_rank, drivers = model[a]
            comp["expected_return"] = 100 * pct_rank
            why = ", ".join(
                f"{FEATURE_LABELS.get(d['feature'], d['feature'])} ({'up' if d['shap'] > 0 else 'down'})"
                for d in drivers
            )
            reasons.append(
                f"Model ranks it above {pct_rank:.0%} of NIFTY 50 stocks for 20-day excess return; "
                f"drivers: {why}"
            )

        v = vol.get(a)
        comp["risk"] = None if v is None or pd.isna(v) else 100 - score_component(v, **cfg["risk_volatility"])
        if comp["risk"] is not None:
            reasons.append(f"Volatility {v:.0%} (1y, annualised)")

        if h.asset_type is AssetType.STOCK:
            score, n = s_eff.get(a, (0.0, 0))
            comp["news"] = 50 + 50 * score
            reasons.append(news_reason(score, n))
            es, sector = e_s.get(a, 0.0), sector_of.get(a, UNMAPPED)
            ek = e_k.get(sector, 0.0)
            comp["portfolio_fit"] = float(
                np.clip(100 * (1 - max(es / caps["company"], ek / caps["sector"])), 0, 100)
            )
        else:
            hf = holdings[holdings["scheme_code"] == a]
            fs = fund_sentiment(hf, s_eff)
            comp["news"] = None if fs is None else 50 + 50 * fs
            if fs is not None:
                reasons.append(f"Holdings-weighted news sentiment {fs:+.2f}")
            ov, with_fund = max_overlap(a, held_funds)
            comp["portfolio_fit"] = None if hf.empty else 100 * (1 - ov)
            if hf.empty:
                reasons.append("No holdings disclosure ingested: news and portfolio fit unavailable")
            elif with_fund:
                reasons.append(f"Overlaps {ov:.0%} with fund {with_fund}")

        w = cfg["weights"]
        avail = {k: c for k, c in comp.items() if c is not None and w[k] > 0}
        final = sum(w[k] * c for k, c in avail.items()) / sum(w[k] for k in avail) if avail else 50.0
        up = "BUY" if h.asset_type is AssetType.STOCK else "INCREASE"
        action = up if final >= th["buy"] else "REDUCE" if final <= th["reduce"] else "HOLD"
        if action == up and len(avail) < cfg["min_components_to_add"]:
            action = "HOLD"
            reasons.append(f"Not enough evidence to recommend adding (only {', '.join(avail) or 'no'} score)")

        proposed = action
        # Safety rules: look-through exposure can only make the action more cautious.
        if h.asset_type is AssetType.STOCK:
            if es > caps["company"]:
                action = "REDUCE"
                constraints.append("max_company_exposure")
                reasons.append(
                    f"Effective exposure {es:.1%} exceeds {caps['company']:.0%} single-company cap"
                )
            if ek > caps["sector"]:
                constraints.append("max_sector_exposure")
                reasons.append(f"{sector} effective exposure {ek:.1%} above {caps['sector']:.0%} cap")
                if action == up:
                    action = "HOLD"
        else:
            fund_syms = set(hf["symbol"].dropna())
            breached = sorted(
                {f"max_company_exposure:{s}" for s in fund_syms if e_s.get(s, 0) >= caps["company"]}
                | {
                    f"max_sector_exposure:{sector_of.get(s)}"
                    for s in fund_syms
                    if e_k.get(sector_of.get(s), 0) >= caps["sector"]
                }
            )
            if breached and action == up:
                action = "HOLD"
                constraints += breached
                reasons.append("Adding would raise exposure that is already at a cap")
            # Of two heavily overlapping funds, switch the smaller holding and keep the larger.
            if ov >= cfg["switch_overlap"] and (weight[with_fund], with_fund) > (h.weight, a):
                others = [f for f in held_funds if f != a]
                candidates = [
                    (max_overlap(c, others)[0], c)
                    for c in isins
                    if c not in held_funds and category.get(c) == category.get(a)
                ]
                best = min(candidates, default=None)
                if best and best[0] < ov:
                    action, switch_to = "SWITCH", best[1]
                    reasons.append(
                        f"Same-category fund {best[1]} overlaps only {best[0]:.0%} with your other funds"
                    )

        items.append(
            Recommendation(
                asset_id=a,
                asset_type=h.asset_type,
                action=action,
                final_score=round(final, 1),
                components={k: None if c is None else round(c, 1) for k, c in comp.items()},
                reasons=reasons,
                constraints_triggered=constraints,
                switch_to=switch_to,
                blocked_action=proposed if action not in (proposed, "SWITCH") else None,
                shap_top=drivers,
            )
        )
    w = cfg["weights"]
    notes = []
    if w["expected_return"] == 0:
        notes.append(
            "expected_return is shown for information only (weight 0): the Phase 9 model has no "
            "statistically significant skill yet (see docs/model_card.md)"
            if model
            else "expected_return needs the Phase 9 model: run app.services.ml"
        )
    return RecommendationReport(
        portfolio_id=snap.portfolio_id,
        as_of=pd.Timestamp.now(tz="UTC").to_pydatetime(),
        disclaimer=cfg["disclaimer"],
        config_version=cfg["version"],
        weights=cfg["weights"],
        items=sorted(items, key=lambda i: i.final_score),
        notes=notes + exp.notes,
    )
