from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EarlyEco API"
    app_version: str = "0.1.0"
    debug: bool = False
    mongodb_uri: str
    mongodb_db_name: str
    jwt_algorithm: str = "HS256"
    session_timeout_minutes: int = 60
    llm_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file="environment.env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )


def try_load_settings() -> Settings | None:
    try:
        return Settings()
    except ValidationError:
        return None


def get_settings() -> Settings:
    settings = try_load_settings()
    if not settings:
        raise RuntimeError("Missing required configuration (set MONGODB_URI and MONGODB_DB_NAME).")
    return settings
