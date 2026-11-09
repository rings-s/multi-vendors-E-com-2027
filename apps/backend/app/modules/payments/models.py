"""Payments: Payment, PaymentAllocation, PaymentProviderAccount, PaymentWebhookEvent,
Refund, Chargeback."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import BigInteger, CheckConstraint, Field, Index, Relationship, Text, UniqueConstraint, text

from app.database.base import Timestamps, UUIDPrimaryKey


class PaymentStatus(StrEnum):
    """Payment lifecycle (docs/architecture/payment-architecture.md §2.5)."""

    CREATED = "CREATED"
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"
    DISPUTED = "DISPUTED"


# Statuses meaning money was captured for the merchant order.
CAPTURED_STATUSES = (
    PaymentStatus.PAID,
    PaymentStatus.PARTIALLY_REFUNDED,
    PaymentStatus.REFUNDED,
    PaymentStatus.DISPUTED,
)


class FeeBearer(StrEnum):
    PLATFORM = "PLATFORM"
    MERCHANT = "MERCHANT"


class RecipientType(StrEnum):
    MERCHANT = "MERCHANT"
    PLATFORM = "PLATFORM"


_PAYMENT_STATUSES = ", ".join(f"'{s.value}'" for s in PaymentStatus)
_CAPTURED = ", ".join(f"'{s.value}'" for s in CAPTURED_STATUSES)


class PaymentAllocation(UUIDPrimaryKey, Timestamps, table=True):
    """How a payment's amount is distributed between recipients (integer halalas)."""

    __tablename__ = "payment_allocations"
    __table_args__ = (
        UniqueConstraint("payment_id", "recipient_type"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        CheckConstraint("delivery_amount >= 0 AND delivery_amount <= amount", name="delivery_amount_range"),
        CheckConstraint(
            "(recipient_type = 'MERCHANT' AND merchant_id IS NOT NULL) OR recipient_type = 'PLATFORM'",
            name="merchant_reference",
        ),
    )

    payment_id: uuid.UUID = Field(foreign_key="payments.id", ondelete="RESTRICT", index=True)
    recipient_type: str = Field(max_length=20)
    merchant_id: uuid.UUID | None = Field(default=None, foreign_key="merchants.id", ondelete="RESTRICT")
    recipient_id: str = Field(max_length=100)  # provider recipient identifier
    amount: int = Field(sa_type=BigInteger)
    # Part of ``amount`` that comes from the delivery charge (merchant: its delivery
    # share; platform: delivery commission or platform-received delivery fee).
    delivery_amount: int = Field(default=0, sa_type=BigInteger)
    is_fee_source: bool = False
    refundable: bool = True


class Payment(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(f"status IN ({_PAYMENT_STATUSES})", name="status_valid"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("refunded_amount >= 0 AND refunded_amount <= amount", name="refunded_range"),
        CheckConstraint("currency = 'SAR'", name="currency_sar"),
        UniqueConstraint("provider", "provider_payment_id"),
        # At most one captured payment per merchant order.
        Index(
            "uq_payments_captured_per_merchant_order",
            "merchant_order_id",
            unique=True,
            postgresql_where=text(f"status IN ({_CAPTURED}, 'AUTHORIZED')"),
        ),
    )

    order_id: uuid.UUID = Field(foreign_key="orders.id", ondelete="RESTRICT", index=True)
    merchant_order_id: uuid.UUID = Field(foreign_key="merchant_orders.id", ondelete="RESTRICT", index=True)
    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="RESTRICT", index=True)
    customer_user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    provider: str = Field(max_length=30)
    provider_payment_id: str | None = Field(default=None, max_length=100)
    # True for mock-provider and provider test-mode payments. Never real money.
    is_test: bool
    status: str = Field(default=PaymentStatus.CREATED.value, max_length=30, index=True)
    amount: int = Field(sa_type=BigInteger)  # halalas
    currency: str = Field(default="SAR", max_length=3)
    refunded_amount: int = Field(default=0, sa_type=BigInteger)
    fee: int | None = Field(default=None, sa_type=BigInteger)  # processing fee reported by the provider
    fee_bearer: str = Field(max_length=20)
    payment_method: str | None = Field(default=None, max_length=30)
    transaction_url: str | None = Field(default=None, max_length=1000)
    failure_reason: str | None = Field(default=None, sa_type=Text)
    provider_response: dict[str, object] | None = Field(default=None, sa_type=JSONB)
    paid_at: datetime | None = None
    last_synced_at: datetime | None = None

    allocations: list[PaymentAllocation] = Relationship(sa_relationship_kwargs={"lazy": "selectin"})

    @property
    def refundable_amount(self) -> int:
        return self.amount - self.refunded_amount


class PaymentProviderAccount(UUIDPrimaryKey, Timestamps, table=True):
    """The platform's own account with a payment provider (no credentials stored)."""

    __tablename__ = "payment_provider_accounts"
    __table_args__ = (UniqueConstraint("provider", "is_live"),)

    provider: str = Field(max_length=30)
    is_live: bool = False
    platform_recipient_id: str | None = Field(default=None, max_length=100)
    status: str = Field(default="CONFIGURED", max_length=30)
    capabilities: dict[str, object] = Field(default_factory=dict, sa_type=JSONB)
    notes: str | None = Field(default=None, sa_type=Text)


class WebhookEventStatus(StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    IGNORED = "IGNORED"
    FAILED = "FAILED"


class PaymentWebhookEvent(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "payment_webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_id"),)

    provider: str = Field(max_length=30)
    event_id: str = Field(max_length=100)
    event_type: str = Field(max_length=80, index=True)
    status: str = Field(default=WebhookEventStatus.RECEIVED.value, max_length=20, index=True)
    attempts: int = 0
    is_live: bool = False
    payload: dict[str, object] = Field(sa_type=JSONB)  # secrets stripped before storage
    last_error: str | None = Field(default=None, sa_type=Text)
    processed_at: datetime | None = None


class RefundStatus(StrEnum):
    REQUESTED = "REQUESTED"
    REJECTED = "REJECTED"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class RefundInitiator(StrEnum):
    CUSTOMER = "CUSTOMER"
    MERCHANT = "MERCHANT"
    PLATFORM = "PLATFORM"


class RefundScope(StrEnum):
    AUTO = "AUTO"  # items first; the delivery charge only once items are fully refunded
    ITEMS = "ITEMS"  # items only (never touches the delivery charge)
    DELIVERY = "DELIVERY"  # the delivery charge only (e.g. failed or late delivery)


# Refunds holding part of the refundable amount (prevents over-refunding).
ACTIVE_REFUND_STATUSES = (RefundStatus.PROCESSING, RefundStatus.SUCCEEDED)


class Refund(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("merchant_portion >= 0 AND platform_portion >= 0", name="portions_non_negative"),
        CheckConstraint("merchant_portion + platform_portion = amount", name="portions_sum"),
        CheckConstraint(
            "delivery_portion >= 0 AND delivery_portion <= amount"
            " AND delivery_platform_portion >= 0 AND delivery_platform_portion <= delivery_portion"
            " AND delivery_platform_portion <= platform_portion"
            " AND delivery_portion - delivery_platform_portion <= merchant_portion",
            name="delivery_portions_valid",
        ),
        CheckConstraint("scope IN ('AUTO', 'ITEMS', 'DELIVERY')", name="scope_valid"),
    )

    payment_id: uuid.UUID = Field(foreign_key="payments.id", ondelete="RESTRICT", index=True)
    merchant_order_id: uuid.UUID = Field(foreign_key="merchant_orders.id", ondelete="RESTRICT", index=True)
    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="RESTRICT", index=True)
    amount: int = Field(sa_type=BigInteger)
    merchant_portion: int = Field(sa_type=BigInteger)
    platform_portion: int = Field(sa_type=BigInteger)
    # What is being refunded: AUTO (items first, then delivery), ITEMS or DELIVERY only.
    scope: str = Field(default="AUTO", max_length=20)
    # Part of ``amount`` refunding the delivery charge, and the platform's share of it.
    delivery_portion: int = Field(default=0, sa_type=BigInteger)
    delivery_platform_portion: int = Field(default=0, sa_type=BigInteger)
    currency: str = Field(default="SAR", max_length=3)
    status: str = Field(default=RefundStatus.REQUESTED.value, max_length=20, index=True)
    initiated_by: str = Field(max_length=20)
    requested_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    reviewed_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    reason: str = Field(default="", sa_type=Text)
    restock: bool = False
    provider_reference: str | None = Field(default=None, max_length=100)
    provider_response: dict[str, object] | None = Field(default=None, sa_type=JSONB)
    failure_reason: str | None = Field(default=None, sa_type=Text)
    completed_at: datetime | None = None


class ChargebackStatus(StrEnum):
    OPEN = "OPEN"
    WON = "WON"
    LOST = "LOST"


class Chargeback(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "chargebacks"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        UniqueConstraint("payment_id", "provider_reference"),
        CheckConstraint(
            "delivery_portion >= 0 AND delivery_portion <= amount"
            " AND delivery_platform_portion >= 0 AND delivery_platform_portion <= delivery_portion",
            name="delivery_portions_valid",
        ),
    )

    payment_id: uuid.UUID = Field(foreign_key="payments.id", ondelete="RESTRICT", index=True)
    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="RESTRICT", index=True)
    amount: int = Field(sa_type=BigInteger)
    merchant_portion: int = Field(default=0, sa_type=BigInteger)
    platform_portion: int = Field(default=0, sa_type=BigInteger)
    delivery_portion: int = Field(default=0, sa_type=BigInteger)
    delivery_platform_portion: int = Field(default=0, sa_type=BigInteger)
    currency: str = Field(default="SAR", max_length=3)
    status: str = Field(default=ChargebackStatus.OPEN.value, max_length=20, index=True)
    reason: str = Field(default="", sa_type=Text)
    provider_reference: str = Field(max_length=100)
    previous_payment_status: str = Field(max_length=30)
    recorded_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    opened_at: datetime
    resolved_at: datetime | None = None
