# ADR 0003: Historical news from the GDELT Knowledge Graph in BigQuery

- **Status:** Accepted (supersedes the open "historical backtest news" item of ADR 0001)
- **Date:** 2026-10-16

## Context
The first backtest run (`docs/backtest_report.md`) had news evidence on only 3 of 105 monthly rebalances,
because the RSS archive starts on 2026-10-04. Without history the news-aware strategy D equals strategy C, so
RQ3 cannot be answered. ADR 0001 left three options: Alpha Vantage (untested, unknown Indian coverage, 25
requests/day free), GDELT, or a US research universe.

The GDELT DOC API only searches a rolling recent window. The full history is in the GDELT Global Knowledge
Graph (GKG 2.1), published as the public BigQuery table `gdelt-bq.gdeltv2.gkg_partitioned`. Each row is one
article: the publisher domain, the URL, the 15-minute batch in which GDELT saw it, and the page title (in the
`Extras` field). The BigQuery sandbox is free without a card (1 TB of queries a month); over the quota a query
is refused, not billed.

## Decision
- `app.services.news_gdelt sql` generates one query: rows from six Indian business publishers (Economic Times,
  Mint, Business Standard, Moneycontrol, BusinessLine, Financial Express) whose title mentions a universe
  company alias or sector keyword, from `gdelt.start` (default 2022-01-01) to today. Only four columns are read
  and partitions are pruned by date, so the scan stays within the sandbox quota.
- The result (CSV) is imported with `news_gdelt import`: raw JSONL in `data/raw/news/gdelt/`, then the same
  `news_pipeline.process()` (dedupe, entity mapping, stop phrases, importance, reliability) into a separate
  store, `data/processed/news_history/`. `load_news()` returns live and history together.
- FinBERT scores the history once, locally (`sentiment score`). The cloud job only queues headlines from the
  last 7 days, so history is never scored in Lambda.
- Timestamp: `published_at` = the GKG batch time. GDELT sees an article minutes to hours after publication,
  so a backtest at time *t* sees each article late, never early: no look-ahead.

## Consequences
- RQ3 becomes testable on the window where history exists (from `gdelt.start`); the ablation reports news
  coverage per rebalance, so the window is explicit.
- Headlines only (GKG has no article body); this matches how FinBERT is used for live news.
- Coverage depends on GDELT's crawl of these publishers, which is not complete; the report should state the
  number of articles per month and per company.
- Titles are filtered twice: loosely in SQL (word boundaries) and exactly by the Mapper after import, so
  "SBI Card" or "Reliance Power" never count as SBI or Reliance.
- One manual step (running the query in the BigQuery console) stays outside the codebase; the SQL is generated
  and versioned, so the step is reproducible.
