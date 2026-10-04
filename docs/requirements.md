# Requirements

> Academic decision-support and research system. Recommendations are hypothetical, generated from data, explained, and evaluated by historical backtesting. They are **not** personalised financial advice, and the system does not guarantee profit.

## Research question
Does incorporating near-real-time financial news sentiment into multi-asset (look-through) portfolio risk analysis improve risk-adjusted portfolio performance compared with traditional analysis and optimisation?

Sub-questions RQ1–RQ4 are in [00_PROJECT_PLAN.md §2](00_PROJECT_PLAN.md).

## Functional requirements
| ID | Requirement | Phase |
|---|---|---|
| FR1 | User can register and log in (local stub first, Cognito later) | 1, 17 |
| FR2 | User can create a portfolio of NSE stocks (symbol, qty, avg cost), mutual funds (scheme code, units, avg NAV) and cash | 3 |
| FR3 | System values the portfolio daily: weights, daily P/L, total P/L, allocation | 3 |
| FR4 | System computes direct and **effective (look-through)** company and sector exposure, and fund overlap | 5 |
| FR5 | System computes returns, volatility, Sharpe, Sortino, max drawdown, VaR (historical, parametric, Monte Carlo), CVaR, beta, correlation, HHI, diversification, and a 0–100 risk score with configurable weights | 4 |
| FR6 | System ingests news, deduplicates it, maps it to tickers/sectors, scores it with FinBERT, and computes exposure-weighted portfolio impact | 6–8 |
| FR7 | System produces BUY/HOLD/REDUCE (stocks) and INCREASE/HOLD/REDUCE/SWITCH (funds), each with written reasons | 11 |
| FR8 | System runs stress scenarios through effective exposure | 4, 5 |
| FR9 | System runs backtests and ablations, and stores reproducible results | 12 |
| FR10 | System sends alerts when thresholds are breached (risk, drawdown, high-impact negative news) | 15, 17 |
| FR11 | Fund analytics: NAV history, 1D/1M/3M/6M returns, 1Y/3Y/5Y CAGR, volatility, Sharpe, MDD, VaR, beta, expense ratio, AUM, category, holdings, sector mix | 5 |

## Non-functional requirements
| ID | Requirement |
|---|---|
| NFR1 | Freshness: prices at most 1 trading day old (daily mode); news processed within 30 min of ingestion. Always described as **near-real-time**, never "real-time" |
| NFR2 | Read endpoints p95 < 1 s (results are precomputed) |
| NFR3 | Dev cost under US$5/month, enforced by an AWS Budget alarm |
| NFR4 | Per-user data isolation, no secrets in Git, least-privilege IAM |
| NFR5 | Every backtest is reproducible from a config file plus a data snapshot |
| NFR6 | Every financial formula has a unit test against a hand-computed example |
| NFR7 | Point-in-time correctness: every record carries `available_at`; no feature may use data with `available_at > t` |

## Out of scope
Real-money or automated trading, HFT, Kubernetes, Kafka, reinforcement learning, LLM-made buy/sell decisions, price-level prediction, blockchain.

## Constraints
- Single student developer, ~16 weeks, ~12–15 h/week.
- Free or free-tier data sources only (see [data_sources.md](data_sources.md)).
- Research universe fixed in [`config/universe.yaml`](../config/universe.yaml): NIFTY 50 stocks + 15 Direct-Growth equity funds from 6 AMCs.
