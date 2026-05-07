
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Student Progress Tracking"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://student:password@localhost:5432/progress_tracking"
    DATABASE_URL_SYNC: str = "postgresql://student:password@localhost:5432/progress_tracking"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
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
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    MAX_UPLOAD_SIZE_MB: int = 20

    # Rate Limiting (requests per minute)
    RATE_LIMIT_FREE: int = 10
    RATE_LIMIT_STANDARD: int = 100
    RATE_LIMIT_PREMIUM: int = 1000

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
