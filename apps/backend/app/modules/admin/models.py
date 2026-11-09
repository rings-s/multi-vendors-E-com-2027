"""Administration: AuditLog, PlatformSetting, SupportTicket."""

import uuid
from enum import StrEnum

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Index, Text

from app.database.base import CreatedAt, Timestamps, UUIDPrimaryKey


class AuditLog(UUIDPrimaryKey, CreatedAt, table=True):
    """Append-only (UPDATE/DELETE rejected by a database trigger)."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_entity", "entity_type", "entity_id"),)

    actor_user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL", index=True)
    action: str = Field(max_length=100, index=True)
    entity_type: str = Field(max_length=60)
    entity_id: str | None = Field(default=None, max_length=100)
    before: dict[str, object] | None = Field(default=None, sa_type=JSONB)
    after: dict[str, object] | None = Field(default=None, sa_type=JSONB)
    ip_address: str | None = Field(default=None, max_length=64)


class PlatformSetting(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "platform_settings"

    key: str = Field(max_length=60, unique=True)
    value: dict[str, object] = Field(sa_type=JSONB)
    updated_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class SupportTicket(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "support_tickets"

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    merchant_order_id: uuid.UUID | None = Field(default=None, foreign_key="merchant_orders.id", ondelete="SET NULL")
    subject: str = Field(max_length=200)
    body: str = Field(sa_type=Text)
    status: str = Field(default=TicketStatus.OPEN.value, max_length=20, index=True)
    admin_response: str | None = Field(default=None, sa_type=Text)
