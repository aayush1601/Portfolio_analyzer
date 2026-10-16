# ADR 0002: FIFO queue instead of reserved concurrency for the FinBERT scorer

- **Status:** Accepted
- **Date:** 2026-10-15

## Context
`news_score` (the FinBERT Lambda) reads `processed/sentiment.parquet`, appends the scores of a batch and writes
the file back to S3. Two copies running at once would each write their own version and one batch of scores
would be lost (a lost update). The first design prevented that with `reserved_concurrent_executions = 1`.

The first real deploy failed: *"Specified ReservedConcurrentExecutions for function decreases account's
UnreservedConcurrentExecution below its minimum value of [10]."* New AWS accounts have a regional Lambda
concurrency limit of 10, and AWS requires 10 to stay unreserved, so on such an account any reservation is
refused. A quota increase is possible but takes time and is not guaranteed for new accounts.

## Options
1. **Ask for a quota increase** and keep the reservation. Blocks deployment on AWS's timeline.
2. **`maximum_concurrency` on the SQS event source.** Its minimum is 2, so two writers remain possible.
3. **SQS FIFO queue with a single message group.** Lambda processes the messages of one group strictly in
   order, one batch at a time, so there is one writer by construction.
4. **One file per batch** (no read-modify-write). Removes the race but changes the storage layout that the
   API, backtest and tests read.

## Decision
Option 3. The news queue and its DLQ are FIFO (`pi-<env>-news.fifo`); `news_ingest` sends every headline
with `MessageGroupId = "news"` and `MessageDeduplicationId = news_id`; the reservation is removed.

## Consequences
- Single-writer guarantee without reserving capacity; works on any account.
- Duplicate sends within FIFO's 5-minute window are dropped by SQS; later redeliveries were already skipped by
  the handler (it ignores news_ids that are already scored).
- Batch size is at most 10 (FIFO limit) and FIFO sources take no batching window. At ~50–150 new headlines
  per 30-minute run this means a handful of sequential invocations, well inside the 30-minute cycle.
- Throughput is one batch at a time. If scoring ever falls behind, the `news-older-than-30-min` alarm fires;
  the next step would then be option 4.
- A failing batch blocks the group until it succeeds or moves to the DLQ after 3 receives (alarmed), which is
  the behaviour we want for a single ordered writer.
