"""Customers: CustomerProfile, CustomerAddress, CustomerPreference."""

import uuid

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Index, text

from app.database.base import Timestamps, UUIDPrimaryKey


class CustomerProfile(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "customer_profiles"

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", unique=True)
    display_name: str | None = Field(default=None, max_length=200)


class CustomerAddress(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "customer_addresses"
    __table_args__ = (
        Index(
            "uq_customer_addresses_default",
            "user_id",
            unique=True,
            postgresql_where=text("is_default AND NOT is_deleted"),
        ),
    )

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    label: str = Field(default="", max_length=100)
    recipient_name: str = Field(max_length=200)
    phone: str = Field(max_length=20)
    region: str = Field(max_length=50)
    city: str = Field(max_length=100)
    district: str = Field(default="", max_length=100)
    street: str = Field(default="", max_length=200)
    building_number: str = Field(default="", max_length=20)
    postal_code: str = Field(default="", max_length=10)
    additional_info: str = Field(default="", max_length=300)
    # Optional WGS84 map pin for delivery; both set or both null (API schema + DB check).
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)
    delivery_instructions: str = Field(default="", max_length=500)
    is_default: bool = False
    # Soft deletion: past orders keep a snapshot, but the address book entry may be removed.
    is_deleted: bool = False


class CustomerPreference(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "customer_preferences"

    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", unique=True)
    marketing_emails: bool = False
    notification_settings: dict[str, bool] = Field(default_factory=dict, sa_type=JSONB)
