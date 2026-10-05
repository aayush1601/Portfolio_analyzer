# API: FastAPI in a container Lambda behind an API Gateway HTTP API (cheaper than REST API).
variable "name" { type = string }
variable "image_tag" { type = string }
variable "environment" { type = map(string) }
variable "policy_json" {
  type        = string
  description = "IAM policy shared by the backend functions"
}
variable "log_retention_days" {
  type    = number
  default = 14
}

resource "aws_ecr_repository" "app" {
  name                 = "${var.name}-backend"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({ rules = [{
    rulePriority = 1, description = "keep the last 5 images",
    selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 },
    action       = { type = "expire" }
  }] })
}

data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "backend" {
  name               = "${var.name}-backend"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.backend.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "backend" {
  role   = aws_iam_role.backend.id
  policy = var.policy_json
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${var.name}-api"
  retention_in_days = var.log_retention_days # default retention is forever: a classic bill trap
}

resource "aws_lambda_function" "api" {
  function_name = "${var.name}-api"
  role          = aws_iam_role.backend.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
  architectures = ["arm64"]
  memory_size   = 1536
  timeout       = 29 # API Gateway's integration limit is 30 s
  ephemeral_storage { size = 1024 }
  image_config { command = ["app.aws.handlers.api"] }
  environment { variables = var.environment }
  depends_on = [aws_cloudwatch_log_group.api]
}

resource "aws_apigatewayv2_api" "http" {
  name          = "${var.name}-http"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "all" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit = 50 # caps a runaway client's cost
    throttling_rate_limit  = 20
  }
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowHttpApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

output "repository_url" { value = aws_ecr_repository.app.repository_url }
output "role_arn" { value = aws_iam_role.backend.arn }
output "api_domain" { value = replace(aws_apigatewayv2_api.http.api_endpoint, "https://", "") }
output "api_endpoint" { value = aws_apigatewayv2_api.http.api_endpoint }
