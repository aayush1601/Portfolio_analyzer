#!/usr/bin/env bash
# Deploy the dev environment (Phase 14/15) to your AWS account. Needs: aws CLI with credentials, Terraform,
# Docker (running), Node. Terraform shows its plan and waits for you to type "yes" before changing anything.
#   ./scripts/deploy.sh you@example.com
set -euo pipefail
cd "$(dirname "$0")/.."
EMAIL="${1:?usage: scripts/deploy.sh <alert email>}"
REGION="${AWS_REGION:-ap-south-1}"
TAG="$(git rev-parse --short HEAD)-$(date +%Y%m%d%H%M%S)"
TF="terraform -chdir=infrastructure/environments/dev"
VARS=(-var "image_tag=$TAG" -var "alert_email=$EMAIL" -var "region=$REGION")

for tool in aws terraform docker npm; do command -v "$tool" >/dev/null || { echo "missing: $tool"; exit 1; }; done
aws sts get-caller-identity >/dev/null || { echo "AWS credentials not set: run 'aws configure' or 'aws login'"; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker isn't running: start Docker Desktop"; exit 1; }

echo "1/5 Image registries"
$TF init -input=false
$TF apply "${VARS[@]}" -target=module.api.aws_ecr_repository.app -target=module.pipeline.aws_ecr_repository.finbert
BACKEND_REPO="$($TF output -raw backend_repository_url 2>/dev/null || aws ecr describe-repositories --region "$REGION" --repository-names pi-dev-backend --query 'repositories[0].repositoryUri' --output text)"
FINBERT_REPO="$(aws ecr describe-repositories --region "$REGION" --repository-names pi-dev-finbert --query 'repositories[0].repositoryUri' --output text)"

echo "2/5 Build and push the Lambda images (arm64; FinBERT is ~2 GB, the first push takes a while)"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${BACKEND_REPO%%/*}"
docker buildx build --platform linux/arm64 --provenance=false -f docker/lambda.Dockerfile -t "$BACKEND_REPO:$TAG" --push .
docker buildx build --platform linux/arm64 --provenance=false -f docker/lambda-finbert.Dockerfile -t "$FINBERT_REPO:$TAG" --push .

echo "3/5 Everything else (API, pipeline, CloudFront, budget)"
$TF apply "${VARS[@]}"
DATA="$($TF output -raw data_bucket)"; WEB="$($TF output -raw web_bucket)"; DIST="$($TF output -raw distribution_id)"

echo "4/5 Seed S3 with the local data (prices, NAVs, news, sentiment, predictions)"
aws s3 sync data/processed "s3://$DATA/processed" --exclude "*.DS_Store"
aws s3 sync data/raw/news "s3://$DATA/raw/news" --exclude "*.DS_Store"
[ -d data/backtests ] && aws s3 sync data/backtests "s3://$DATA/backtests" --exclude "*.DS_Store"
date +%s | aws s3 cp - "s3://$DATA/_version"

echo "5/5 Frontend"
(cd frontend && npm ci --silent && npm run build)
aws s3 sync frontend/dist "s3://$WEB" --delete
aws cloudfront create-invalidation --distribution-id "$DIST" --paths "/*" >/dev/null

echo "Done: $($TF output -raw url)"
echo "Confirm the SNS subscription email AWS sent to $EMAIL to receive alerts."
