"""Settings from environment (frameworks layer — see ARCHITECTURE.md §1)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    # When set, the test suite runs against this database instead of `database_url`.
    # Only tests read it (see tests/conftest.py); the app never does.
    test_database_url: str = ""

    clerk_issuer: str = ""
    # Derived from the issuer when left empty (see `jwks_url`).
    clerk_jwks_url: str = ""
    clerk_secret_key: str = ""

    # Comma-separated. Kept as a plain string because pydantic-settings would otherwise
    # expect JSON for a list field.
    allowed_origins: str = "http://localhost:3000"

    environment: str = "development"

    @property
    def jwks_url(self) -> str:
        if self.clerk_jwks_url:
            return self.clerk_jwks_url
        return f"{self.clerk_issuer.rstrip('/')}/.well-known/jwks.json"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
