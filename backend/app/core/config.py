
import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Student Progress Tracking"
    APP_ENV: str = "production"
    DEBUG: bool = False
    SECRET_KEY: str  # Security fix V-001: no default, must be set via env
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://student:password@localhost:5432/progress_tracking"
    DATABASE_URL_SYNC: str = "postgresql://student:password@localhost:5432/progress_tracking"

    # Redis (supports password auth via standard URL: redis://:password@host:port/db)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None

    # MinIO — no weak defaults, provide via environment when using MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str | None = None
    MINIO_SECRET_KEY: str | None = None
    MINIO_BUCKET_NAME: str = "student-progress"
    MINIO_SECURE: bool = False

    # AI
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_GATEWAY_URL: str | None = None
    OPENAI_API_KEY: str | None = None
    DASHSCOPE_API_KEY: str | None = None
    MATHPIX_APP_ID: str | None = None
    MATHPIX_API_KEY: str | None = None
    OLLAMA_BASE_URL: str | None = None

    # Embedding
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Security
    MASKING_ENABLED: bool = True
    ALLOWED_ORIGINS: str = ""
    MAX_UPLOAD_SIZE_MB: int = 20

    # Rate Limiting (requests per minute)
    RATE_LIMIT_FREE: int = 10
    RATE_LIMIT_STANDARD: int = 100
    RATE_LIMIT_PREMIUM: int = 1000

    @model_validator(mode='after')
    def validate_secret_key(self) -> 'Settings':
        # Security fix V-001: enforce strong SECRET_KEY at startup
        key = self.SECRET_KEY
        weak_values = {
            "change-me", "change-me-in-production", "secret", "admin",
            "password", "123456", "default", "key", "supersecret",
        }
        if len(key.encode('utf-8')) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 bytes long. "
                "Please set a strong SECRET_KEY environment variable."
            )
        if key.lower() in weak_values:
            raise ValueError(
                "SECRET_KEY is too weak or is a known default value. "
                "Please set a strong random SECRET_KEY environment variable."
            )
        return self

    @model_validator(mode='after')
    def validate_debug_in_production(self) -> 'Settings':
        # Security: warn if DEBUG is enabled in production
        if self.APP_ENV == "production" and self.DEBUG:
            logger.warning(
                "SECURITY WARNING: DEBUG mode is enabled in production environment. "
                "This exposes sensitive information and should be disabled immediately."
            )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
