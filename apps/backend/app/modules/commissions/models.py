"""Commissions: CommissionRule (the "Commission" entity) and CommissionTransaction.

Rules are never edited in place. A change closes the current rule (``effective_to``)
and creates a new one, which keeps a full commission history. Orders snapshot the
rule applied to each line, so later changes never affect existing orders.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlmodel import BigInteger, CheckConstraint, Field, Text

from app.database.base import CreatedAt, UUIDPrimaryKey


class CommissionScope(StrEnum):
    GLOBAL = "GLOBAL"
    CATEGORY = "CATEGORY"
    MERCHANT = "MERCHANT"


class CommissionRateType(StrEnum):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"  # fixed halalas per unit sold, where contractually supported


class CommissionRule(UUIDPrimaryKey, CreatedAt, table=True):
    __tablename__ = "commission_rules"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'GLOBAL' AND merchant_id IS NULL AND category_id IS NULL)"
            " OR (scope = 'CATEGORY' AND category_id IS NOT NULL AND merchant_id IS NULL)"
            " OR (scope = 'MERCHANT' AND merchant_id IS NOT NULL AND category_id IS NULL)",
            name="scope_target",
        ),
        CheckConstraint(
            "(rate_type = 'PERCENTAGE' AND rate IS NOT NULL AND rate >= 0 AND rate <= 100 AND fixed_amount IS NULL)"
            " OR (rate_type = 'FIXED' AND fixed_amount IS NOT NULL AND fixed_amount >= 0 AND rate IS NULL)",
            name="rate_valid",
        ),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="effective_range"),
    )

    scope: str = Field(max_length=20, index=True)
    merchant_id: uuid.UUID | None = Field(default=None, foreign_key="merchants.id", ondelete="RESTRICT", index=True)
    category_id: uuid.UUID | None = Field(default=None, foreign_key="categories.id", ondelete="RESTRICT", index=True)
    rate_type: str = Field(max_length=20)
    rate: Decimal | None = Field(default=None, max_digits=6, decimal_places=3)  # percent, e.g. 10.000
    fixed_amount: int | None = Field(default=None, sa_type=BigInteger)  # halalas per unit
    effective_from: datetime
    effective_to: datetime | None = None
    created_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    note: str | None = Field(default=None, sa_type=Text)


class CommissionTransaction(UUIDPrimaryKey, CreatedAt, table=True):
    """Commission record per merchant order (immutable snapshot at checkout)."""

    __tablename__ = "commission_transactions"
    __table_args__ = (
        CheckConstraint("commission_amount >= 0 AND commission_amount <= gross_amount", name="commission_range"),
        CheckConstraint(
            "delivery_fee >= 0 AND delivery_commission_amount >= 0 AND delivery_commission_amount <= delivery_fee"
            " AND platform_delivery_amount >= 0",
            name="delivery_amounts_valid",
        ),
        CheckConstraint(
            "seller_net_amount = gross_amount - commission_amount - delivery_commission_amount"
            " - platform_delivery_amount"
            " - CASE WHEN fee_bearer = 'MERCHANT' THEN COALESCE(processing_fee, 0) ELSE 0 END",
            name="net_consistent",
        ),
    )

    order_id: uuid.UUID = Field(foreign_key="orders.id", ondelete="RESTRICT", index=True)
    merchant_order_id: uuid.UUID = Field(foreign_key="merchant_orders.id", ondelete="RESTRICT", unique=True)
    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="RESTRICT", index=True)
    currency: str = Field(default="SAR", max_length=3)
    gross_amount: int = Field(sa_type=BigInteger)  # merchant order total paid by the customer
    commission_base: int = Field(sa_type=BigInteger)  # items after discounts (excl. VAT and delivery)
    commission_rate: Decimal = Field(max_digits=8, decimal_places=4)  # effective % of commission_base
    commission_amount: int = Field(sa_type=BigInteger)  # commission on items only
    # Delivery is reported separately and never folded into the item commission.
    delivery_fee: int = Field(default=0, sa_type=BigInteger)  # excl. VAT
    delivery_commission_rate: Decimal | None = Field(default=None, max_digits=6, decimal_places=3)
    delivery_commission_amount: int = Field(default=0, sa_type=BigInteger)
    platform_delivery_amount: int = Field(default=0, sa_type=BigInteger)  # delivery charge received by the platform
    processing_fee: int | None = Field(default=None, sa_type=BigInteger)
    fee_bearer: str = Field(max_length=20)
    seller_net_amount: int = Field(sa_type=BigInteger)
