# Testing (Phase 18)

| Layer | What | Where | How to run |
|---|---|---|---|
| Unit: finance | Every risk, exposure, optimiser and decision formula against hand-computed examples (NFR6) | `backend/tests/test_risk.py`, `test_exposure.py`, `test_optimizer.py`, `test_recommend.py` | `cd backend && uv run pytest -q` |
| Unit: data | Market data cleaning, NAVs, RSS parsing, news mapping and stop phrases, GDELT import, CAS import | `test_market_data.py`, `test_nav_data.py`, `test_news_rss.py`, `test_news_pipeline.py`, `test_news_gdelt.py`, `test_cas_import.py` | same |
| ML | Point-in-time features (no look-ahead), walk-forward split, sentiment aggregation | `test_features.py`, `test_sentiment.py` | same |
| Backtest | Costs, turnover, rebalancing, bootstrap test | `test_backtest.py` | same |
| API | Endpoints, ownership, sign-in (JWT `sub`, 401 on AWS without identity) | `test_portfolio.py`, `test_health.py`, `test_auth.py` | same |
| Cloud (moto) | Lambda handlers, DynamoDB store, S3 mirror, SQS → FinBERT, SNS alerts, SSM secrets | `test_aws.py` | same |
| Failure modes | One RSS feed down; FinBERT crash → batch raises (SQS retry → DLQ), nothing written; redelivered SQS messages not re-scored; history never queued to Lambda | `test_news_rss.py`, `test_aws.py` | same |
| Load | Dashboard traffic: list → overview, risk, look-through, news, actions | `scripts/loadtest/locustfile.py` | see below |
| CI | All of the above except load, plus ruff, frontend lint/build, Terraform fmt/validate, on every push | `.github/workflows/ci.yml` | GitHub → Actions |

Status 2026-10-16: 115 backend tests pass.

## Load test (NFR2: read endpoints p95 < 1 s)
```bash
cd backend && uv run uvicorn app.main:app --port 8000          # terminal 1 (add --workers 4 to compare)
uvx locust -f scripts/loadtest/locustfile.py --host http://localhost:8000 \
    --headless -u 50 -r 5 -t 2m --csv docs/loadtest/local      # terminal 2, from the repo root
```
`docs/loadtest/local_stats.csv` has the percentiles per endpoint. Run it with 1 and with 4 workers, and later
against the cloud API (instructions in the locustfile), and put the three p95 tables here.

**First result (2-core test machine, 1 worker, 20 users, 60 s, 0 failures):** single requests take 0.1–0.5 s,
but under concurrency the heavy pages queue: p95 overview 1.9 s, look-through 2.7 s, news 3.3 s, risk 5.1 s,
recommendations 6.1 s. NFR2 is **not** met by a single local process. Causes: the risk and recommendation
pages recompute from the full price history on every request, and one Python process serves requests one CPU
slice at a time. Planned answers, in order: more workers locally; on AWS, Lambda runs each concurrent request in
its own container; then cache per-portfolio results keyed by the data `_version` so repeated reads are
precomputed (as NFR2 assumes).
