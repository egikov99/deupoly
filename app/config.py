from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Deupoly"
    api_prefix: str = "/api"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    redis_url: str = "redis://redis:6379/0"
    database_url: str = "postgresql://deupoly:deupoly@postgres:5432/deupoly"
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

