"""Portfolio engine (Phase 3): valuation, weights, P/L. Pure functions over price/NAV frames, no I/O."""

from datetime import date

import pandas as pd

from app.models.portfolio import (
    AssetType,
    HoldingValue,
    Portfolio,
    PortfolioSnapshot,
    ValueHistory,
    ValuePoint,
)


class MissingPrice(LookupError):
    pass


def last_two(
    df: pd.DataFrame, key: str, col: str, as_of: date
) -> dict[str, tuple[date, float, float | None]]:
    """Per asset: (date of latest value ≤ as_of, latest value, previous value or None).

    Expects df sorted by date (read() does this).
    """
    recent = df[df["date"] <= pd.Timestamp(as_of)].groupby(key).tail(2)
    out = {}
    for k, g in recent.groupby(key):
        vals = g[col].tolist()
        out[str(k)] = (g["date"].iloc[-1].date(), vals[-1], vals[-2] if len(vals) > 1 else None)
    return out


def value_portfolio(
    p: Portfolio, prices: pd.DataFrame, navs: pd.DataFrame, as_of: date | None = None
) -> PortfolioSnapshot:
    """Mark holdings to market at as_of (default: latest trading day in `prices`).

    Stocks use `close` (Yahoo's close is split-adjusted, so avg_cost must be in today's share terms);
    funds use NAV; cash is valued at 1. daily_pl counts only assets priced on as_of itself, so a NAV
    that is not yet published for as_of contributes 0 instead of yesterday's move.
    """
    as_of = as_of or prices["date"].max().date()
    quotes = {
        AssetType.STOCK: last_two(prices, "symbol", "close", as_of),
        AssetType.MF: last_two(navs, "scheme_code", "nav", as_of),
    }
    rows = []
    for h in p.holdings:
        if h.asset_type is AssetType.CASH:
            price_date, price, prev = None, 1.0, None
        elif (q := quotes[h.asset_type].get(h.asset_id)) is None:
            raise MissingPrice(f"no price for {h.asset_type}:{h.asset_id} on or before {as_of}")
        else:
            price_date, price, prev = q
        value = h.quantity * price
        rows.append(
            dict(
                **h.model_dump(),
                price=price,
                price_date=price_date,
                value=value,
                pl=0.0 if h.asset_type is AssetType.CASH else value - h.quantity * h.avg_cost,
                daily_pl=h.quantity * (price - prev) if prev is not None and price_date == as_of else 0.0,
            )
        )

    total = sum(r["value"] for r in rows)
    holdings = [
        HoldingValue(
            **{
                **r,
                "value": round(r["value"], 2),
                "pl": round(r["pl"], 2),
                "daily_pl": round(r["daily_pl"], 2),
            },
            weight=round(r["value"] / total, 6) if total else 0.0,
        )
        for r in rows
    ]
    return PortfolioSnapshot(
        portfolio_id=p.portfolio_id,
        as_of=as_of,
        total_value=round(total, 2),
        daily_pl=round(sum(r["daily_pl"] for r in rows), 2),
        total_pl=round(sum(r["pl"] for r in rows), 2),
        holdings=holdings,
    )


def value_history(p: Portfolio, prices: pd.DataFrame, navs: pd.DataFrame, since: date) -> ValueHistory:
    """Value of today's quantities on every trading day since `since` (stock closes; fund NAVs carried
    forward over days without a NAV; cash constant). Days before an asset's first price are skipped."""
    px = prices.pivot(index="date", columns="symbol", values="close").sort_index()
    px = px[px.index >= pd.Timestamp(since)]
    nav = navs.pivot(index="date", columns="scheme_code", values="nav").reindex(px.index).ffill(limit=5)
    total = pd.Series(0.0, index=px.index)
    cash = invested = 0.0
    for h in p.holdings:
        if h.asset_type is AssetType.CASH:
            cash += h.quantity
            invested += h.quantity
            continue
        series = (px if h.asset_type is AssetType.STOCK else nav).get(h.asset_id)
        if series is None:
            raise MissingPrice(f"no price history for {h.asset_type}:{h.asset_id}")
        total = total + h.quantity * series
        invested += h.quantity * h.avg_cost
    total = (total + cash).dropna()
    return ValueHistory(
        portfolio_id=p.portfolio_id,
        invested=round(invested, 2),
        points=[ValuePoint(date=d.date(), value=round(v, 2)) for d, v in total.items()],
    )
