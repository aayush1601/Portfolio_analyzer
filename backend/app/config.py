"""Application settings, read from environment variables (and the repo-root .env locally).

On AWS the same variables are set on the Lambda; secrets come from Secrets Manager (Phase 17).
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
