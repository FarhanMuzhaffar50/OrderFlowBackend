from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "OrderFlow"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://orderflow:orderflow@localhost:5432/orderflow"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = Field(default="local-development-secret-change-me-32chars")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    payment_provider_url: str = "http://localhost:8001"
    webhook_secret: str = "local-webhook-secret-change-me"
    log_level: str = "INFO"
    product_cache_seconds: int = 300
    login_rate_limit: int = 10
    checkout_rate_limit: int = 20

    @field_validator("jwt_secret")
    @classmethod
    def secure_production_secret(cls, value: str, info):
        if info.data.get("environment") == "production" and len(value) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters in production")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
