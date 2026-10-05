#!/usr/bin/env bash
# Remove the whole dev environment (data buckets included). Terraform asks for "yes" first.
set -euo pipefail
cd "$(dirname "$0")/.."
terraform -chdir=infrastructure/environments/dev destroy -var "image_tag=unused" -var "alert_email=${1:-unused@example.com}"
