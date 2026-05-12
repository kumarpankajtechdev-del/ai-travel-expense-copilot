from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Travel & Expense Copilot"
    app_env: str = Field(default="local", alias="APP_ENV")
    policy_dir: Path = Field(default=Path("sample_data/policies"), alias="POLICY_DIR")


@lru_cache
def get_settings() -> Settings:
    return Settings()
