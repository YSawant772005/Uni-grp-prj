"""Application settings loaded from environment (.env supported)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    environment: str = "local"
    api_prefix: str = "/api/v1"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = (
        "postgresql+psycopg://uni_shortlist:change_me_local_only@localhost:5433/uni_shortlist"
    )
    app_database_url: str | None = None
    unishortlist_test_mode: bool = False

    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 30
    jwt_refresh_ttl_days: int = 14
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    rate_limit_auth: str = "10/minute"

    seed_demo_data: bool = True
    enable_scheduler: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def runtime_database_url(self) -> str:
        if self.app_database_url:
            return self.app_database_url
        if self.unishortlist_test_mode:
            # Test startup has its own fail-closed TEST_DATABASE_URL identity gate.
            return self.database_url
        raise RuntimeError(
            "APP_DATABASE_URL is required for application runtime; "
            "DATABASE_URL is reserved for explicit database administration."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
