# ADR 0001: News sources

- **Status:** Accepted for live news (RSS). Historical news: option (b), decided in [ADR 0003](0003-historical-news-gdelt.md)
- **Date:** 2026-10-04

## Context
The research question needs **timestamped, company-level news for Indian stocks** for the backtest test period, plus a live feed for the app. Spike findings ([data_sources.md](../data_sources.md)):
- RSS (ET, Moneycontrol, Livemint) works and is India-focused, but has no history.
- GDELT DOC works and covers Indian publishers, but it is heavily rate-limited and only searches a recent rolling window.
- Alpha Vantage NEWS_SENTIMENT is untested (no key yet), and its coverage of Indian tickers is unknown.

## Decision
1. **Start archiving now.** Collect RSS every 30 min from 2026-10-04 onward (GDELT goes in a later step). Store raw items with `published_at` and `ingested_at`. This collector is the first piece of code in Phase 1/2.
2. **Live pipeline:** RSS (primary) + Alpha Vantage (if the spike shows coverage) → the same `NewsItem` schema. We use our own FinBERT scores, not the vendor's sentiment.
3. **Historical backtest news:** decide by the Alpha Vantage result.
   - (a) If AV returns ≥ ~100 articles per name since 2022 for most of the top-25 names → AV is the historical source and the universe stays Indian.
   - (b) Otherwise → backfill from GDELT raw/BigQuery data for 2022–2025 (more work, still Indian).
   - (c) Last resort → run the *research experiment* on a US universe (well covered by AV), while the app stays Indian. Report this as a limitation.

## Consequences
- The news test period for the backtest may be shorter than the price test period. The ablation (A–D) must run on the window where news exists.
- Every news record keeps both `published_at` (publisher) and `ingested_at` (us). Backtests use `published_at` with a delay buffer, and live decisions use `ingested_at`.
- Source reliability weights (needed by the impact score) start as a config table per domain.
