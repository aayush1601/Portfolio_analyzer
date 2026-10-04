"""Look-through exposure (Phase 5), stress and fund analytics. Formulas: docs/algorithms/exposure.md."""

from datetime import date
from itertools import combinations

import numpy as np
import pandas as pd

from app.analytics import risk
from app.models.exposure import (
    CompanyExposure,
    ExposureReport,
    FundAnalytics,
    FundHolding,
    FundOverlap,
    FundRisk,
    IndustryWeight,
    SectorExposure,
    StressContributor,
    StressResult,
    Via,
)

UNMAPPED = "Other/Unmapped"


def latest_holdings(h: pd.DataFrame, t: date) -> pd.DataFrame:
    """Point-in-time: per fund, the latest disclosure already published at t (published_at ≤ t)."""
    h = h[h["published_at"] <= t]
    return h[h["as_of_month"] == h.groupby("scheme_code")["as_of_month"].transform("max")]


def effective_exposure(
    portfolio_id: str,
    as_of: date,
    direct: dict[str, float],
    funds: dict[str, float],
    holdings: pd.DataFrame,
    sectors: dict[str, str],
) -> ExposureReport:
    """direct: stock weights; funds: fund weights; holdings: latest_holdings(...) rows."""
    contrib, unmapped, notes, months, fund_isins = [], 0.0, [], {}, {}
    for f, wf in funds.items():
        hf = holdings[holdings["scheme_code"] == f]
        if hf.empty:
            unmapped += wf
            notes.append(f"no holdings disclosure for fund {f}; its {wf:.1%} counts as {UNMAPPED}")
            continue
        months[f] = hf["as_of_month"].iloc[0]
        fund_isins[f] = hf.groupby("isin")["weight"].sum()
        mapped = hf[hf["symbol"].notna()].groupby("symbol")["weight"].sum()
        contrib += [(s, f, wf * h) for s, h in mapped.items()]
        unmapped += wf * max(0.0, 1 - mapped.sum())
    via = pd.DataFrame(contrib, columns=["symbol", "fund", "contribution"])

    companies = []
    for s in set(direct) | set(via["symbol"]):
        v = via[via["symbol"] == s]
        d, i = direct.get(s, 0.0), float(v["contribution"].sum())
        companies.append(
            CompanyExposure(
                symbol=s,
                sector=sectors.get(s, UNMAPPED),
                direct=round(d, 6),
                indirect=round(i, 6),
                effective=round(d + i, 6),
                via=[Via(fund=r.fund, contribution=round(r.contribution, 6)) for r in v.itertuples()],
            )
        )
    companies.sort(key=lambda c: -c.effective)

    by_sector: dict[str, list[float]] = {}
    for c in companies:
        acc = by_sector.setdefault(c.sector, [0.0, 0.0])
        acc[0] += c.direct
        acc[1] += c.effective
    if unmapped:
        by_sector.setdefault(UNMAPPED, [0.0, 0.0])[1] += unmapped
    sector_list = [
        SectorExposure(sector=k, direct=round(d, 6), effective=round(e, 6)) for k, (d, e) in by_sector.items()
    ]
    sector_list.sort(key=lambda s: -s.effective)

    overlap = [
        FundOverlap(
            fund_a=a,
            fund_b=b,
            overlap=round(float(np.minimum(*fund_isins[a].align(fund_isins[b], fill_value=0)).sum()), 6),
        )
        for a, b in combinations(sorted(fund_isins), 2)
    ]
    hhi = sum(c.effective**2 for c in companies)
    return ExposureReport(
        portfolio_id=portfolio_id,
        as_of=as_of,
        holdings_as_of=months,
        companies=companies,
        sectors=sector_list,
        overlap=overlap,
        unmapped=round(unmapped, 6),
        hhi_effective=round(hhi, 6),
        n_effective=round(1 / hhi, 2) if hhi else None,
        notes=notes,
    )


def stress(exp: ExposureReport, shocks: dict[str, float], total_value: float, scenario: str) -> StressResult:
    """Linear shock on effective sector exposure: loss = Σ_k E_k · shock_k."""
    loss = sum(s.effective * shocks.get(s.sector, 0.0) for s in exp.sectors)
    per_company = [(c.symbol, c.effective * shocks.get(c.sector, 0.0)) for c in exp.companies]
    if shocks.get(UNMAPPED):
        per_company.append((UNMAPPED, exp.unmapped * shocks[UNMAPPED]))
    top = sorted((p for p in per_company if p[1]), key=lambda p: p[1])[:5]
    return StressResult(
        scenario=scenario,
        estimated_loss=round(loss, 6),
        estimated_loss_inr=round(loss * total_value, 2),
        top_contributors=[StressContributor(symbol=s, loss=round(v, 6)) for s, v in top],
    )


def fund_analytics(
    meta: dict, nav: pd.Series, market: pd.Series, rf: float | None, holdings: pd.DataFrame
) -> FundAnalytics:
    """meta: the fund's universe.yaml entry; nav: date-indexed NAV; holdings: its latest disclosure."""
    notes = []
    as_of = nav.index[-1]

    def since(offset: pd.DateOffset, years: int | None = None) -> float | None:
        base = nav[: as_of - offset]
        if base.empty:
            return None
        ratio = nav.iloc[-1] / base.iloc[-1]
        return float(ratio ** (1 / years) - 1 if years else ratio - 1)

    r = nav.pct_change().dropna().tail(risk.TRADING_DAYS)
    vol = float(r.std() * np.sqrt(risk.TRADING_DAYS))
    if rf is None:
        notes.append("risk-free rate not set in config/universe.yaml; Sharpe uses 0")
    if holdings.empty:
        notes.append("no holdings disclosure ingested yet for this fund")
    for key in ("expense_ratio", "aum"):
        if meta.get(key) is None:
            notes.append(f"{key} not available from free sources; set it in config/universe.yaml")
    mix = holdings.groupby("industry")["weight"].sum().sort_values(ascending=False)
    return FundAnalytics(
        scheme_code=str(meta["scheme_code"]),
        name=meta["name"],
        amc=meta["amc"],
        category=meta["category"],
        as_of=as_of.date(),
        nav=float(nav.iloc[-1]),
        returns={
            "1d": float(r.iloc[-1]) if len(r) else None,
            "1m": since(pd.DateOffset(months=1)),
            "3m": since(pd.DateOffset(months=3)),
            "6m": since(pd.DateOffset(months=6)),
            "cagr_1y": since(pd.DateOffset(years=1), 1),
            "cagr_3y": since(pd.DateOffset(years=3), 3),
            "cagr_5y": since(pd.DateOffset(years=5), 5),
        },
        risk=FundRisk(
            volatility_ann=vol,
            sharpe=(float(r.mean() * risk.TRADING_DAYS) - (rf or 0.0)) / vol if vol else 0.0,
            max_drawdown=risk.max_drawdown(r),
            var_1d=risk.var_historical(r, 0.95),
            beta=risk.beta(r, market),
        ),
        expense_ratio=meta.get("expense_ratio"),
        aum=meta.get("aum"),
        holdings_as_of=holdings["as_of_month"].iloc[0] if len(holdings) else None,
        top_holdings=[
            FundHolding(
                isin=h.isin,
                symbol=h.symbol if isinstance(h.symbol, str) else None,
                name=h.name,
                weight=h.weight,
            )
            for h in holdings.sort_values("weight", ascending=False).head(10).itertuples()
        ],
        sector_mix=[IndustryWeight(industry=str(k), weight=round(float(v), 6)) for k, v in mix.items()],
        notes=notes,
    )
