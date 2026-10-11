#!/usr/bin/env bash
# Remove one environment (data buckets included). Terraform asks for "yes" first. The bootstrap stack (state
# bucket, CI role) is left alone.
#   ./scripts/destroy.sh [dev|prod]
set -euo pipefail
cd "$(dirname "$0")/.."
ENV="${1:-dev}"
REGION="${AWS_REGION:-ap-south-1}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
TF="terraform -chdir=infrastructure/environments"
$TF init -input=false -reconfigure -backend-config="bucket=pi-tfstate-$ACCOUNT" -backend-config="key=$ENV/terraform.tfstate" \
  -backend-config="region=$REGION" -backend-config="use_lockfile=true"
$TF destroy -var "env=$ENV" -var "image_tag=unused" -var "alert_email=unused@example.com" -var "region=$REGION"
