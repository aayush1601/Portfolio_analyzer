# Portfolio Intelligence

**Real-Time Cloud-Based Multi-Asset Portfolio Risk & Financial Intelligence System**: a cloud-native, event-driven platform that combines market data, mutual-fund look-through exposure, FinBERT news sentiment, machine learning, portfolio optimisation and explainable recommendations, and evaluates them by historical backtesting.

> **Disclaimer:** academic decision-support and research project. Recommendations are hypothetical and are not financial advice. The system does not guarantee profit; it generates data-driven, explainable recommendations and evaluates their historical risk-adjusted performance through backtesting.

## Status
Phase 0 (planning & architecture).

## Docs
- [Project plan](docs/00_PROJECT_PLAN.md) · [Phase 0 guide](docs/01_PHASE_0_GUIDE.md)
- [Requirements](docs/requirements.md) · [Data sources](docs/data_sources.md) · [ADR 0001](docs/adr/0001-news-source.md)
- [Look-through exposure](docs/algorithms/exposure.md) · [Data model & DynamoDB](docs/data_model.md)
- [API spec](docs/api/openapi.yaml) · [Diagrams](docs/diagrams/README.md)
- Research universe: [config/universe.yaml](config/universe.yaml)

## Phase 0 feasibility spike
```bash
python3 -m venv .venv && .venv/bin/pip install yfinance requests pandas pyyaml
cp .env.example .env   # add ALPHAVANTAGE_API_KEY
.venv/bin/python spikes/check_sources.py
```
