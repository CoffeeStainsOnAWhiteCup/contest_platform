import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from app.models.models import UserRole


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        # Account identifiers in this application are case-insensitive.
        return value.strip().lower() if isinstance(value, str) else value


class RegisterRequest(EmailInput):
    name: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(
        min_length=8, max_length=128,
        description="8–128 characters, including at least one letter and one decimal digit",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: SecretStr) -> SecretStr:
        """Enforce FR-AUTH-03 for new passwords without modifying them."""
        password = value.get_secret_value()
        if not any(char.isalpha() for char in password) or not any(
            char.isdecimal() for char in password
        ):
            raise ValueError("Password must contain at least one letter and one digit")
        return value

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class LoginRequest(EmailInput):
    password: SecretStr = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    role: UserRole


class TokenResponse(BaseModel):
    refresh_token: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: SecretStr = Field(min_length=1, max_length=128)
