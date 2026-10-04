# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
- **Primary: evaluators.** Faculty and examiners who judge the project in live demos and through the written report. They need to see the method, the evidence and the honest result fast, without already knowing portfolio theory or the codebase.
- **Primary: the researcher (single student developer).** Uses the UI to inspect portfolios, check intermediate outputs (exposure, risk, sentiment, recommendations) and produce figures for the report.
- Retail investors are the *modelled* user the system reasons about, not the audience the UI is designed for.

## Product Purpose
Portfolio Intelligence is an academic decision-support and research system for Indian multi-asset portfolios (NSE stocks, mutual funds, cash). It values a portfolio, looks through mutual funds into their underlying stocks to get *effective* company and sector exposure, measures risk, scores financial news with FinBERT and weights its impact by that effective exposure, estimates expected returns with explainable ML, optimises the allocation under constraints, and issues explained recommendations. Backtests and an ablation study then test whether it actually helps.

It exists to answer one research question: does adding near-real-time news sentiment to look-through portfolio risk analysis improve risk-adjusted performance compared with traditional analysis and optimisation? Success means evaluators can follow the full chain from holdings to recommendation to backtest evidence and trust the answer, even if that answer is "no significant improvement".

## Positioning
- **Look-through exposure:** direct holdings and fund holdings are combined into one effective exposure. A user who owns only IT funds is still shown as exposed to TCS.
- **Exposure-weighted news impact:** news is scored against the user's effective exposure, not just against tickers the user holds directly.
- **Honest evaluation:** results come from leakage-safe walk-forward backtests and ablations, and a null result is reported as a valid outcome.

It is a portfolio intelligence and risk platform built around a research question. It is not a stock-price predictor or a trading tool.

## Operating Context
- Shown in live demos on a classroom projector.
- Screens are captured as static figures in the written report, so they must read well in print and PDF.
- The researcher uses it day to day during development to inspect pipeline outputs.
- Planned views: Overview, Portfolio, Risk, Funds, News, Recommendations, Backtest, Stress.

## Capabilities and Constraints
- **Stack:** React + TypeScript + Vite + Tailwind v4 (Recharts planned for charts). FastAPI backend behind `/api`. Planned AWS hosting: S3 + CloudFront, with API Gateway + Lambda behind them.
- **Portfolios:** seeded, realistic demo portfolios are available, and users can also enter their own holdings. Stocks are entered as symbol, quantity and average cost; mutual funds as scheme code, units and average NAV; plus cash.
- **Research universe:** NIFTY 50 stocks plus 15 Direct-Growth equity funds from 6 AMCs (`config/universe.yaml`).
- **Recommendation vocabulary:** stocks get BUY / HOLD / REDUCE; funds get INCREASE / HOLD / REDUCE / SWITCH. Every recommendation carries written reasons drawn from SHAP, risk, news and exposure.
- **Risk metrics:** volatility, Sharpe, Sortino, max drawdown, VaR (historical, parametric, Monte Carlo), CVaR, beta, correlation, HHI, diversification, and a 0–100 risk score.
- **Terminology:** always say "near-real-time", never "real-time". Data freshness is at most 1 trading day for prices, and news is processed within 30 minutes of ingestion.
- **Out of scope:** real-money or automated trading, HFT, and LLM-made buy/sell decisions.

## Brand Commitments
- Name: **Portfolio Intelligence**. No logo, palette or voice has been committed yet.
- A disclaimer is mandatory wherever recommendations appear: academic decision-support only, recommendations are hypothetical, not financial advice, no guaranteed profit.

## Evidence on Hand
- Real market, NAV and fund-holdings data from free sources (`docs/data_sources.md`).
- Real archived RSS news (`data/raw/news/rss/`).
- Backtest and ablation results do not exist yet. Never fabricate performance numbers, Sharpe improvements or outcomes. Show placeholder or empty states until real results land.
- No testimonials, users or deployments exist, and none may be invented.

## Product Principles
1. **Show the chain, not just the verdict.** Every recommendation should trace back to the exposure, risk, news and model evidence behind it.
2. **Effective exposure is the hero idea.** The gap between direct and look-through exposure is what this product offers that others don't.
3. **Honesty over salesmanship.** Hedge claims accurately, keep disclaimers present without shouting them, and give null results the same clarity as wins.
4. **Legible from the back of the room and on paper.** Every screen must survive a projector and a static report figure.

## Accessibility & Inclusion
- **Projector-safe:** information must not depend on subtle contrast or thin strokes.
- **Print-safe:** charts and states must stay distinguishable in static, possibly greyscale, report figures. Never rely on colour alone, for example red vs green for gains and losses.
