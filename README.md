# Portfolio Intelligence

**Real-Time Cloud-Based Multi-Asset Portfolio Risk & Financial Intelligence System**: a cloud-native, event-driven platform that combines market data, mutual-fund look-through exposure, FinBERT news sentiment, machine learning, portfolio optimisation and explainable recommendations, and evaluates them by historical backtesting.

> **Disclaimer:** academic decision-support and research project. Recommendations are hypothetical and are not financial advice. The system does not guarantee profit; it generates data-driven, explainable recommendations and evaluates their historical risk-adjusted performance through backtesting.

## Status
Phase 1 (foundation) done: FastAPI + React skeleton, Docker, tests, RSS news archiver.
Phase 2 (market data) done: cleaned daily price panel for the universe + `^NSEI` + `^INDIAVIX` in Parquet.
Phase 3 (portfolio engine) done: portfolio API with valuation, weights and P/L for stocks, funds and cash.

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

## Phase 0 feasibility spike
```bash
cd backend && uv sync --group spikes && uv run python ../spikes/check_sources.py
```
