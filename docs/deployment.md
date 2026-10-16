# AWS deployment (Phases 14–17)

Region `ap-south-1` (Mumbai). Everything is Terraform in `infrastructure/`: a one-time `bootstrap` stack
(state bucket, GitHub OIDC deploy role) and one environment root (`environments/`, modules `storage`, `api`,
`web`, `auth`, `pipeline`, `monitoring`, `budget`) applied per environment with `-var env=dev|prod`.
Serverless only: no VPC, NAT gateway or always-on compute, so idle cost is close to zero (plan §12, NFR3).

```text
Browser ──HTTPS──▶ CloudFront ─┬─ /*      ▶ S3 (frontend, private, Origin Access Control)
                               └─ /api/*  ▶ API Gateway HTTP API ─(Cognito JWT authorizer)─▶ Lambda "api"
                                                                     │ reads S3 Parquet (mirrored to /tmp)
                                                                     │ portfolios ▶ DynamoDB UserData
EventBridge Scheduler (IST)
  weekdays 16:30 ▶ market_ingest ──▶ S3 prices ──▶ bus: MarketDataUpdated ▶ risk_refresh ▶ DynamoDB snapshots
  daily 23:30    ▶ nav_ingest    ──▶ S3 NAVs
  every 30 min   ▶ news_ingest   ──▶ S3 news ──▶ SQS FIFO news ──(DLQ after 3)──▶ news_score (FinBERT image)
                                                                   └▶ bus: NewsScored ▶ news_impact ▶ SNS email alert
  monthly 12th   ▶ holdings_ingest (parses AMC files uploaded to s3://…/raw/mutual_funds/holdings/)
CloudWatch: 14-day logs, an alarm per Lambda + API 5xx + DLQ + news backlog, one dashboard.
AWS Budget: US$5/month, alerts at 50/80/100%.
```

## Design notes
- **One codebase.** The same `app` package runs locally and on Lambda. `STORAGE=s3` switches portfolios to
  DynamoDB and makes every function mirror S3 into `/tmp`; a small `_version` object, bumped on every write,
  tells other containers when to re-sync (one HEAD per request).
- **Images, not zips.** pandas, SciPy and pyarrow exceed Lambda's 250 MB zip limit, so functions ship as arm64
  container images: one backend image (API and jobs; the handler is chosen per function) and one FinBERT image
  with CPU-only torch and the model baked in, so cold starts never download it. ECR keeps the last 2 backend
  images and the last FinBERT image (storage is the main running cost).
- **Decoupled news scoring.** Ingestion never waits for FinBERT: unscored headlines queue in SQS. The queue is
  FIFO with one message group, so the scorer gets one batch at a time and `sentiment.parquet` has a single
  writer without reserving Lambda concurrency ([ADR 0002](adr/0002-fifo-queue-single-writer.md)). Failures
  retry and then land in the DLQ, which raises an alarm. Only headlines from the last 7 days are queued, so
  the historical GDELT store ([ADR 0003](adr/0003-historical-news-gdelt.md)) is never scored in Lambda.
- **Least privilege.** Two IAM roles: the API may only Get/Put/Query its table; the jobs may also Scan and use
  the bus, queue and topic. The scheduler role can only invoke the job functions. Secrets are SecureString
  parameters in SSM Parameter Store, read at start-up, never in environment variables or Terraform state.
- **Sign-in.** Cognito user pool (admin-created users only), managed login with code + PKCE, and an API Gateway
  JWT authorizer, so unauthenticated calls never reach Lambda. Cognito only accepts HTTPS callback URLs, which
  is one reason CloudFront is required.
- **Phone import on AWS.** QR tokens live in DynamoDB (TTL) so any container can validate them, and the QR
  opens the public CloudFront URL.

## Prerequisites (one time)
1. AWS account with root MFA. Region ap-south-1.
2. A way for the CLI to sign in:
   - **IAM user** with AdministratorAccess and `aws login --profile <name>` (short-lived credentials; works on
     the AWS free plan), or
   - **IAM Identity Center** + `aws configure sso`. Note: giving an Identity Center user access to the account
     needs an *organization* instance, i.e. AWS Organizations, which moves a free-plan account to the paid
     plan. On a standalone account Identity Center can only make an account instance, which shows
     "AWS accounts (0)".
3. Tools: AWS CLI v2, Terraform ≥ 1.10 (`brew install hashicorp/tap/terraform`), Docker Desktop, Node.
4. **New accounts:** AWS blocks CloudFront until the account is verified. Open a free *Account and billing*
   support case quoting the `AccessDenied: Your account must be verified…` error before the first deploy.
   New accounts also have a Lambda concurrency limit of 10 (fine for this design, see ADR 0002).

## Deploy / remove
```bash
export AWS_PROFILE=<name>                       # aws login --profile <name> when it expires
terraform -chdir=infrastructure/bootstrap init  # once per account
terraform -chdir=infrastructure/bootstrap apply -var github_repo=<owner>/<repo>
./scripts/deploy.sh you@example.com             # Terraform shows a plan and asks before each apply
./scripts/destroy.sh                            # removes the environment, data buckets included
```
`deploy.sh`: creates the ECR repositories, builds and pushes both images, applies the rest, seeds S3 with the
local `data/processed`, `data/raw/news`, fund holdings and backtests, then builds and uploads the frontend.
A failed apply can simply be re-run: Terraform creates only what is missing.

After the first deploy: confirm the two SNS subscription emails, then create a login with
`aws cognito-idp admin-create-user --user-pool-id <user_pool_id> --username <email>` (the script prints it).

**Seeding S3 by hand** (if the deploy stopped before step 4/5, e.g. at CloudFront):
```bash
B=$(aws s3 ls | awk '/pi-dev-data/ {print $3}')
aws s3 sync data/processed "s3://$B/processed" --exclude "*.DS_Store"
aws s3 sync data/raw/news "s3://$B/raw/news" --exclude "*.DS_Store"
aws s3 sync data/raw/mutual_funds "s3://$B/raw/mutual_funds" --exclude "*.DS_Store"
aws s3 sync data/backtests "s3://$B/backtests" --exclude "*.DS_Store"
date +%s | aws s3 cp - "s3://$B/_version"
```

## CI/CD (Phase 16)
`.github/workflows/ci.yml` lints, tests and builds every push and pull request (ruff, pytest, frontend lint and
build, `terraform fmt` and `validate`). `deploy.yml` runs CI, then deploys dev on every push to `main`; prod is
deployed by hand and waits for a required reviewer. GitHub assumes the bootstrap role through OIDC (1-hour
credentials; no AWS keys in GitHub). Repository variables: `AWS_DEPLOY_ROLE_ARN`, `ALERT_EMAIL`; environments
`dev` and `prod` (required reviewers on prod).

## What has been verified
- `terraform validate` passes for the whole configuration (Terraform 1.16.5, AWS provider 5.x).
- Handlers, the DynamoDB store, S3 sync, import tokens, secrets and the FinBERT failure path are tested against
  moto (`backend/tests/test_aws.py`).
- Applied to a real account (2026-10-15/16): bootstrap, ECR, both images, all Lambdas, SQS FIFO + DLQ,
  EventBridge schedules and bus, DynamoDB, S3, SSM, alarms, dashboard and budget. CloudFront (and therefore
  Cognito's callback and the website) waits for AWS account verification.

## Deployment log: problems met and fixes
| Problem | Cause | Fix |
|---|---|---|
| Identity Center portal shows "AWS accounts (0)" | Standalone account → account instance, which cannot grant account access | IAM user + `aws login` |
| `UnreservedConcurrentExecution below its minimum value of [10]` | New-account Lambda limit is 10; reserving 1 for the scorer is refused | FIFO queue, one message group (ADR 0002) |
| `Your account must be verified before you can add new CloudFront resources` | New-account anti-abuse hold | Support case (Account and billing) |
| `terraform: command not found` via Homebrew | Terraform left homebrew-core after the licence change | `brew install hashicorp/tap/terraform` |

## Cost (dev, estimated)
About US$0.50–1.50 a month: ECR image storage dominates; Lambda stays inside the always-free 1M requests and
400,000 GB-s; S3, DynamoDB, SQS, SNS, EventBridge and API Gateway are cents; CloudFront and Cognito are within
their free tiers. Run `./scripts/destroy.sh` after the evaluation.

## Known limits (dev)
- `news_impact` and `risk_refresh` scan the UserData table (fine at dev scale; AP10's index is the upgrade).
- Load test (`scripts/loadtest/locustfile.py`): one local uvicorn worker serves single requests in 0.1–0.5 s
  but queues under 20 concurrent users (p95 several seconds on the heavy risk and recommendation pages).
  On Lambda each concurrent request gets its own container, up to the account's concurrency limit; caching
  per-portfolio results per data version is the next step for NFR2. See `docs/testing.md`.
