# Data plane: one private S3 bucket (Parquet datasets, raw files, backtests) and the UserData table.
variable "name" { type = string }

resource "aws_s3_bucket" "data" {
  bucket_prefix = "${var.name}-data-"
  force_destroy = true # dev: `terraform destroy` removes everything, data included
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

# Portfolios, risk snapshots, alerts (docs/data_model.md). On-demand: no idle cost.
resource "aws_dynamodb_table" "user_data" {
  name         = "${var.name}-UserData"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"
  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }
  ttl { # import QR tokens carry `expires`; portfolios, snapshots and alerts do not, so they are kept
    attribute_name = "expires"
    enabled        = true
  }
  point_in_time_recovery { enabled = false } # dev; enable for prod
  server_side_encryption { enabled = true }
}

output "bucket" { value = aws_s3_bucket.data.bucket }
output "bucket_arn" { value = aws_s3_bucket.data.arn }
output "table_name" { value = aws_dynamodb_table.user_data.name }
output "table_arn" { value = aws_dynamodb_table.user_data.arn }
