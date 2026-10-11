# One-time setup per AWS account (Phase 16), applied by hand with local state:
#   terraform -chdir=infrastructure/bootstrap init
#   terraform -chdir=infrastructure/bootstrap apply -var github_repo=<owner>/<repo>
# Creates the shared Terraform state bucket, GitHub's OIDC identity provider, and the role GitHub Actions assumes
# to deploy. CI holds no long-lived AWS keys: each run gets 1-hour credentials, and only for this repository's
# dev and prod environments.
terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
}

variable "region" {
  type    = string
  default = "ap-south-1"
}
variable "github_repo" {
  type        = string
  description = "owner/name of the GitHub repository allowed to deploy"
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "portfolio-intelligence", Environment = "shared", ManagedBy = "terraform" }
  }
}

data "aws_caller_identity" "me" {}

# ---- state ----
resource "aws_s3_bucket" "state" {
  bucket = "pi-tfstate-${data.aws_caller_identity.me.account_id}"
  lifecycle { prevent_destroy = true } # losing state orphans every resource
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" } # recover from a bad apply
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---- GitHub Actions → AWS (OIDC) ----
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Only jobs bound to a GitHub environment of this repo. Protection rules on those environments (required
    # reviewers on prod) therefore gate every deploy; pull requests and forks can never assume the role.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [for e in ["dev", "prod"] : "repo:${var.github_repo}:environment:${e}"]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name                 = "pi-github-deploy"
  assume_role_policy   = data.aws_iam_policy_document.github_assume.json
  max_session_duration = 3600
}

# Terraform creates many kinds of resource, so the deployer needs broad service access (PowerUserAccess: no
# account or IAM administration). IAM is fenced to this project's role names (pi-*) and the role can't touch
# itself. Known limit: it can still write any inline policy on a pi-* role. A permissions boundary required on
# every pi-* role would close that; worth adding before this account holds anything beyond this project.
resource "aws_iam_role_policy_attachment" "power" {
  role       = aws_iam_role.deploy.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

resource "aws_iam_role_policy" "project_iam" {
  role = aws_iam_role.deploy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:TagRole", "iam:UntagRole", "iam:UpdateRole",
          "iam:UpdateAssumeRolePolicy", "iam:PassRole", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies",
          "iam:PutRolePolicy", "iam:GetRolePolicy", "iam:DeleteRolePolicy", "iam:AttachRolePolicy",
          "iam:DetachRolePolicy", "iam:ListInstanceProfilesForRole",
        ]
        Resource = "arn:aws:iam::${data.aws_caller_identity.me.account_id}:role/pi-*"
      },
      {
        Effect   = "Deny" # never modify its own trust or permissions
        Action   = ["iam:*"]
        Resource = aws_iam_role.deploy.arn
      },
    ]
  })
}

output "state_bucket" { value = aws_s3_bucket.state.bucket }
output "deploy_role_arn" { value = aws_iam_role.deploy.arn }
