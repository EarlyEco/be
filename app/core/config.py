from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HackArizona API"
    app_version: str = "0.1.0"
    debug: bool = True
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "EarlyEco"
    database_username: str = "postgres"
    database_password: str = "root"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_dsn(self) -> str:
        return (
            f"postgresql://{self.database_username}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


settings = Settings()
