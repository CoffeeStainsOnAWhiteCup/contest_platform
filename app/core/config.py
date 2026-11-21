from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SYNC_DATABASE_URL: str | None = None
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    SANDBOX_CPUS: float = 0.5
    SANDBOX_PIDS_LIMIT: int = 64
    SANDBOX_TMPFS_MB: int = 64
    SANDBOX_MEMORY_OVERHEAD_MB: int = 64
    SANDBOX_JAVA_MEMORY_OVERHEAD_MB: int = 256
    SANDBOX_COMPILE_TIMEOUT_S: int = 10
    SANDBOX_MAX_OUTPUT_BYTES: int = 65536
    JUDGE_MAX_ATTEMPTS: int = 3
    JUDGE_STALE_TIMEOUT_S: int = 300

    JWT_SECRET_KEY: SecretStr
    JWT_ACCESS_TOKEN_MINUTES: int = Field(default=30, ge=1, le=1440)
    JWT_ISSUER: str = "contest-platform"
    JWT_AUDIENCE: str = "contest-platform-api"

    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: SecretStr | None = None
    GITHUB_CALLBACK_URL: str = "http://localhost:8000/api/v1/auth/github/callback"
    GITHUB_FRONTEND_URL: str = "http://localhost:5173/auth/callback"

    @field_validator("GITHUB_CALLBACK_URL", "GITHUB_FRONTEND_URL")
    @classmethod
    def validate_oauth_url(cls, value: str) -> str:
        parts = urlsplit(value)
        local = parts.hostname in {"localhost", "127.0.0.1", "::1"}
        if not parts.hostname or parts.username is not None or parts.query or parts.fragment:
            raise ValueError("Use an absolute OAuth URL without credentials, query or fragment")
        if parts.scheme != "https" and not (parts.scheme == "http" and local):
            raise ValueError("OAuth URLs require HTTPS outside localhost")
        return value

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sync_database_url(self) -> str:
        if self.SYNC_DATABASE_URL:
            return self.SYNC_DATABASE_URL
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg")

    @property
    def celery_broker_url(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def celery_result_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL


settings = Settings()
