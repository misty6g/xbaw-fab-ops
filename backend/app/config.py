"""Runtime settings.

Environment variables use the field name in upper case, for example
``DATABASE_URL`` and ``SEED_ON_STARTUP``.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./xbaw.db"
    seed_on_startup: bool = True
    simulator_enabled: bool = False
    simulator_interval_seconds: float = 12.0
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
