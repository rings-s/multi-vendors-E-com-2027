"""Settlement: bank transfer of merchant earnings, confirmed by the provider.

Payment success and bank settlement are separate events: a settlement only becomes
COMPLETED from a verified confirmation (provider webhook / provider API / audited
reconciliation against the provider's records).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import BigInteger, CheckConstraint, Field, Text, UniqueConstraint

from app.database.base import Timestamps, UUIDPrimaryKey


class SettlementStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ConfirmationSource(StrEnum):
    PROVIDER_WEBHOOK = "PROVIDER_WEBHOOK"
    PROVIDER_API = "PROVIDER_API"
    ADMIN_RECONCILIATION = "ADMIN_RECONCILIATION"


class Settlement(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "settlements"
    __table_args__ = (
        UniqueConstraint("provider", "provider_settlement_id"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("currency = 'SAR'", name="currency_sar"),
        CheckConstraint(
            "status <> 'COMPLETED' OR (completed_at IS NOT NULL AND confirmation_source IS NOT NULL"
            " AND confirmation_reference IS NOT NULL)",
            name="completed_requires_confirmation",
        ),
    )

    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="RESTRICT", index=True)
    provider: str = Field(max_length=30)
    provider_settlement_id: str = Field(max_length=100)
    amount: int = Field(sa_type=BigInteger)
    currency: str = Field(default="SAR", max_length=3)
    status: str = Field(default=SettlementStatus.PENDING.value, max_length=20, index=True)
    is_test: bool
    initiated_at: datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = Field(default=None, sa_type=Text)
    confirmation_source: str | None = Field(default=None, max_length=30)
    confirmation_reference: str | None = Field(default=None, max_length=200)
    provider_details: dict[str, object] | None = Field(default=None, sa_type=JSONB)
