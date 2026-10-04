# Data model and storage design

Conventions: timestamps are ISO-8601 UTC; money is INR decimals; weights are fractions (0.232, not 23.2).
**Every market/news/holdings record carries `available_at`**, the earliest moment the system could have known it. This is the leakage guard (NFR7).

## 1. Entities (become Pydantic models in Phases 1–3)

```text
User(user_id, email, created_at, risk_profile{conservative|moderate|aggressive}, settings)
Portfolio(portfolio_id, user_id, name, base_currency="INR", created_at)
Holding(portfolio_id, asset_type{STOCK|MF|CASH}, asset_id, quantity, avg_cost, added_at)
Transaction(portfolio_id, txn_id, asset_id, type{BUY|SELL|DEPOSIT|WITHDRAW}, qty, price, ts)

Stock(symbol, yahoo, isin, name, sector, industry, aliases[])
Fund(scheme_code, isin, name, amc, category, subcategory, plan{Direct|Regular}, option{Growth|IDCW},
     benchmark, expense_ratio, aum, manager, strategy, as_of)
FundHolding(scheme_code, as_of_month, published_at, isin, symbol?, name, weight, sector)

PriceBar(symbol, date, open, high, low, close, adj_close, volume, available_at)
NavPoint(scheme_code, date, nav, available_at)

NewsItem(news_id = sha256(normalised_url | normalised_title), source, url, headline, summary,
         published_at, ingested_at, symbols[], sectors[], importance, reliability)
Sentiment(news_id, model="ProsusAI/finbert", p_pos, p_neu, p_neg, score = p_pos − p_neg,
          label, confidence = max(p_pos, p_neu, p_neg))

RiskSnapshot(portfolio_id, as_of, metrics{...}, risk_score, risk_band, weights_config_version)
Recommendation(portfolio_id, as_of, asset_id, action, final_score, components{...},
               reasons[], constraints_triggered[], model_version)
Alert(user_id, alert_id, type, severity, message, created_at, acknowledged)
BacktestRun(run_id, config_hash, strategy, period, status, metrics{...}, s3_path)
```

## 2. Where each thing lives

| Data | Store | Why |
|---|---|---|
| Prices, NAVs, features, sentiment history | **S3 Parquet** (`processed/…`, partitioned by year) | Time series are scanned in bulk by pandas; cheap and columnar |
| Raw API responses, raw news, AMC Excel files | **S3** `raw/…` | Immutable audit trail; lets us re-process |
| Models, backtest outputs, reports | **S3** `models/`, `backtests/`, `reports/` | Large files |
| Users, portfolios, holdings, latest risk/recs, alerts | **DynamoDB** `UserData` | Low-latency key lookups per user |
| Stock/fund reference data, fund holdings | **DynamoDB** `MarketRef` | Shared, read by API and news-impact lookups |
| Recent news + sentiment (180-day TTL) | **DynamoDB** `News` | "Latest news for ticker X" queries |

S3 layout:
```text
s3://<project>-<env>-data/
  raw/{market,news,mutual_funds}/YYYY/MM/DD/…
  processed/{market,nav,news,features}/year=YYYY/…parquet
  models/<model_name>/<version>/
  backtests/<run_id>/
  reports/
```

## 3. DynamoDB design (from access patterns, not entities)

All three tables use **on-demand** capacity, generic key names `PK`/`SK`, and one overloaded GSI `GSI1PK`/`GSI1SK`.

| # | Access pattern | Table / index | Key condition |
|---|---|---|---|
| AP1 | Get user profile | UserData | PK=`USER#<sub>`, SK=`PROFILE` |
| AP2 | List my portfolios | UserData | PK=`USER#<sub>`, SK begins_with `PORTFOLIO#` (metadata items have SK=`PORTFOLIO#<pid>#META`) |
| AP3 | Holdings of a portfolio | UserData | PK=`USER#<sub>`, SK begins_with `PORTFOLIO#<pid>#HOLDING#` |
| AP4 | Latest risk snapshot | UserData | SK begins_with `PORTFOLIO#<pid>#RISK#`, ScanIndexForward=false, Limit=1 |
| AP5 | Recommendations for a date | UserData | SK begins_with `PORTFOLIO#<pid>#REC#<yyyy-mm-dd>#` |
| AP6 | My alerts, newest first | UserData | SK begins_with `ALERT#` (SK=`ALERT#<ts>#<id>`), ScanIndexForward=false |
| AP7 | Fund metadata | MarketRef | PK=`FUND#<code>`, SK=`META` |
| AP8 | Fund holdings for a month | MarketRef | PK=`FUND#<code>`, SK begins_with `HOLDING#<yyyy-mm>#` |
| AP9 | **Which funds hold stock X?** | MarketRef GSI1 | GSI1PK=`STOCK#<symbol>`, GSI1SK begins_with `<yyyy-mm>#` |
| AP10 | **Which portfolios hold stock X or fund F?** | UserData GSI1 | GSI1PK=`ASSET#<asset_id>` (set only on holding items), GSI1SK=`USER#<sub>#PORTFOLIO#<pid>` |
| AP11 | Recent news for stock X | News | PK=`TICKER#<symbol>`, SK begins_with/≥ `<published_at>` |
| AP12 | Dedupe a news item | News | PK=`NEWS#<id>`, SK=`META`, conditional put `attribute_not_exists(PK)` |

Example items:
```json
{"PK":"USER#a1b2","SK":"PORTFOLIO#p01#HOLDING#STOCK#TCS","asset_type":"STOCK","quantity":10,"avg_cost":3650.5,
 "GSI1PK":"ASSET#STOCK#TCS","GSI1SK":"USER#a1b2#PORTFOLIO#p01"}
{"PK":"FUND#120594","SK":"HOLDING#2026-08#INE467B01029","symbol":"TCS","weight":0.081,"published_at":"2026-09-10",
 "GSI1PK":"STOCK#TCS","GSI1SK":"2026-08#FUND#120594"}
{"PK":"TICKER#TCS","SK":"2026-10-02T08:00:00Z#9f3c…","news_id":"9f3c…","score":-0.62,"impact":-0.18,"ttl":1790000000}
```

News → affected users (the look-through query): article mentions TCS → AP9 gives the funds holding TCS → AP10 for `ASSET#STOCK#TCS` plus each `ASSET#MF#<code>` gives the affected portfolios. No Scan is needed.

**Isolation:** the API always builds `PK = USER#<sub>`, where `sub` comes from the verified Cognito JWT, never from the request body or path. A user cannot construct another user's key. The API Lambda's IAM policy additionally limits it to the `UserData` table.

**Why three tables, not one:** one table is the textbook DynamoDB pattern. But three tables match three different writers (API, ingestion, news pipeline), allow per-table IAM least privilege, and are easier to defend in a viva. Each table is still key-designed, not normalised.
