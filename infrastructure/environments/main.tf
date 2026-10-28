# One root for both environments, chosen with -var env=dev|prod. Each has its own state file
# (s3://pi-tfstate-<account>/<env>/terraform.tfstate) and its own resources (prefix pi-<env>), so
# applying dev can never touch prod. scripts/deploy.sh and .github/workflows/deploy.yml pass the backend config.
terraform {
  required_version = ">= 1.10" # S3-native state locking (use_lockfile)
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
  backend "s3" {} # bucket, key, region and use_lockfile come from -backend-config (infrastructure/bootstrap)
}

variable "env" {
  type = string
  validation {
    condition     = contains(["dev", "prod"], var.env)
    error_message = "env is dev or prod."
  }
}
variable "region" {
  type    = string
  default = "ap-south-1" # Mumbai: closest to NSE data and Indian users
}
variable "image_tag" {
  type        = string
  description = "Tag of both Lambda images, set by scripts/deploy.sh or CI"
}
variable "alert_email" {
  type        = string
  description = "Receives budget alerts, news alerts and ops alarms"
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "portfolio-intelligence", Environment = var.env, ManagedBy = "terraform" }
  }
}

data "aws_caller_identity" "me" {}

locals {
  name    = "pi-${var.env}"
  account = data.aws_caller_identity.me.account_id
  secrets = "/${local.name}/secrets/"
}

module "storage" {
  source = "../modules/storage"
  name   = local.name
}

# Secrets (Phase 17): SecureString parameters, read by the app at start-up (app/config.py). Terraform only
# creates the slot; the value is put by hand so it never enters state or git:
#   aws ssm put-parameter --overwrite --type SecureString --name /pi-dev/secrets/ALPHAVANTAGE_API_KEY --value …
resource "aws_ssm_parameter" "secret" {
  for_each = toset(["ALPHAVANTAGE_API_KEY"])
  name     = "${local.secrets}${each.key}"
  type     = "SecureString"
  value    = "unset"
  lifecycle { ignore_changes = [value] }
}

locals {
  # Least privilege (Phase 17): two roles. ARNs are built from the name prefix so the policies can exist
  # before the resources they name; every statement is limited to this environment's resources.
  data_access = [
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = "${module.storage.bucket_arn}/*" },
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = module.storage.bucket_arn },
    # IAM matches the path exactly as requested, with or without the trailing slash, so allow both spellings.
    { Effect = "Allow", Action = ["ssm:GetParametersByPath"], Resource = [for p in [trimsuffix(local.secrets, "/"), local.secrets] : "arn:aws:ssm:${var.region}:${local.account}:parameter${p}"] },
  ]
  # The API reads and writes one user's items at a time: no Scan, no pipeline access.
  api_policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(local.data_access, [
      { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"], Resource = module.storage.table_arn },
      { Effect = "Allow", Action = ["lambda:InvokeFunction"], Resource = "arn:aws:lambda:${var.region}:${local.account}:function:${local.name}-backtest" },
    ])
  })
  # The jobs walk every portfolio (Scan) and drive the event pipeline.
  jobs_policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(local.data_access, [
      { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:Scan"], Resource = module.storage.table_arn },
      { Effect = "Allow", Action = ["events:PutEvents"], Resource = "arn:aws:events:${var.region}:${local.account}:event-bus/${local.name}-pipeline" },
      { Effect = "Allow", Action = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = "arn:aws:sqs:${var.region}:${local.account}:${local.name}-news.fifo" },
      { Effect = "Allow", Action = ["sns:Publish"], Resource = "arn:aws:sns:${var.region}:${local.account}:${local.name}-alerts" },
    ])
  })
  base_env = {
    APP_ENV          = var.env
    STORAGE          = "s3"
    S3_BUCKET        = module.storage.bucket
    DDB_TABLE        = module.storage.table_name
    DATA_DIR         = "/tmp/data"
    LOG_LEVEL        = "INFO"
    SSM_SECRETS_PATH = local.secrets
  }
}

module "api" {
  source      = "../modules/api"
  name        = local.name
  image_tag   = var.image_tag
  policy_json = local.api_policy
  environment = merge(local.base_env, { AUTH_REQUIRED = "true", BACKTEST_FUNCTION = "${local.name}-backtest" })
}

module "pipeline" {
  source                 = "../modules/pipeline"
  name                   = local.name
  backend_repository_url = module.api.repository_url
  image_tag              = var.image_tag
  policy_json            = local.jobs_policy
  environment            = local.base_env
  alert_email            = var.alert_email
}

module "web" {
  source     = "../modules/web"
  name       = local.name
  api_domain = module.api.api_domain
}

module "auth" {
  source         = "../modules/auth"
  name           = local.name
  api_id         = module.api.api_id
  integration_id = module.api.integration_id
  app_url        = module.web.url
}

module "monitoring" {
  source          = "../modules/monitoring"
  name            = local.name
  alert_email     = var.alert_email
  api_id          = module.api.api_id
  functions       = merge(module.pipeline.function_names, { api = module.api.function_name })
  news_queue_name = module.pipeline.news_queue_name
  news_dlq_name   = module.pipeline.news_dlq_name
}

module "budget" {
  source = "../modules/budget"
  name   = local.name
  email  = var.alert_email
}

output "url" { value = module.web.url }
output "api_endpoint" { value = module.api.api_endpoint }
output "data_bucket" { value = module.storage.bucket }
output "web_bucket" { value = module.web.bucket }
output "distribution_id" { value = module.web.distribution_id }
output "backend_repository_url" { value = module.api.repository_url }
output "finbert_repository_url" { value = module.pipeline.finbert_repository_url }
output "user_pool_id" { value = module.auth.user_pool_id }
output "login_domain" { value = module.auth.login_domain }
output "client_id" { value = module.auth.client_id }
output "dashboard_url" { value = module.monitoring.dashboard_url }
