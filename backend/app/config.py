"""Application settings, read from environment variables (and the repo-root .env locally).

On AWS the same variables are set on each Lambda by Terraform (infrastructure/). Secrets never sit in Lambda
environment variables: they are SecureString parameters under SSM_SECRETS_PATH, read once per container
(Phase 17; Parameter Store rather than Secrets Manager because it is free at this scale, plan §12).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_env: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"
    data_dir: Path = REPO_ROOT / "data"
    config_dir: Path = REPO_ROOT / "config"
    cors_origins: list[str] = ["http://localhost:5173"]
    alphavantage_api_key: SecretStr | None = None

    # AWS (Phase 14/15). Locally storage is "local": data_dir on disk, portfolios as JSON files.
    # On Lambda storage is "s3": data is synced from s3_bucket into /tmp and portfolios live in DynamoDB.
    storage: Literal["local", "s3"] = "local"
    s3_bucket: str | None = None
    ddb_table: str | None = None  # UserData table
    event_bus: str | None = None  # custom EventBridge bus for pipeline events
    news_queue_url: str | None = None
    alerts_topic_arn: str | None = None
    backtest_function: str | None = None  # Lambda that runs backtests (longer than API Gateway's 30 s limit)

    # Phase 17. auth_required: refuse requests without a verified Cognito identity (set on AWS).
    auth_required: bool = False
    ssm_secrets_path: str | None = None  # e.g. /pi-dev/secrets/ → alphavantage_api_key


def ssm_secrets(path: str) -> dict[str, str]:
    """SecureString parameters under `path`, keyed by their lower-cased last segment."""
    import boto3

    # Ask without the trailing slash: IAM matches the requested path exactly (infrastructure/environments).
    paginator = boto3.client("ssm").get_paginator("get_parameters_by_path")
    pages = paginator.paginate(Path=path.rstrip("/") or "/", WithDecryption=True)
    # Terraform creates each parameter with the placeholder "unset"; the real value is put by hand.
    params = [p for page in pages for p in page["Parameters"] if p["Value"] != "unset"]
    return {p["Name"].rsplit("/", 1)[-1].lower(): p["Value"] for p in params}


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.ssm_secrets_path:
        found = ssm_secrets(s.ssm_secrets_path)
        s = Settings(**{k: v for k, v in found.items() if k in Settings.model_fields})
    return s
