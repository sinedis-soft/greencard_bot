from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Green Card Telegram API"
    app_version: str = "0.1.0"
    bitrix24_webhook_url: str = "https://example.bitrix24.com/rest"
    default_currency: str = "USD"
    default_language: str = "en"
    mini_app_url: str = ""
    bot_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def app_root() -> Path:
    return Path(__file__).resolve().parents[1]
