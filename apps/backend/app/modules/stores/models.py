"""Stores: Store, StoreCategory."""

import uuid
from decimal import Decimal
from enum import StrEnum

from sqlmodel import CheckConstraint, Field, SQLModel, Text

from app.database.base import Timestamps, UUIDPrimaryKey


class StoreStatus(StrEnum):
    INACTIVE = "INACTIVE"  # not yet published / merchant not approved
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"  # set by the platform


class StoreCategory(SQLModel, table=True):
    """Categories a store is listed under (many-to-many link)."""

    __tablename__ = "store_categories"

    store_id: uuid.UUID = Field(foreign_key="stores.id", ondelete="CASCADE", primary_key=True)
    category_id: uuid.UUID = Field(foreign_key="categories.id", ondelete="CASCADE", primary_key=True)


class Store(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "stores"
    __table_args__ = (CheckConstraint("rating_avg >= 0 AND rating_avg <= 5", name="rating_range"),)

    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="RESTRICT", unique=True)
    slug: str = Field(max_length=80, unique=True)
    name: str = Field(max_length=200)
    description: str = Field(default="", sa_type=Text)
    logo_url: str | None = Field(default=None, max_length=500)
    cover_url: str | None = Field(default=None, max_length=500)
    region: str = Field(max_length=50)
    city: str = Field(max_length=100, index=True)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=20)
    status: str = Field(default=StoreStatus.INACTIVE.value, max_length=20, index=True)
    is_open: bool = True
    shipping_policy: str = Field(default="", sa_type=Text)
    return_policy: str = Field(default="", sa_type=Text)
    # Delivery fees, zones and pickup are configured in the delivery module.
    rating_avg: Decimal = Field(default=Decimal("0"), max_digits=3, decimal_places=2)
    rating_count: int = 0
    orders_count: int = 0
