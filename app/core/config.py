from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TicketFlow API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://ticketflow:ticketflow@localhost:5432/ticketflow"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"
    auto_process_tickets: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
