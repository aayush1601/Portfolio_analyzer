# Diagrams (Mermaid; renders on GitHub)

For the report, redraw diagram 1 in draw.io with the AWS icon set and save it as `aws_architecture.drawio` + `.png`.

## 1. System architecture (AWS)
```mermaid
flowchart TB
  U[User] --> CF[CloudFront] --> S3W[S3 static React app]
  U -- JWT --> APIGW[API Gateway HTTP API<br/>Cognito JWT authorizer]
  COG[Cognito] -.issues JWT.-> U
  APIGW --> APIL[API Lambdas<br/>FastAPI + Mangum]
  APIL --> DDB[(DynamoDB<br/>UserData · MarketRef · News)]
  APIL --> S3D[(S3 data lake<br/>raw · processed · models · backtests)]

  subgraph Ingestion & events
    SCH[EventBridge Scheduler] --> MI[market_ingest λ]
    SCH --> NAV[nav_ingest λ]
    SCH --> NI[news_ingest λ]
    MI --> S3D
    NAV --> S3D
    NI --> S3D
    NI --> Q[SQS news-queue] --> NP[news_process λ<br/>FinBERT container]
    Q -. 3 failures .-> DLQ[SQS DLQ]
    NP --> DDB
    NP -- NewsScored --> EB[EventBridge bus]
    MI -- MarketDataUpdated --> EB
    EB --> IMP[impact + risk + decision λ]
    IMP --> DDB
    IMP --> SNS[SNS alerts] --> E[Email]
  end

  SM[Secrets Manager] -.API keys.-> MI & NI
  CW[CloudWatch logs · metrics · alarms] -.-> APIL & NP & Q & DLQ
```

## 2. Component diagram (domain core, AWS-independent)
```mermaid
flowchart LR
  market[market data] --> portfolio
  mf[mutual_fund_engine] --> exposure
  portfolio --> exposure
  market --> risk
  exposure --> risk
  exposure --> stress
  news --> sentiment --> impact
  exposure --> impact
  market --> features
  sentiment --> features
  exposure --> features
  features --> ml --> optimizer
  risk --> optimizer
  exposure --> optimizer
  risk --> decision
  impact --> decision
  ml --> decision
  optimizer --> decision
  decision --> backtest
  optimizer --> backtest
```

## 3a. Data-flow diagram, level 0
```mermaid
flowchart LR
  User((User)) -- holdings, queries --> SYS[Portfolio Intelligence System]
  SYS -- dashboards, recommendations, alerts --> User
  MKT[(Market data: Yahoo)] --> SYS
  AMFI[(AMFI / mfapi NAVs)] --> SYS
  AMC[(AMC holdings files)] --> SYS
  NEWS[(News: RSS / AV / GDELT)] --> SYS
```

## 3b. Data-flow diagram, level 1
```mermaid
flowchart LR
  subgraph Ingest
    P1[1. Ingest prices & NAVs]
    P2[2. Ingest fund holdings]
    P3[3. Ingest & dedupe news]
  end
  P1 --> D1[(S3 processed prices/NAV)]
  P2 --> D2[(MarketRef holdings)]
  P3 --> D3[(S3 raw news)]
  D3 --> P4[4. FinBERT + entity mapping] --> D4[(News table)]
  D1 & D2 --> P5[5. Exposure + risk]
  D4 & P5 --> P6[6. Impact + ML + optimise + decide]
  P5 & P6 --> D5[(UserData: risk, recs, alerts)]
  D5 --> P7[7. API] --> User((User))
```

## 4. News → portfolio impact sequence
```mermaid
sequenceDiagram
  participant EB as EventBridge Scheduler
  participant NI as news_ingest λ
  participant Q as SQS news-queue
  participant NP as news_process λ (FinBERT)
  participant DB as DynamoDB
  participant IM as impact λ
  participant SNS as SNS
  EB->>NI: every 30 min
  NI->>NI: fetch, dedupe (hash), store raw to S3
  NI->>Q: send new article ids
  Q->>NP: batch of 8–16 messages
  NP->>DB: put sentiment (idempotent, conditional put)
  NP-->>IM: event NewsScored(symbols)
  IM->>DB: GSI1 STOCK#X → funds holding X
  IM->>DB: GSI1 ASSET#… → portfolios holding X or those funds
  IM->>DB: write portfolio impact
  IM->>SNS: publish alert if |impact| > threshold
```

## 5. DynamoDB key design
```mermaid
erDiagram
  UserData {
    string PK "USER#sub"
    string SK "PROFILE | PORTFOLIO#pid#META | PORTFOLIO#pid#HOLDING#type#id | PORTFOLIO#pid#RISK#ts | PORTFOLIO#pid#REC#date#asset | ALERT#ts#id"
    string GSI1PK "ASSET#type#id (holdings only)"
    string GSI1SK "USER#sub#PORTFOLIO#pid"
  }
  MarketRef {
    string PK "STOCK#symbol | FUND#code"
    string SK "META | HOLDING#yyyy-mm#isin"
    string GSI1PK "STOCK#symbol (holding rows)"
    string GSI1SK "yyyy-mm#FUND#code"
  }
  News {
    string PK "NEWS#id | TICKER#symbol"
    string SK "META | published_at#id"
    number ttl "expire after 180 days"
  }
  UserData ||--o{ MarketRef : "holding asset_id → fund/stock"
  MarketRef ||--o{ News : "symbol → articles"
```
