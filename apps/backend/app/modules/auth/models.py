"""Identity: User, Role, Permission, UserSession, RefreshToken, UserActionToken."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlmodel import CheckConstraint, Field, Index, Relationship, SQLModel

from app.database.base import CreatedAt, Timestamps, UUIDPrimaryKey


class RoleName(StrEnum):
    CUSTOMER = "CUSTOMER"
    MERCHANT = "MERCHANT"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"


class Language(StrEnum):
    AR = "ar"
    EN = "en"


class UserRole(SQLModel, table=True):
    __tablename__ = "user_roles"

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", primary_key=True)
    role_id: uuid.UUID = Field(foreign_key="roles.id", ondelete="RESTRICT", primary_key=True)


class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permissions"

    role_id: uuid.UUID = Field(foreign_key="roles.id", ondelete="CASCADE", primary_key=True)
    permission_id: uuid.UUID = Field(foreign_key="permissions.id", ondelete="CASCADE", primary_key=True)


class Permission(UUIDPrimaryKey, table=True):
    __tablename__ = "permissions"

    code: str = Field(max_length=100, unique=True)
    description: str = Field(default="", max_length=255)


class Role(UUIDPrimaryKey, table=True):
    __tablename__ = "roles"

    name: str = Field(max_length=50, unique=True)

    permissions: list[Permission] = Relationship(link_model=RolePermission, sa_relationship_kwargs={"lazy": "selectin"})


class User(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint("preferred_language IN ('ar', 'en')", name="preferred_language_valid"),
    )

    email: str = Field(max_length=320, unique=True)
    password_hash: str = Field(max_length=255)
    full_name: str = Field(max_length=200)
    phone: str | None = Field(default=None, max_length=20)
    is_active: bool = True
    email_verified_at: datetime | None = None
    preferred_language: str = Field(default=Language.AR.value, max_length=2)
    last_login_at: datetime | None = None

    roles: list[Role] = Relationship(link_model=UserRole, sa_relationship_kwargs={"lazy": "selectin"})

    @property
    def role_names(self) -> list[str]:
        return sorted(r.name for r in self.roles)

    @property
    def permission_codes(self) -> set[str]:
        return {p.code for r in self.roles for p in r.permissions}

    def has_role(self, *names: str) -> bool:
        return bool(set(self.role_names) & set(names))


class UserSession(UUIDPrimaryKey, CreatedAt, table=True):
    __tablename__ = "user_sessions"

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    ip_address: str | None = Field(default=None, max_length=64)
    user_agent: str | None = Field(default=None, max_length=512)
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_reason: str | None = Field(default=None, max_length=100)


class RefreshToken(UUIDPrimaryKey, CreatedAt, table=True):
    __tablename__ = "refresh_tokens"

    session_id: uuid.UUID = Field(foreign_key="user_sessions.id", ondelete="CASCADE", index=True)
    token_hash: str = Field(max_length=64, unique=True)
    expires_at: datetime
    used_at: datetime | None = None
    revoked_at: datetime | None = None


class TokenPurpose(StrEnum):
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    PASSWORD_RESET = "PASSWORD_RESET"  # noqa: S105


class UserActionToken(UUIDPrimaryKey, CreatedAt, table=True):
    """Single-use tokens for email verification and password reset (hash only)."""

    __tablename__ = "user_action_tokens"
    __table_args__ = (Index("ix_user_action_tokens_user_purpose", "user_id", "purpose"),)

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    purpose: str = Field(max_length=40)
    token_hash: str = Field(max_length=64, unique=True)
    expires_at: datetime
    used_at: datetime | None = None
