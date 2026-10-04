# Real-Time Cloud-Based Multi-Asset Portfolio Risk & Financial Intelligence System
### Master Project Plan (v0.1, 4 Oct 2026)

> Academic decision-support and research system. It produces data-driven, explainable portfolio recommendations and evaluates their historical risk-adjusted performance through backtesting. It does **not** guarantee profit, and its output is not personalised financial advice.

**Alternative title for the report** (same idea, a bit tighter):
*"News-Aware Look-Through Portfolio Intelligence: A Cloud-Native, Event-Driven System for Multi-Asset Risk Analysis and Explainable Recommendations"*

---

## 1. What we are building (my understanding)

A cloud-native platform where a user enters a portfolio of **Indian stocks, mutual funds and cash**. The system:

1. **Collects** prices, mutual-fund NAVs, fund metadata, fund holdings and financial news on a schedule (near-real-time, not HFT).
2. **Looks through** every mutual fund into its underlying stocks, so it knows the user's *effective* exposure to each company and sector (direct + indirect).
3. **Measures risk** at asset and portfolio level (volatility, Sharpe, drawdown, VaR/CVaR, beta, correlation, concentration, a 0–100 risk score).
4. **Reads the news** with FinBERT, maps each article to companies and sectors, and converts it into a **portfolio impact** that is weighted by the user's effective exposure.
5. **Estimates expected returns** with ML (baselines → XGBoost), explained with SHAP.
6. **Optimises** the allocation (mean-variance with asset/sector/cash constraints).
7. **Recommends** BUY / HOLD / REDUCE (stocks) and INCREASE / HOLD / REDUCE / SWITCH (funds), each with a written reason.
8. **Proves or disproves** its value via chronological backtests and an ablation study.

Its identity is a **portfolio intelligence and risk platform with a research question**, not a stock-price predictor.

---

## 2. Research question and contribution

**RQ:** Does incorporating near-real-time financial news sentiment into multi-asset (look-through) portfolio risk analysis improve risk-adjusted portfolio performance compared with traditional analysis and optimisation?

**Sub-questions (each maps to an experiment):**
- RQ1: How different is *effective* exposure from *direct* exposure for realistic retail portfolios? (descriptive; uses look-through engine)
- RQ2: Does adding news-sentiment features improve out-of-sample expected-return estimates (rank IC, hit rate) versus market-only features?
- RQ3: Does a news-aware optimiser improve Sharpe / Sortino / max drawdown / CVaR after transaction costs versus buy-and-hold and plain mean-variance?
- RQ4 (ablation): Which layer (risk, news, optimisation) contributes the improvement, and under what market regimes does sentiment mislead?

**Contributions you can claim in the report:**
1. **Look-through exposure engine** that unifies direct stock holdings and fund holdings into effective company/sector exposure and fund-overlap metrics.
2. **Exposure-weighted news impact**: news is scored against *the user's effective exposure*, so a negative TCS article matters to a user who only owns IT funds.
3. **Portfolio-aware, explainable decision engine** with safety constraints (never INCREASE an asset whose effective exposure already breaches limits).
4. **Empirical evaluation** with leakage-safe backtesting and ablation, reported honestly even if the result is "no significant improvement". A well-measured null result is still a valid research outcome.
5. **Reference cloud architecture** (serverless + event-driven + IaC + CI/CD) at student-budget cost.

---

## 3. Complete architecture

### 3.1 Logical layers

```text
┌──────────────────────────── PRESENTATION ────────────────────────────┐
│ React + TS + Tailwind + Recharts  →  S3 (static)  →  CloudFront      │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTPS + JWT (Cognito)
┌───────────────────────────────▼──────────────────────────────────────┐
│ API LAYER: API Gateway (HTTP API, JWT authorizer) → API Lambdas       │
└───────────────────────────────┬──────────────────────────────────────┘
┌───────────────────────────────▼──────────────────────────────────────┐
│ DOMAIN CORE (pure Python, AWS-independent, unit-tested)              │
│ portfolio · market · mutual_fund_engine · exposure · risk · news ·   │
│ sentiment · features · ml · optimizer · decision · backtest · stress │
└───────┬───────────────────────────────────────────────┬──────────────┘
┌───────▼──────────── INGESTION / EVENTS ───────────────▼──────────────┐
│ EventBridge Scheduler → Market / NAV / Holdings / News ingest Lambdas │
│ News → SQS (+DLQ) → FinBERT Lambda (container) → events → Risk/Recs   │
│ SNS → email alerts                                                    │
└───────┬──────────────────────────────────────────────────────────────┘
┌───────▼──────────── STORAGE ─────────────────────────────────────────┐
│ S3: raw/ processed/ models/ backtests/ reports/  (Parquet, JSON)      │
│ DynamoDB: users, portfolios, holdings, fund metadata+holdings,        │
│           news+sentiment, risk snapshots, recommendations, alerts     │
└──────────────────────────────────────────────────────────────────────┘
Cross-cutting: IAM least privilege · Secrets Manager · CloudWatch logs/metrics/alarms
               Terraform (IaC) · GitHub Actions (CI/CD) · Docker · pytest
```

### 3.2 Event-driven pipelines

```text
MARKET (daily after market close + optional intraday every 15–30 min)
EventBridge Scheduler → market_ingest λ → S3 raw/market/… → event "MarketDataUpdated"
                                                            → risk_refresh λ → DynamoDB RISK#…

MUTUAL FUNDS
EventBridge (daily ~11pm IST, after AMFI NAV publish) → nav_ingest λ → S3 + DynamoDB FUND#…
EventBridge (monthly) → holdings_ingest λ (AMC portfolio disclosures) → DynamoDB FUND#…/HOLDING#…

NEWS
EventBridge (every 15–30 min) → news_ingest λ → dedupe (hash) → S3 raw/news/
                               → SQS news-queue (DLQ after 3 failures)
                               → news_process λ (FinBERT container, batch 8–16)
                                   → entity/ticker/sector mapping
                                   → DynamoDB NEWS#… + per-ticker sentiment
                                   → event "NewsScored"
"NewsScored" → impact λ: find portfolios exposed (direct OR via a fund) → PORTFOLIO impact
             → if |impact| > threshold → SNS alert
             → decision λ recompute recommendations
```

Why decoupled with EventBridge/SQS: ingestion never waits on FinBERT; spikes in news queue up instead of failing; each stage retries independently; adding a new consumer (e.g. alerts) needs no change to producers.

---

## 4. Major components (one line each, detail comes in its phase)

| Component | Responsibility | Key output |
|---|---|---|
| Portfolio engine | Holdings, quantities, cost basis, valuation, weights, P/L | `PortfolioSnapshot` |
| Market data | Daily OHLCV for NSE stocks + index (NIFTY 50) | Parquet price panel |
| Mutual fund engine | NAV history, returns/CAGR, fund risk, metadata, holdings, sector mix, overlap, fund score | `FundAnalytics` |
| **Exposure engine** | Direct + look-through company/sector exposure, overlap matrix | `EffectiveExposure` |
| Risk engine | Vol, Sharpe, Sortino, MDD, VaR (hist/param/MC), CVaR, beta, correlation, HHI, diversification, risk score | `RiskReport` |
| Stress engine | Shock sectors/market via effective exposure | `StressResult` |
| News pipeline | Fetch, clean, dedupe, timestamp, source, ticker/sector mapping, importance, recency | `NewsItem` |
| Sentiment engine | FinBERT probs, score = P(pos) − P(neg), confidence, time-decayed aggregates | `SentimentScore` |
| Impact engine | Sentiment × importance × recency × reliability × effective exposure | `PortfolioNewsImpact` |
| Feature store | Point-in-time features (market, news, portfolio) | Parquet feature table |
| ML engine | Historical mean → LinReg → RF → XGBoost on future 5d/20d return; SHAP | `ExpectedReturn` + explanations |
| Optimizer | Mean-variance with constraints (asset, sector via look-through, cash) | target weights |
| Decision engine | Combine scores + safety rules → action + reasons | `Recommendation` |
| Backtester | Walk-forward simulation, costs, turnover, metrics, ablations | results in S3 + report |
| Dashboard | Overview, Portfolio, Risk, Funds, News, Recommendations, Backtest, Stress | React app |

---

## 5. How everything connects (end-to-end data story)

```text
Holdings (stocks, funds, cash)
  │
  ├─► prices/NAVs ──► valuation ──► weights w_i
  │
  ├─► funds ──► fund holdings h_{f,s} ──► effective exposure
  │              E_s = w_s(direct) + Σ_f w_f · h_{f,s}      ← THE KEY STEP
  │              E_sector = Σ_s E_s · 1[sector(s)=k]
  │
  ├─► returns ──► Σ (covariance) ──► risk engine ──► risk score, VaR, beta, ...
  │
  ├─► news ──► FinBERT ──► sentiment per ticker ──┐
  │                                               ├─► impact_s = sent·imp·rec·rel
  │                     effective exposure E_s ───┘    portfolio impact = Σ E_s·impact_s
  │
  ├─► features (market + news + portfolio, point-in-time) ──► ML ──► μ (expected returns)
  │
  ├─► μ, Σ, constraints (max E_s, max E_sector, min cash) ──► optimizer ──► target w*
  │
  └─► decision engine: scores + (w* − w) + safety rules ──► BUY/HOLD/REDUCE, INCREASE/…/SWITCH
                                                              + reasons (SHAP, risk, news, exposure)
```

Notes on mutual funds in the optimizer: a fund is optimised as **one asset** (its NAV return series), but the *constraints* use its look-through holdings. So "max 20% IT sector" is enforced on effective sector exposure, including the IT inside funds. This is the bridge between the novel feature and the optimiser.

Cash: modelled as an asset with return = risk-free rate (e.g. 91-day T-bill yield) and zero volatility/correlation.

---

## 6. Phases at a glance

Legend: **M** = mandatory (MVP), **A** = advanced but required to answer the research question, **O** = optional.

| # | Phase | Objective | Major tasks | Tech | Deliverable | Depends on | Tier |
|---|---|---|---|---|---|---|---|
| 0 | Planning & architecture | Lock scope, data sources, designs | Requirements, universe, data feasibility spikes, diagrams, DB + API design, milestones | Markdown, Mermaid/draw.io, OpenAPI | Design pack + repo | — | M |
| 1 | Foundation | Runnable skeleton | Repo layout, venv/uv, FastAPI hello, React+Vite+TS+Tailwind, config (pydantic-settings), logging, pytest, ruff, Docker compose, pre-commit | Python 3.11, FastAPI, Vite, Docker | Skeleton runs locally, CI-ready | 0 | M |
| 2 | Market data | Reliable price history | yfinance (`.NS`) loader, cleaning (splits, gaps, holidays), Parquet storage, calendar, returns | pandas, yfinance, pyarrow | Price/return panel for universe + NIFTY | 1 | M |
| 3 | Portfolio engine | Track a portfolio | Pydantic models, valuation, weights, P/L, transactions, cash | Pydantic, pandas | Portfolio tracker API | 2 | M |
| 4 | Risk engine | Quantify risk | Vol, Sharpe, Sortino, MDD, VaR×3, CVaR, beta, corr, HHI, diversification, risk score (configurable weights) | NumPy, SciPy | Risk API + tests vs hand-computed examples | 3 | M |
| 5 | Mutual fund engine | Funds first-class + look-through | NAV (AMFI/mfapi), CAGR, fund risk, metadata, holdings parser, ISIN→ticker map, sector mix, overlap, **effective exposure** | pandas, openpyxl | Multi-asset analysis + exposure API | 3, 4 | M |
| 6 | News pipeline | Structured news | API client, dedupe, timestamps (UTC/IST), source reliability table, ticker/sector mapping, importance, recency | requests, rapidfuzz | News store (S3 + table) | 1 | M |
| 7 | FinBERT | Financial sentiment | ProsusAI/finbert inference, batching, score & confidence, aggregation, exponential time decay | transformers, torch/ONNX | Sentiment engine + eval on labelled sample | 6 | M |
| 8 | News→portfolio impact | Exposure-weighted news | Impact formula, reverse index stock→funds, portfolio aggregation, alert threshold | — | Portfolio-aware news view | 5, 7 | M |
| 9 | ML | Expected-return model | Point-in-time features, targets (fwd 5d/20d), walk-forward CV, 4 models, IC/hit-rate, SHAP | scikit-learn, XGBoost, SHAP | Model + model card | 2, 7 | A |
| 10 | Optimization | Target allocation | MV with constraints, look-through sector caps, cash floor, (opt) Black-Litterman | PyPortfolioOpt / cvxpy / SciPy | Allocation engine | 4, 5, 9 | A |
| 11 | Recommendations | Explainable actions | Score blend, thresholds, safety rules, SWITCH logic for funds, reason templates | — | Rec API with reasons | 4, 5, 8 (+9, 10) | M (basic) / A (full) |
| 12 | Backtesting & research | Evidence | Walk-forward sim, costs, turnover, 4 strategies, ablation A–D, bootstrap / Sharpe tests, regime split | pandas, NumPy | Results tables + plots | 2–11 | A (needed for RQ) |
| 13 | Dashboard | Professional UI | 8 pages, charts, explanations | React, Recharts | Frontend | 3–12 (incremental) | M (basic) |
| 14 | AWS deploy | Cloud-hosted | S3+CloudFront, API GW HTTP API + Lambda, DynamoDB, S3 data | AWS, Terraform | Live URL | 1–13 | A |
| 15 | Event-driven | Near-real-time | EventBridge Scheduler, SQS+DLQ, FinBERT container Lambda, events | AWS | Automated pipeline | 14 | A |
| 16 | DevOps & CI/CD | Automation | GH Actions: lint, test, build, docker push to ECR, terraform plan/apply, dev/prod | GitHub Actions, OIDC, Terraform | Pipeline | 14 | A |
| 17 | Security & monitoring | Production-style | Cognito, IAM least privilege, Secrets Manager, CloudWatch dashboards/alarms, DLQ alarm, SNS | AWS | Hardened system | 14–16 | A |
| 18 | Final testing | Validation | Unit, integration, API, ML, finance validation, load (k6/Locust), failure, security | pytest, k6 | Test report | all | A |
| 19 | Docs & report | Submission | Report, viva prep, slides, demo script | — | Final package | all | M |

**Strictly optional research extensions:** Black-Litterman, factor models (Fama-French style for India), regime detection (HMM / volatility regimes), alternative sentiment models (e.g. comparing FinBERT vs a lexicon baseline), advanced time-series models.

**Honest note:** your MVP list puts backtesting in "advanced", but your research question cannot be answered without it. Treat Phase 12 as mandatory for the *research* deliverable even if the *demo* MVP ships without it.

---

## 7. Realistic roadmap (16 weeks; compress or stretch to your deadline)

Assumes ~12–15 focused hours/week for one person. With a team of 3–4, run tracks in parallel (see 7.2).

| Week | Focus | Exit criterion |
|---|---|---|
| 1 | Phase 0 | Design pack committed, data feasibility proven |
| 2 | Phase 1 + start **news collector** (see 8) | `docker compose up` runs API + UI; news accumulating daily |
| 3 | Phase 2 | 5+ years of prices for universe in Parquet, tests pass |
| 4 | Phase 3 | Portfolio valuation + P/L correct on sample portfolio |
| 5–6 | Phase 4 | All risk metrics validated against hand/Excel examples |
| 6–7 | Phase 5 | Effective exposure + overlap working for 15–20 funds |
| 8 | Phase 6 + 7 | News scored by FinBERT, sentiment per ticker/day |
| 9 | Phase 8 + basic Phase 11 | **MVP backend complete** |
| 10 | Phase 13 (MVP pages) | **MVP demo-able locally** ← midterm checkpoint |
| 11 | Phase 9 | XGBoost + SHAP, walk-forward results |
| 12 | Phase 10 + full Phase 11 | Optimiser-driven recommendations |
| 13 | Phase 12 | Backtests + ablation tables |
| 14 | Phases 14–15 | Deployed on AWS, event pipeline live |
| 15 | Phases 16–17 | CI/CD, Cognito, alarms |
| 16 | Phases 18–19 | Tests, report, viva prep, demo rehearsal |

### 7.2 If you are a team
- Track A (quant): Phases 2, 4, 5, 10, 12
- Track B (NLP/ML): Phases 6, 7, 8, 9
- Track C (app/cloud): Phases 1, 3, 13, then 14–17
- Integration contract = the Pydantic models + API spec from Phase 0. This is why Phase 0 matters.

---

## 8. Recommended actual build order (and why it differs slightly)

```text
0 → 1 → (start news collector cron NOW) → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 11(basic) → 13(MVP)
  → 9 → 10 → 11(full) → 12 → 14 → 15 → 16 → 17 → 18 → 19
```

Three deliberate tweaks:
1. **Start collecting news in week 2**, even before the news pipeline is "properly" built. A tiny script on a schedule (GitHub Actions cron or your laptop) saving raw JSON every few hours. Free news APIs often limit how far back you can query, so every week you wait is test data you lose. Your backtest needs news with trustworthy timestamps.
2. **Snapshot MF monthly holdings early** for the same reason (AMCs publish monthly portfolios; build an archive going back as far as possible).
3. **Frontend grows incrementally**: from Phase 3 on, add one page per backend phase instead of doing all the UI in Phase 13. A demo-able system at week 10 protects you.

---

## 9. Riskiest / hardest parts

| Risk | Why hard | Mitigation |
|---|---|---|
| **Historical, timestamped news for Indian stocks** | Free APIs have limited India coverage, history and rate limits (Alpha Vantage free tier is very low; verify current limits) | Test coverage in Phase 0; combine sources (Alpha Vantage, GDELT, RSS); start collecting now; restrict research universe to well-covered NIFTY 50 names |
| **Historical MF holdings** | Monthly Excel disclosures, format differs per AMC, ISIN→ticker mapping | Limit to 15–20 funds from 4–5 AMCs; write one parser per AMC; ISIN master from NSE equity list |
| **Leakage / look-ahead bias** | Easy to use same-day close + after-close news, or holdings before their publish date | Every record has `available_at`; feature builder only uses `available_at ≤ t`; unit tests that assert it |
| **FinBERT on Lambda** | ~440 MB model, torch is heavy, cold starts | Container image Lambda, batch via SQS, consider ONNX + int8 quantisation; or score offline for backtests |
| **Weak signal** | News sentiment often has small/unstable predictive power | Design for honest reporting; significance tests; regime analysis |
| **Entity resolution** | "Tata" → which company? "Reliance" → RIL or Reliance Power? | Alias dictionary + ticker tags from API + confidence threshold; manual eval on 200 articles |
| **Scope** | 19 phases | MVP gate at week 10; simplification list below |
| **AWS bill** | NAT gateways, always-on endpoints, log bloat | Budget alarm day 1; no VPC Lambdas; no SageMaker real-time; log retention 7–14 days |

---

## 10. Simplifications if you fall behind (in the order I'd apply them)

1. Universe: NIFTY 50 → **top 20–25 stocks**, 15–20 → **8–10 funds**.
2. Intraday updates → **daily** pipeline only (still event-driven).
3. Monte Carlo VaR → keep historical + parametric only.
4. Random Forest → drop; keep Historical mean, LinReg, XGBoost.
5. Black-Litterman → skip (it's optional anyway).
6. FinBERT in Lambda → **score news in batch** (local/Docker), upload scores to S3/DynamoDB; Lambda only reads scores.
7. Cognito → keep (it's cheap and a marking point) but drop social logins etc.
8. Terraform → keep core modules only (S3, DynamoDB, Lambda, API GW, EventBridge, SQS); add CloudFront/Cognito manually as a last resort and document it.
9. Prod environment → just `dev` with a documented `prod` plan.
10. Stress tests → 3 scenarios instead of 5.

Never cut: look-through exposure, risk engine correctness, leakage-safe backtest, explanations.

---

## 11. Key technical decisions (initial ADRs, revisit in Phase 0)

| Decision | Choice | Reason |
|---|---|---|
| Market | Indian (NSE stocks, AMFI mutual funds) | Matches user base; MF data is free via AMFI |
| Prices | yfinance (dev/historical); paid API only if needed for intraday | Free; verify reliability; label system "near-real-time" |
| NAV | AMFI NAV file + mfapi.in (history) | Free; verify terms |
| Fund holdings | AMC monthly portfolio disclosures | SEBI requires monthly disclosure |
| News | Alpha Vantage NEWS_SENTIMENT + one fallback (GDELT or RSS) | Verify India coverage first |
| Sentiment | ProsusAI/finbert | Trained on financial text (Financial PhraseBank) |
| API | API Gateway **HTTP API** + Lambda | Cheaper than REST API; native JWT authorizer for Cognito |
| Local API | FastAPI, same service layer; Mangum adapter for Lambda | One codebase, thin handlers |
| Time series storage | S3 Parquet (not DynamoDB) | Cheap, columnar, fits pandas |
| App storage | DynamoDB on-demand | Serverless, pay per request, free tier |
| FinBERT hosting (MVP) | Lambda container image fed by SQS | No always-on cost; async so cold start OK |
| IaC | Terraform with modules + dev/prod envs | Required by brief |
| CI auth to AWS | GitHub OIDC role (no long-lived keys) | Security best practice |

---

## 12. Cost model (student budget; verify current prices + free-tier terms on aws.amazon.com/pricing)

| Service | Expected dev usage | Expected cost | Trap to avoid |
|---|---|---|---|
| Lambda | ~50k invocations/month, FinBERT ~3 GB × few s per batch | ≈ $0 (free tier: 1M req + 400k GB-s) | Huge memory on *every* function; give only FinBERT 3 GB |
| API Gateway HTTP API | < 100k req/month | ≈ $0–0.10 | REST API costs ~3.5× more; use HTTP API |
| DynamoDB on-demand | Few k writes/day | ≈ $0 (25 GB free) | Scans; provisioned capacity left on |
| S3 | < 5 GB Parquet + raw news | < $0.15 | Versioning on noisy prefixes |
| EventBridge / SQS / SNS | Thousands of msgs/month | ≈ $0 | — |
| CloudWatch Logs | Lambda logs | $0–1 | **Set retention 7–14 days** (default is forever) |
| ECR | 1 FinBERT image ~1–2 GB | ~$0.10–0.20 | Old image tags; add lifecycle policy |
| Secrets Manager | 2–3 secrets | ~$0.40 per secret/month | Use SSM Parameter Store SecureString (free) if budget is tight |
| Cognito | < 50 users | $0 | — |
| CloudFront | Low traffic | ≈ $0 (free tier) | — |
| **NAT Gateway** | **not used** | would be ~$32+/month | Never put Lambdas in a VPC for this project |
| **SageMaker real-time endpoint** | **not used** | ~$40–100+/month always-on | Use Lambda container; Serverless Inference only as an experiment |

**FinBERT hosting decision:** (1) Lambda container image: no idle cost; cold start ~5–15 s is fine because SQS processing is async → **MVP choice**. (2) Always-on inference service (EC2/ECS): low latency, but you pay 24/7. (3) SageMaker endpoint: most "ML-ops" looking, but the most expensive and the most complex. (4) Offline batch scoring for historical backtests: always run locally/Docker; Lambda handles only new articles.

Target: **< US$5/month** in dev, enforced by the Budget alarm from Phase 0.

---

*Next: see `01_PHASE_0_GUIDE.md`.*
