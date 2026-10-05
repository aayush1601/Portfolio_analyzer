# NFR3: dev must stay under US$5/month; email at 50%, 80% and 100% of actual spend.
variable "name" { type = string }
variable "limit_usd" {
  type    = number
  default = 5
}
variable "email" { type = string }

resource "aws_budgets_budget" "monthly" {
  name         = "${var.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.email]
    }
  }
}
