# Event-driven pipeline (Phase 15).
#   Scheduler → market/nav/news/holdings ingest Lambdas (IST schedules)
#   news_ingest → SQS news queue (DLQ after 3 receives) → FinBERT Lambda → "NewsScored" on the bus
#   bus rules: NewsScored → news_impact (SNS alert); MarketDataUpdated → risk_refresh
variable "name" { type = string }
variable "backend_repository_url" { type = string }
variable "image_tag" { type = string }
variable "policy_json" {
  type        = string
  description = "IAM policy of the pipeline functions (separate from the API's: least privilege, Phase 17)"
}
variable "environment" { type = map(string) }
variable "alert_email" {
  type    = string
  default = ""
}
variable "log_retention_days" {
  type    = number
  default = 14
}

resource "aws_cloudwatch_event_bus" "pipeline" { name = "${var.name}-pipeline" }

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "jobs" {
  name               = "${var.name}-jobs"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "jobs_logs" {
  role       = aws_iam_role.jobs.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "jobs" {
  role   = aws_iam_role.jobs.id
  policy = var.policy_json
}

resource "aws_sns_topic" "alerts" { name = "${var.name}-alerts" }

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email # AWS emails a confirmation link first
}

resource "aws_sqs_queue" "news_dlq" {
  name                      = "${var.name}-news-dlq"
  message_retention_seconds = 1209600 # 14 days to inspect failures
}

resource "aws_sqs_queue" "news" {
  name                       = "${var.name}-news"
  visibility_timeout_seconds = 1800 # ≥ 6 × the scorer's timeout, per AWS guidance for SQS event sources
  redrive_policy             = jsonencode({ deadLetterTargetArn = aws_sqs_queue.news_dlq.arn, maxReceiveCount = 3 })
}

# ---- FinBERT image and scorer ----
resource "aws_ecr_repository" "finbert" {
  name                 = "${var.name}-finbert"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "aws_ecr_lifecycle_policy" "finbert" {
  repository = aws_ecr_repository.finbert.name
  policy = jsonencode({ rules = [{
    rulePriority = 1, description = "keep the last 3 images",
    selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 3 },
    action       = { type = "expire" }
  }] })
}

locals {
  env = merge(var.environment, {
    EVENT_BUS        = aws_cloudwatch_event_bus.pipeline.name
    NEWS_QUEUE_URL   = aws_sqs_queue.news.url
    ALERTS_TOPIC_ARN = aws_sns_topic.alerts.arn
  })
  # function → handler, memory (MB), timeout (s); all run the backend image except news_score
  jobs = {
    market_ingest   = { memory = 1536, timeout = 600 }
    nav_ingest      = { memory = 1024, timeout = 600 }
    news_ingest     = { memory = 1024, timeout = 300 }
    holdings_ingest = { memory = 1536, timeout = 600 }
    news_impact     = { memory = 1536, timeout = 300 }
    risk_refresh    = { memory = 1536, timeout = 600 }
  }
}

resource "aws_cloudwatch_log_group" "job" {
  for_each          = merge(local.jobs, { news_score = {} })
  name              = "/aws/lambda/${var.name}-${replace(each.key, "_", "-")}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "job" {
  for_each      = local.jobs
  function_name = "${var.name}-${replace(each.key, "_", "-")}"
  role          = aws_iam_role.jobs.arn
  package_type  = "Image"
  image_uri     = "${var.backend_repository_url}:${var.image_tag}"
  architectures = ["arm64"]
  memory_size   = each.value.memory
  timeout       = each.value.timeout
  ephemeral_storage { size = 2048 }
  image_config { command = ["app.aws.handlers.${each.key}"] }
  environment { variables = local.env }
  depends_on = [aws_cloudwatch_log_group.job]
}

resource "aws_lambda_function" "news_score" {
  function_name                  = "${var.name}-news-score"
  role                           = aws_iam_role.jobs.arn
  package_type                   = "Image"
  image_uri                      = "${aws_ecr_repository.finbert.repository_url}:${var.image_tag}"
  architectures                  = ["arm64"]
  memory_size                    = 3008 # the only large function (plan §12)
  timeout                        = 300
  reserved_concurrent_executions = 1 # one writer for sentiment.parquet
  ephemeral_storage { size = 2048 }
  image_config { command = ["app.aws.handlers.news_score"] }
  environment { variables = local.env }
  depends_on = [aws_cloudwatch_log_group.job]
}

resource "aws_lambda_event_source_mapping" "news" {
  depends_on                         = [aws_iam_role_policy.jobs] # SQS polling needs the policy first
  event_source_arn                   = aws_sqs_queue.news.arn
  function_name                      = aws_lambda_function.news_score.arn
  batch_size                         = 16
  maximum_batching_window_in_seconds = 30
}

# ---- schedules (EventBridge Scheduler, IST) ----
data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.name}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

resource "aws_iam_role_policy" "scheduler" {
  role = aws_iam_role.scheduler.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect   = "Allow", Action = "lambda:InvokeFunction",
    Resource = [for f in aws_lambda_function.job : f.arn]
  }] })
}

locals {
  schedules = {
    market_ingest   = "cron(30 16 ? * MON-FRI *)" # after the 15:30 close
    nav_ingest      = "cron(30 23 * * ? *)"       # after AMFI publishes (~21:00–23:00)
    news_ingest     = "rate(30 minutes)"
    holdings_ingest = "cron(0 9 12 * ? *)" # monthly, after the ~10-day disclosure deadline
  }
}

resource "aws_scheduler_schedule" "job" {
  for_each                     = local.schedules
  name                         = "${var.name}-${replace(each.key, "_", "-")}"
  schedule_expression          = each.value
  schedule_expression_timezone = "Asia/Kolkata"
  flexible_time_window { mode = "OFF" }
  target {
    arn      = aws_lambda_function.job[each.key].arn
    role_arn = aws_iam_role.scheduler.arn
    retry_policy { maximum_retry_attempts = 2 }
  }
}

# ---- events on the pipeline bus ----
locals {
  reactions = {
    news_impact  = "NewsScored"
    risk_refresh = "MarketDataUpdated"
  }
}

resource "aws_cloudwatch_event_rule" "reaction" {
  for_each       = local.reactions
  name           = "${var.name}-${replace(each.key, "_", "-")}"
  event_bus_name = aws_cloudwatch_event_bus.pipeline.name
  event_pattern  = jsonencode({ source = ["portfolio-intelligence"], "detail-type" = [each.value] })
}

resource "aws_cloudwatch_event_target" "reaction" {
  for_each       = local.reactions
  rule           = aws_cloudwatch_event_rule.reaction[each.key].name
  event_bus_name = aws_cloudwatch_event_bus.pipeline.name
  arn            = aws_lambda_function.job[each.key].arn
}

resource "aws_lambda_permission" "reaction" {
  for_each      = local.reactions
  statement_id  = "AllowPipelineBus"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.job[each.key].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.reaction[each.key].arn
}

# Alarms (the DLQ included) are in the monitoring module.

output "finbert_repository_url" { value = aws_ecr_repository.finbert.repository_url }
output "event_bus" { value = aws_cloudwatch_event_bus.pipeline.name }
output "news_queue_url" { value = aws_sqs_queue.news.url }
output "news_queue_arn" { value = aws_sqs_queue.news.arn }
output "alerts_topic_arn" { value = aws_sns_topic.alerts.arn }
output "function_names" {
  value = merge({ for k, f in aws_lambda_function.job : k => f.function_name }, { news_score = aws_lambda_function.news_score.function_name })
}
output "news_queue_name" { value = aws_sqs_queue.news.name }
output "news_dlq_name" { value = aws_sqs_queue.news_dlq.name }
