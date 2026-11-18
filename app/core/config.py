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
