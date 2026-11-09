import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.validators import SaudiMobile

Password = Annotated[str, Field(min_length=10, max_length=128)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    full_name: str = Field(min_length=2, max_length=200)
    phone: SaudiMobile | None = None
    preferred_language: Literal["ar", "en"] = "ar"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    # Browser clients send the refresh token as an HTTP-only cookie; other clients may use the body.
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int
    refresh_token: str | None = None  # only returned when not using cookies
    user: "UserPublic"


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    roles: list[str]
    preferred_language: str
    email_verified: bool
    created_at: datetime


class TokenRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class EmailRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: Password


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    last_seen_at: datetime | None
    current: bool = False


class CsrfResponse(BaseModel):
    csrf_token: str


class MessageResponse(BaseModel):
    message: str
