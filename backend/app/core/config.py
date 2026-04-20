from functools import lru_cache
import json
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    app_name: str = "AGENTICA"
    environment: str = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://agentica:agentica_dev@localhost:5432/agentica"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Vector store
    qdrant_url: str = "http://localhost:6333"

    # Auth
    jwt_secret: str = "change_this_in_production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 horas

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: Optional[str] = None
    builder_model: str = "claude-sonnet-4-5"        # modelo para generar diseño y código
    builder_temperature: float = 0.2                 # baja temp para generación de código

    # Celery
    celery_broker: str = "redis://localhost:6379/1"
    celery_backend: str = "redis://localhost:6379/2"

    # CORS
    cors_origins: str | list[str] = "http://localhost:5173"

    # Agent builds
    builds_path: str = "/app/builds"
    max_eval_rounds: int = 3
    eval_pass_threshold: float = 0.75

    # Docker (para deploy de agentes)
    docker_registry: Optional[str] = None           # None = solo local
    docker_network: str = "agentica_default"

    # Twilio (WhatsApp)
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_whatsapp_number: Optional[str] = None

    # Telegram
    telegram_bot_token: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        if isinstance(self.cors_origins, list):
            return self.cors_origins

        value = self.cors_origins.strip()
        if not value:
            return []
        if value.startswith("["):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(origin) for origin in parsed]
            except json.JSONDecodeError:
                pass
        return [origin.strip() for origin in value.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
