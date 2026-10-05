# dev environment: everything Phase 14 (API, data, web) and Phase 15 (event pipeline) need, in ap-south-1.
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
  # Local state for a single developer. For a team, move it to an S3 backend with a lock table.
}

variable "region" {
  type    = string
  default = "ap-south-1" # Mumbai: closest to NSE data and Indian users
}
variable "name" {
  type    = string
  default = "pi-dev"
}
variable "image_tag" {
  type        = string
  description = "Tag of both Lambda images, set by scripts/deploy.sh"
}
variable "alert_email" {
  type        = string
  description = "Receives budget alerts, news alerts and DLQ alarms"
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "portfolio-intelligence", Environment = "dev", ManagedBy = "terraform" }
  }
}

data "aws_caller_identity" "me" {}

module "storage" {
  source = "../../modules/storage"
  name   = var.name
}

locals {
  account = data.aws_caller_identity.me.account_id
  # Shared by the API and pipeline functions. ARNs are built from the name prefix (not module outputs) so the
  # policy can exist before the pipeline does; each statement is limited to this project's resources.
  backend_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = "${module.storage.bucket_arn}/*" },
      { Effect = "Allow", Action = ["s3:ListBucket"], Resource = module.storage.bucket_arn },
      { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:Scan", "dynamodb:DeleteItem"], Resource = module.storage.table_arn },
      { Effect = "Allow", Action = ["events:PutEvents"], Resource = "arn:aws:events:${var.region}:${local.account}:event-bus/${var.name}-pipeline" },
      { Effect = "Allow", Action = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = "arn:aws:sqs:${var.region}:${local.account}:${var.name}-news" },
      { Effect = "Allow", Action = ["sns:Publish"], Resource = "arn:aws:sns:${var.region}:${local.account}:${var.name}-alerts" },
    ]
  })
  base_env = {
    APP_ENV   = "dev"
    STORAGE   = "s3"
    S3_BUCKET = module.storage.bucket
    DDB_TABLE = module.storage.table_name
    DATA_DIR  = "/tmp/data"
    LOG_LEVEL = "INFO"
  }
}

module "api" {
  source      = "../../modules/api"
  name        = var.name
  image_tag   = var.image_tag
  policy_json = local.backend_policy
  # The API publishes nothing to the pipeline; it only needs data access.
  environment = local.base_env
}

module "pipeline" {
  source                 = "../../modules/pipeline"
  name                   = var.name
  backend_repository_url = module.api.repository_url
  image_tag              = var.image_tag
  role_arn               = module.api.role_arn
  environment            = local.base_env
  alert_email            = var.alert_email
  depends_on             = [module.api] # the shared role and its policy must exist before SQS polling starts
}

module "web" {
  source     = "../../modules/web"
  name       = var.name
  api_domain = module.api.api_domain
}

module "budget" {
  source = "../../modules/budget"
  name   = var.name
  email  = var.alert_email
}

output "url" { value = module.web.url }
output "api_endpoint" { value = module.api.api_endpoint }
output "data_bucket" { value = module.storage.bucket }
output "web_bucket" { value = module.web.bucket }
output "distribution_id" { value = module.web.distribution_id }
output "backend_repository_url" { value = module.api.repository_url }
output "finbert_repository_url" { value = module.pipeline.finbert_repository_url }
