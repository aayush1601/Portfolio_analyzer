"""Application settings, read from environment variables (and the repo-root .env locally).

On AWS the same variables are set on each Lambda by Terraform (infrastructure/); secrets come from SSM
Parameter Store (Phase 17).
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
