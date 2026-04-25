from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EarlyEco API"
    app_version: str = "0.1.0"
    debug: bool = False
    mongodb_uri: str
    mongodb_db_name: str
    jwt_algorithm: str = "HS256"
    session_timeout_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file="environment.env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
