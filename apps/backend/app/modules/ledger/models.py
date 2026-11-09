"""Double-entry ledger: LedgerAccount, LedgerTransaction, LedgerEntry, FinancialReconciliation.

Entries are immutable. The migration installs triggers that reject UPDATE and DELETE
on ``ledger_transactions`` and ``ledger_entries``; corrections are reversing entries.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import BigInteger, CheckConstraint, Field, Index, Relationship, Text, text

from app.database.base import CreatedAt, UUIDPrimaryKey


class AccountType(StrEnum):
    # Platform accounts (merchant_id IS NULL)
    PROVIDER_CLEARING = "PROVIDER_CLEARING"  # asset: funds held/routed by the provider
    PLATFORM_COMMISSION = "PLATFORM_COMMISSION"  # revenue: commission on items
    DELIVERY_COMMISSION = "DELIVERY_COMMISSION"  # revenue: commission on merchant-received delivery fees
    DELIVERY_FEE_REVENUE = "DELIVERY_FEE_REVENUE"  # revenue: delivery charges received by the platform
    PROCESSING_FEES = "PROCESSING_FEES"  # expense
    # Merchant accounts
    MERCHANT_PAYABLE = "MERCHANT_PAYABLE"  # liability: earned, not yet settled to the bank


MERCHANT_ACCOUNT_TYPES = (AccountType.MERCHANT_PAYABLE,)


class LedgerComponent(StrEnum):
    """What part of a sale an entry relates to, so delivery money stays identifiable
    inside shared accounts (e.g. a merchant's single payable balance)."""

    GOODS = "GOODS"  # items after discounts, incl. their VAT
    DELIVERY = "DELIVERY"  # delivery fee incl. its VAT


class Direction(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class LedgerTransactionType(StrEnum):
    PAYMENT_CAPTURED = "PAYMENT_CAPTURED"
    PROCESSING_FEE = "PROCESSING_FEE"
    REFUND = "REFUND"
    CHARGEBACK = "CHARGEBACK"
    CHARGEBACK_REVERSAL = "CHARGEBACK_REVERSAL"
    SETTLEMENT = "SETTLEMENT"
    REVERSAL = "REVERSAL"


class LedgerAccount(UUIDPrimaryKey, CreatedAt, table=True):
    __tablename__ = "ledger_accounts"
    __table_args__ = (
        Index(
            "uq_ledger_accounts_platform",
            "account_type",
            "currency",
            unique=True,
            postgresql_where=text("merchant_id IS NULL"),
        ),
        Index(
            "uq_ledger_accounts_merchant",
            "merchant_id",
            "account_type",
            "currency",
            unique=True,
            postgresql_where=text("merchant_id IS NOT NULL"),
        ),
        CheckConstraint(
            "(account_type = 'MERCHANT_PAYABLE') = (merchant_id IS NOT NULL)",
            name="owner_matches_type",
        ),
    )

    merchant_id: uuid.UUID | None = Field(default=None, foreign_key="merchants.id", ondelete="RESTRICT")
    currency: str = Field(default="SAR", max_length=3)
    account_type: str = Field(max_length=40)


class LedgerEntry(UUIDPrimaryKey, CreatedAt, table=True):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("direction IN ('DEBIT', 'CREDIT')", name="direction_valid"),
        CheckConstraint("component IS NULL OR component IN ('GOODS', 'DELIVERY')", name="component_valid"),
    )

    transaction_id: uuid.UUID = Field(foreign_key="ledger_transactions.id", ondelete="RESTRICT", index=True)
    account_id: uuid.UUID = Field(foreign_key="ledger_accounts.id", ondelete="RESTRICT", index=True)
    direction: str = Field(max_length=6)
    amount: int = Field(sa_type=BigInteger)
    currency: str = Field(default="SAR", max_length=3)
    # NULL for entries that are not tied to a sale component (fees, settlements).
    component: str | None = Field(default=None, max_length=20)
    description: str = Field(default="", sa_type=Text)


class LedgerTransaction(UUIDPrimaryKey, CreatedAt, table=True):
    __tablename__ = "ledger_transactions"
    __table_args__ = (
        # Idempotency: one posting per (source, type). Duplicate events never double-post.
        Index("uq_ledger_transactions_source", "source_type", "source_id", "transaction_type", unique=True),
    )

    reference: str = Field(max_length=120, unique=True)
    transaction_type: str = Field(max_length=40)
    source_type: str = Field(max_length=40)
    source_id: uuid.UUID
    status: str = Field(default="POSTED", max_length=20)
    merchant_id: uuid.UUID | None = Field(default=None, foreign_key="merchants.id", ondelete="RESTRICT", index=True)
    description: str = Field(default="", sa_type=Text)
    is_test: bool = False

    entries: list[LedgerEntry] = Relationship(sa_relationship_kwargs={"lazy": "selectin"})


class ReconciliationStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FinancialReconciliation(UUIDPrimaryKey, CreatedAt, table=True):
    __tablename__ = "financial_reconciliations"

    provider: str = Field(max_length=30)
    scope: str = Field(max_length=40)
    period_start: datetime | None = None
    period_end: datetime | None = None
    status: str = Field(default=ReconciliationStatus.RUNNING.value, max_length=20)
    checked_count: int = 0
    mismatch_count: int = 0
    applied_updates: int = 0
    details: list[dict[str, object]] = Field(default_factory=list, sa_type=JSONB)
    triggered_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    completed_at: datetime | None = None
