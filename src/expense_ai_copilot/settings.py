from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="TRIPLEDGER_", extra="ignore")
    data_dir: Path = Path(".tripledger")
    provider: Literal["demo", "openai", "anthropic"] = "demo"
    model: str = ""
    api_key: SecretStr = SecretStr("")
    timeout_seconds: float = 45

    @model_validator(mode="after")
    def configured_provider(self):
        if self.provider != "demo" and (not self.model.strip() or not self.api_key.get_secret_value()):
            raise ValueError("Live mode requires TRIPLEDGER_MODEL and TRIPLEDGER_API_KEY in .env.")
        if not 1 <= self.timeout_seconds <= 120:
            raise ValueError("TRIPLEDGER_TIMEOUT_SECONDS must be between 1 and 120.")
        return self
