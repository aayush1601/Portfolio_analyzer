# Sign-in (Phase 17): a Cognito user pool with its managed login page, and the API Gateway JWT authorizer that
# checks every API call before Lambda runs. The browser signs in with authorization code + PKCE (public client,
# no secret) and sends the access token in X-Access-Token: CloudFront does not forward Authorization to an
# uncached origin, so a custom header carries it.
variable "name" { type = string }
variable "api_id" { type = string }
variable "integration_id" { type = string }
variable "app_url" {
  type        = string
  description = "The site's https origin: where the login page returns to"
}

data "aws_caller_identity" "me" {}

resource "aws_cognito_user_pool" "users" {
  name                     = "${var.name}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # No open sign-up: this is a research system, so accounts are created by the researcher
  # (aws cognito-idp admin-create-user …) and Cognito emails a temporary password.
  admin_create_user_config { allow_admin_create_user_only = true }

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  mfa_configuration = "OPTIONAL"
  software_token_mfa_configuration { enabled = true }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}

resource "aws_cognito_user_pool_domain" "login" {
  # Globally unique per region, so the account id is part of it.
  domain       = "${var.name}-${data.aws_caller_identity.me.account_id}"
  user_pool_id = aws_cognito_user_pool.users.id
}

resource "aws_cognito_user_pool_client" "web" {
  name                                 = "${var.name}-web"
  user_pool_id                         = aws_cognito_user_pool.users.id
  generate_secret                      = false # a browser can't keep a secret; PKCE protects the code instead
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = ["${var.app_url}/"]
  logout_urls                          = ["${var.app_url}/"]
  explicit_auth_flows                  = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 7
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = var.api_id
  name             = "${var.name}-cognito"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.X-Access-Token"]
  jwt_configuration {
    issuer   = "https://${aws_cognito_user_pool.users.endpoint}"
    audience = [aws_cognito_user_pool_client.web.id] # access tokens carry it as client_id
  }
}

# Everything needs a signed-in user, except what has to work without one.
resource "aws_apigatewayv2_route" "private" {
  api_id             = var.api_id
  route_key          = "$default"
  target             = "integrations/${var.integration_id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

locals {
  public_routes = {
    health        = "GET /health"                 # uptime checks
    import_status = "GET /import/session/{token}" # the phone checks its link
    import_upload = "POST /import"                # the phone uploads; the single-use token names the account
  }
}

resource "aws_apigatewayv2_route" "public" {
  for_each  = local.public_routes
  api_id    = var.api_id
  route_key = each.value
  target    = "integrations/${var.integration_id}"
}

output "user_pool_id" { value = aws_cognito_user_pool.users.id }
output "client_id" { value = aws_cognito_user_pool_client.web.id }
output "login_domain" { value = "https://${aws_cognito_user_pool_domain.login.domain}.auth.${data.aws_region.here.name}.amazoncognito.com" }

data "aws_region" "here" {}
