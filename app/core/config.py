from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str 
    JWT_SECRET_KEY: SecretStr
    JWT_ACCESS_TOKEN_MINUTES: int = Field(default=30, ge=1, le=1440)
    JWT_ISSUER: str = "contest-platform"
    JWT_AUDIENCE: str = "contest-platform-api"

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
