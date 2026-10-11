#!/usr/bin/env bash
# Deploy one environment from your laptop (CI does the same in .github/workflows/deploy.yml). Needs: aws CLI with
# credentials, Terraform >= 1.10, Docker (running), Node. Terraform shows its plan and waits for "yes".
#   ./scripts/deploy.sh you@example.com [dev|prod]
# First time in an account: apply infrastructure/bootstrap once (state bucket + CI role), see docs/deployment.md.
set -euo pipefail
cd "$(dirname "$0")/.."
EMAIL="${1:?usage: scripts/deploy.sh <alert email> [dev|prod]}"
ENV="${2:-dev}"
REGION="${AWS_REGION:-ap-south-1}"
TAG="$(git rev-parse --short HEAD)-$(date +%Y%m%d%H%M%S)"
TF="terraform -chdir=infrastructure/environments"
VARS=(-var "env=$ENV" -var "image_tag=$TAG" -var "alert_email=$EMAIL" -var "region=$REGION")

for tool in aws terraform docker npm; do command -v "$tool" >/dev/null || { echo "missing: $tool"; exit 1; }; done
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)" || { echo "AWS credentials not set: run 'aws configure' or 'aws login'"; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker isn't running: start Docker Desktop"; exit 1; }
aws s3api head-bucket --bucket "pi-tfstate-$ACCOUNT" 2>/dev/null || { echo "No state bucket: apply infrastructure/bootstrap first (docs/deployment.md)"; exit 1; }

echo "1/5 Image registries ($ENV)"
$TF init -input=false -reconfigure -backend-config="bucket=pi-tfstate-$ACCOUNT" -backend-config="key=$ENV/terraform.tfstate" \
  -backend-config="region=$REGION" -backend-config="use_lockfile=true"
$TF apply "${VARS[@]}" -target=module.api.aws_ecr_repository.app -target=module.pipeline.aws_ecr_repository.finbert
BACKEND_REPO="$($TF output -raw backend_repository_url 2>/dev/null || aws ecr describe-repositories --region "$REGION" --repository-names "pi-$ENV-backend" --query 'repositories[0].repositoryUri' --output text)"
FINBERT_REPO="$(aws ecr describe-repositories --region "$REGION" --repository-names "pi-$ENV-finbert" --query 'repositories[0].repositoryUri' --output text)"

echo "2/5 Build and push the Lambda images (arm64; FinBERT is ~2 GB, the first push takes a while)"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${BACKEND_REPO%%/*}"
docker buildx build --platform linux/arm64 --provenance=false -f docker/lambda.Dockerfile -t "$BACKEND_REPO:$TAG" --push .
docker buildx build --platform linux/arm64 --provenance=false -f docker/lambda-finbert.Dockerfile -t "$FINBERT_REPO:$TAG" --push .

echo "3/5 Everything else (API, pipeline, CloudFront, sign-in, monitoring, budget)"
$TF apply "${VARS[@]}"
DATA="$($TF output -raw data_bucket)"; WEB="$($TF output -raw web_bucket)"; DIST="$($TF output -raw distribution_id)"

echo "4/5 Seed S3 with the local data (prices, NAVs, news, sentiment, predictions, fund holdings)"
aws s3 sync data/processed "s3://$DATA/processed" --exclude "*.DS_Store"
aws s3 sync data/raw/news "s3://$DATA/raw/news" --exclude "*.DS_Store"
[ -d data/raw/mutual_funds ] && aws s3 sync data/raw/mutual_funds "s3://$DATA/raw/mutual_funds" --exclude "*.DS_Store"
[ -d data/backtests ] && aws s3 sync data/backtests "s3://$DATA/backtests" --exclude "*.DS_Store"
date +%s | aws s3 cp - "s3://$DATA/_version"

echo "5/5 Frontend (signs in through Cognito)"
(cd frontend && npm ci --silent && VITE_COGNITO_DOMAIN="$($TF output -raw login_domain)" \
  VITE_COGNITO_CLIENT_ID="$($TF output -raw client_id)" npm run build)
aws s3 sync frontend/dist "s3://$WEB" --delete
aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/*" >/dev/null

echo "Done: $($TF output -raw url)"
echo "Dashboard: $($TF output -raw dashboard_url)"
echo "Confirm the two SNS subscription emails AWS sent to $EMAIL (news alerts, ops alarms)."
echo "Create a login: aws cognito-idp admin-create-user --user-pool-id $($TF output -raw user_pool_id) --username you@example.com"
