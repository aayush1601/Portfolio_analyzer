# Portfolio Intelligence

**Real-Time Cloud-Based Multi-Asset Portfolio Risk & Financial Intelligence System**: a cloud-native, event-driven platform that combines market data, mutual-fund look-through exposure, FinBERT news sentiment, machine learning, portfolio optimisation and explainable recommendations, and evaluates them by historical backtesting.

> **Disclaimer:** academic decision-support and research project. Recommendations are hypothetical and are not financial advice. The system does not guarantee profit; it generates data-driven, explainable recommendations and evaluates their historical risk-adjusted performance through backtesting.

## Status
Phase 1 (foundation) done: FastAPI + React skeleton, Docker, tests, RSS news archiver.
Phase 2 (market data) done: cleaned daily price panel for the universe + `^NSEI` + `^INDIAVIX` in Parquet.
Phase 3 (portfolio engine) done: portfolio API with valuation, weights and P/L for stocks, funds and cash.
Phase 4 (risk engine) done: `GET /portfolio/{id}/risk` with volatility, Sharpe/Sortino, drawdown, VaR ×3, CVaR, beta, HHI, diversification and a 0–100 risk score ([config/risk_score.yaml](config/risk_score.yaml)).
Phase 5 (funds + look-through) code done: fund analytics, effective exposure, overlap, stress. **Needs AMC holdings files** (below).
Phase 6 (news pipeline) done: dedupe, company/sector mapping, importance, reliability, recency → `data/processed/news`.
Phase 7 (FinBERT sentiment) done: per-headline scores, time-decayed per-ticker aggregates, labelled-sample evaluation.
Phase 8 (news → portfolio impact) done: `GET /portfolio/{id}/news`, exposure-weighted impact with alert flag (`impact` in config/news_sources.yaml).
Phase 11 basic (recommendations) done: `GET /portfolio/{id}/recommendations`, BUY/HOLD/REDUCE and INCREASE/HOLD/REDUCE/SWITCH with reasons and look-through safety caps ([config/recommendations.yaml](config/recommendations.yaml)). **MVP backend complete.**
Phase 13 MVP pages: Look-through (default), Holdings, Risk + stress test, News, Actions at http://localhost:5173 (visual direction: `.impeccable/surfaces/`).
Phase 9 (ML) done: point-in-time features, walk-forward ridge/RF/XGBoost vs baseline, SHAP; see the model card.

## Docs
- [Project plan](docs/00_PROJECT_PLAN.md) · [Phase 0 guide](docs/01_PHASE_0_GUIDE.md)
- [Requirements](docs/requirements.md) · [Data sources](docs/data_sources.md) · [ADR 0001](docs/adr/0001-news-source.md)
- [Look-through exposure](docs/algorithms/exposure.md) · [Data model & DynamoDB](docs/data_model.md)
- [API spec](docs/api/openapi.yaml) · [Diagrams](docs/diagrams/README.md)
- Research universe: [config/universe.yaml](config/universe.yaml)

## Run locally
Prerequisites: [uv](https://docs.astral.sh/uv/), Node 22+, Docker.

```bash
cp .env.example .env                                   # add keys; never commit .env
docker compose up --build                              # API :8000, UI :5173
```

Without Docker:
```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

Checks:
```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && npm run lint && npm run build
```

## News archiver (runs from Phase 1 so the backtest has news)
Each run also rebuilds `data/processed/news` (`app.services.news_pipeline`). Company aliases are in
`config/universe.yaml`; stop phrases, sector keywords and the importance weights are in `config/news_sources.yaml`.
```bash
./scripts/collect_news.sh                              # one run → data/raw/news/rss/<date>.jsonl
cp scripts/com.portfolio-intelligence.news.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.portfolio-intelligence.news.plist   # every 30 min while awake
```

## Market data (Phase 2)
```bash
cd backend && uv run python -m app.services.market_data   # after market close; rewrites data/processed/market/prices
cd backend && uv run python -m app.services.nav_data      # after ~23:00 IST; mutual fund NAVs → data/processed/nav
```
In code: `load_prices(settings.data_dir)` for PriceBar rows, `returns(prices)` for the date × symbol return panel.

## Portfolios (Phase 3)
`POST/GET /portfolio`, `GET /portfolio/{id}` (valuation, weights, P/L), `PUT /portfolio/{id}/holdings`; see the API docs at http://localhost:8000/docs.
Local auth stub: every request is user `local`, stored as JSON in `data/portfolios/local/`. A new user starts with the
demo portfolios in [config/demo_portfolios.yaml](config/demo_portfolios.yaml). Holdings must be in the research universe.

## Expected-return models (Phase 9)
```bash
cd backend && uv run --group ml python -m app.services.ml   # ~2 min: walk-forward eval, final XGBoost, SHAP, model card
```
Results and limitations: [docs/model_card.md](docs/model_card.md). Recommendations show the model's rank and drivers;
its weight stays 0 in `config/recommendations.yaml` until it shows significant out-of-sample skill.

## Sentiment (Phase 7)
Needs the `ml` group (torch + transformers; ~440 MB model on first run, cached by Hugging Face):
```bash
cd backend && uv run --group ml python -m app.services.sentiment score        # new headlines only
uv run --group ml python -m app.services.sentiment sample 200                 # data/labelled/news_sample.csv
uv run --group ml python -m app.services.sentiment eval ../data/labelled/news_sample.csv
```
Label the sample by hand (positive / neutral / negative) before running `eval`.

## Fund holdings and look-through exposure (Phase 5)
1. Download each AMC's monthly portfolio disclosure (Excel) for the universe funds, 24–36 months back, into
   `data/raw/mutual_funds/holdings/<amc>/` (file names don't matter).
2. `cd backend && uv run python -m app.services.fund_holdings` → `data/processed/fund_holdings.parquet`.
   Sheets are matched to funds by scheme name; a sheet logged as *skipped* under an old fund name needs a
   `holdings_aliases` entry in `config/universe.yaml`.

Routes: `GET /portfolio/{id}/exposure`, `POST /portfolio/{id}/stress`, `GET /mutual-funds/{scheme_code}`.
Funds without a disclosure count as *Other/Unmapped* (the response says so) until their files are ingested.

## Phase 0 feasibility spike
```bash
cd backend && uv sync --group spikes && uv run python ../spikes/check_sources.py
```
