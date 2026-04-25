from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HackArizona API"
    app_version: str = "0.1.0"
    debug: bool = True
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "EarlyEco"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
