"""In-app notifications. Text is rendered at read time in the user's language."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Index

from app.database.base import CreatedAt, UUIDPrimaryKey


class NotificationType(StrEnum):
    MERCHANT_APPROVED = "merchant_approved"
    MERCHANT_REJECTED = "merchant_rejected"
    MERCHANT_INFO_REQUIRED = "merchant_info_required"
    ACCOUNT_SUSPENDED = "account_suspended"
    PAYMENT_SUCCEEDED = "payment_succeeded"
    PAYMENT_FAILED = "payment_failed"
    NEW_ORDER = "new_order"
    ORDER_STATUS_CHANGED = "order_status_changed"
    DELIVERY_STATUS_CHANGED = "delivery_status_changed"
    REFUND_STATUS = "refund_status"
    SETTLEMENT_COMPLETED = "settlement_completed"
    SETTLEMENT_FAILED = "settlement_failed"
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"  # noqa: S105


class Notification(UUIDPrimaryKey, CreatedAt, table=True):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_unread", "user_id", "read_at"),)

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    type: str = Field(max_length=50)
    data: dict[str, object] = Field(default_factory=dict, sa_type=JSONB)
    read_at: datetime | None = None
    email_sent_at: datetime | None = None
