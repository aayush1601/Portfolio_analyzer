# AWS deployment (Phases 14–15)

Region `ap-south-1` (Mumbai). Everything is Terraform in `infrastructure/` (modules `storage`, `api`, `web`,
`pipeline`, `budget`; environment `environments/dev`). Serverless only: no VPC, NAT gateway or always-on
compute, so idle cost is close to zero (plan §12, NFR3).

```text
Browser ──HTTPS──▶ CloudFront ─┬─ /*      ▶ S3 (frontend, private, Origin Access Control)
                               └─ /api/*  ▶ API Gateway HTTP API ▶ Lambda "api" (FastAPI via Mangum)
                                                                     │ reads S3 Parquet (mirrored to /tmp)
                                                                     │ portfolios ▶ DynamoDB UserData
EventBridge Scheduler (IST)
  weekdays 16:30 ▶ market_ingest ──▶ S3 prices ──▶ bus: MarketDataUpdated ▶ risk_refresh ▶ DynamoDB snapshots
  daily 23:30    ▶ nav_ingest    ──▶ S3 NAVs
  every 30 min   ▶ news_ingest   ──▶ S3 news ──▶ SQS news ──(DLQ after 3)──▶ news_score (FinBERT image)
                                                              └▶ bus: NewsScored ▶ news_impact ▶ SNS email alert
  monthly 12th   ▶ holdings_ingest (parses AMC files uploaded to s3://…/raw/mutual_funds/holdings/)
CloudWatch: 14-day log retention, alarm when the DLQ is not empty. AWS Budget: US$5/month, alerts at 50/80/100%.
```

## Design notes
- **One codebase.** The same `app` package runs locally and on Lambda. `STORAGE=s3` switches portfolios to
  DynamoDB and makes every function mirror S3 into `/tmp`; a small `_version` object, bumped on every write,
  tells other containers when to re-sync (one HEAD per request).
- **Images, not zips.** pandas, SciPy and pyarrow exceed Lambda's 250 MB zip limit, so functions ship as arm64
  container images: one backend image (API and jobs; the handler is chosen per function) and one FinBERT image
  with CPU-only torch and the model baked in, so cold starts never download it.
- **Decoupled news scoring.** Ingestion never waits for FinBERT: unscored headlines queue in SQS, the scorer
  runs with reserved concurrency 1 (a single writer for the sentiment file), failures retry and then land in
  the DLQ, which raises an alarm.
- **Least privilege.** One IAM role for the backend functions, limited to this project's bucket, table, bus,
  queue and topic; the scheduler role can only invoke the job functions.
- **Phone import on AWS.** QR tokens live in DynamoDB (TTL) so any container can validate them, and the QR
  opens the public CloudFront URL.

## Deploy / remove
```bash
aws configure                              # or: aws login
./scripts/deploy.sh you@example.com        # Terraform shows a plan and asks before each apply
./scripts/destroy.sh                       # removes everything, data buckets included
```
The script: creates the ECR repositories, builds and pushes both images, applies the rest, seeds S3 with the
local `data/processed`, `data/raw/news` and backtests, then builds and uploads the frontend.

## What has been verified
- `terraform validate` passes for the whole configuration (Terraform 1.16.5, AWS provider 5.x).
- Handlers, the DynamoDB store, S3 sync and import tokens are tested against moto (`backend/tests/test_aws.py`).
- Not yet run against a real account: image builds, `terraform apply`, and the end-to-end schedule. Those need
  AWS credentials and Docker.

## Known limits (dev)
- Local Terraform state; move to an S3 backend with locking for a team.
- `news_impact` and `risk_refresh` scan the UserData table (fine at dev scale; AP10's index is the upgrade).
- No authentication yet: every request is the local user. Cognito and the JWT authorizer are Phase 17.
