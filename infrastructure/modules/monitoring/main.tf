# Monitoring (Phase 17): one ops topic for alarms, an alarm per failure mode, and a CloudWatch dashboard.
# Alarms go to their own topic so they never mix with the news alerts users get on the pipeline's topic.
variable "name" { type = string }
variable "alert_email" { type = string }
variable "api_id" { type = string }
variable "functions" {
  type        = map(string)
  description = "short name → Lambda function name, the API included"
}
variable "news_queue_name" { type = string }
variable "news_dlq_name" { type = string }

data "aws_region" "here" {}

resource "aws_sns_topic" "ops" { name = "${var.name}-ops" }

resource "aws_sns_topic_subscription" "ops_email" {
  topic_arn = aws_sns_topic.ops.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

locals {
  alarm = {
    period              = 300
    evaluation_periods  = 1
    comparison_operator = "GreaterThanThreshold"
    treat_missing_data  = "notBreaching" # no traffic is not a failure
  }
}

# Any unhandled error in any function: jobs run a few times a day, so one failure is worth an email.
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each            = var.functions
  alarm_name          = "${var.name}-${replace(each.key, "_", "-")}-errors"
  alarm_description   = "${each.value} raised an error. Logs: /aws/lambda/${each.value}"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = each.value }
  statistic           = "Sum"
  threshold           = 0
  period              = local.alarm.period
  evaluation_periods  = local.alarm.evaluation_periods
  comparison_operator = local.alarm.comparison_operator
  treat_missing_data  = local.alarm.treat_missing_data
  alarm_actions       = [aws_sns_topic.ops.arn]
  ok_actions          = [aws_sns_topic.ops.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.name}-api-5xx"
  alarm_description   = "More than 5 server errors in 5 minutes from the HTTP API"
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  dimensions          = { ApiId = var.api_id }
  statistic           = "Sum"
  threshold           = 5
  period              = local.alarm.period
  evaluation_periods  = local.alarm.evaluation_periods
  comparison_operator = local.alarm.comparison_operator
  treat_missing_data  = local.alarm.treat_missing_data
  alarm_actions       = [aws_sns_topic.ops.arn]
}

# Anything in the DLQ means a batch failed 3 times.
resource "aws_cloudwatch_metric_alarm" "dlq" {
  alarm_name          = "${var.name}-news-dlq-not-empty"
  alarm_description   = "News batches failed scoring 3 times and were parked in ${var.news_dlq_name}"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = var.news_dlq_name }
  statistic           = "Maximum"
  threshold           = 0
  period              = local.alarm.period
  evaluation_periods  = local.alarm.evaluation_periods
  comparison_operator = local.alarm.comparison_operator
  treat_missing_data  = local.alarm.treat_missing_data
  alarm_actions       = [aws_sns_topic.ops.arn]
}

# The near-real-time promise: news is scored within 30 minutes of ingestion (NFR). Two periods, so one slow
# FinBERT cold start doesn't page anyone.
resource "aws_cloudwatch_metric_alarm" "news_backlog" {
  alarm_name          = "${var.name}-news-older-than-30-min"
  alarm_description   = "Unscored news has waited over 30 minutes: the near-real-time target is being missed"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  dimensions          = { QueueName = var.news_queue_name }
  statistic           = "Maximum"
  threshold           = 1800
  period              = local.alarm.period
  evaluation_periods  = 2
  comparison_operator = local.alarm.comparison_operator
  treat_missing_data  = local.alarm.treat_missing_data
  alarm_actions       = [aws_sns_topic.ops.arn]
}

locals {
  region = data.aws_region.here.name
  fns    = values(var.functions)
  widget = { type = "metric", width = 12, height = 6 }
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = var.name
  dashboard_body = jsonencode({
    widgets = [
      merge(local.widget, { x = 0, y = 0, properties = {
        title = "API requests and errors", region = local.region, stat = "Sum", period = 300,
        metrics = [
          ["AWS/ApiGateway", "Count", "ApiId", var.api_id],
          [".", "4xx", ".", "."],
          [".", "5xx", ".", "."],
        ]
      } }),
      merge(local.widget, { x = 12, y = 0, properties = {
        title   = "API latency (p95, ms)", region = local.region, stat = "p95", period = 300,
        metrics = [["AWS/ApiGateway", "Latency", "ApiId", var.api_id]]
      } }),
      merge(local.widget, { x = 0, y = 6, properties = {
        title   = "Lambda errors", region = local.region, stat = "Sum", period = 300,
        metrics = [for f in local.fns : ["AWS/Lambda", "Errors", "FunctionName", f]]
      } }),
      merge(local.widget, { x = 12, y = 6, properties = {
        title   = "Lambda duration (p95, ms)", region = local.region, stat = "p95", period = 300,
        metrics = [for f in local.fns : ["AWS/Lambda", "Duration", "FunctionName", f]]
      } }),
      merge(local.widget, { x = 0, y = 12, properties = {
        title = "News queue: waiting, oldest (s), dead letters", region = local.region, stat = "Maximum", period = 300,
        metrics = [
          ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.news_queue_name],
          [".", "ApproximateAgeOfOldestMessage", ".", ".", { yAxis = "right" }],
          [".", "ApproximateNumberOfMessagesVisible", ".", var.news_dlq_name],
        ]
      } }),
      merge(local.widget, { x = 12, y = 12, properties = {
        title   = "Lambda throttles", region = local.region, stat = "Sum", period = 300,
        metrics = [for f in local.fns : ["AWS/Lambda", "Throttles", "FunctionName", f]]
      } }),
    ]
  })
}

output "ops_topic_arn" { value = aws_sns_topic.ops.arn }
output "dashboard_url" {
  value = "https://${local.region}.console.aws.amazon.com/cloudwatch/home?region=${local.region}#dashboards:name=${var.name}"
}
