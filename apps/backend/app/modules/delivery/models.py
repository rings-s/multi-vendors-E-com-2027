"""Delivery: StoreDeliverySettings, DeliveryZone, Delivery, DeliveryEvent.

* ``DeliveryZone`` — where a store delivers, for how much and how fast.
* ``Delivery`` — the fulfillment record of one merchant order (one per merchant order
  that contains items needing delivery or pickup). It snapshots the address, zone,
  pickup point and promised times at checkout, so later configuration changes never
  alter an existing order.
* ``DeliveryEvent`` — append-only status timeline of a delivery.

Money for delivery (fee, VAT, commission, recipient, cost bearer) is part of the
merchant order's financial snapshot (``orders.models.MerchantOrder``); this module
only stores operational data.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import BigInteger, CheckConstraint, Field, Text

from app.database.base import CreatedAt, Timestamps, UUIDPrimaryKey


class DeliveryMethod(StrEnum):
    """How the customer receives a merchant order (chosen at checkout)."""

    NONE = "NONE"  # nothing to deliver (service-only merchant orders)
    DELIVERY = "DELIVERY"  # delivered to the customer's address
    PICKUP = "PICKUP"  # collected by the customer at a pickup point


class DeliveryStatus(StrEnum):
    PENDING = "PENDING"  # awaiting payment or the merchant's confirmation
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"  # for pickup: collected by the customer
    FAILED = "FAILED"  # attempt failed / not collected; can be retried
    CANCELLED = "CANCELLED"


TERMINAL_DELIVERY_STATUSES = frozenset({DeliveryStatus.DELIVERED, DeliveryStatus.CANCELLED})


class FeeRecipient(StrEnum):
    """Who receives the delivery fee the customer pays."""

    MERCHANT = "MERCHANT"
    PLATFORM = "PLATFORM"


class CostBearer(StrEnum):
    """Who is responsible for the cost of performing the delivery (incl. waived fees)."""

    MERCHANT = "MERCHANT"
    PLATFORM = "PLATFORM"
    CUSTOMER = "CUSTOMER"  # pickup: the customer travels to the pickup point


class EventSource(StrEnum):
    CUSTOMER = "CUSTOMER"
    MERCHANT = "MERCHANT"
    PLATFORM = "PLATFORM"
    SYSTEM = "SYSTEM"
    PROVIDER = "PROVIDER"  # reserved for delivery provider webhooks


class StoreDeliverySettings(UUIDPrimaryKey, Timestamps, table=True):
    """Which fulfillment methods a store offers. Missing row = defaults below."""

    __tablename__ = "store_delivery_settings"
    __table_args__ = (
        CheckConstraint(
            "pickup_preparation_minutes >= 0 AND pickup_preparation_minutes <= 43200", name="preparation_range"
        ),
    )

    store_id: uuid.UUID = Field(foreign_key="stores.id", ondelete="CASCADE", unique=True)
    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="CASCADE", index=True)
    delivery_enabled: bool = True  # merchant-managed delivery within the store's zones
    pickup_enabled: bool = False  # customer pickup at the store's pickup locations
    pickup_preparation_minutes: int = 120  # time until a pickup order is usually ready
    delivery_policy: str = Field(default="", sa_type=Text)


class DeliveryZone(UUIDPrimaryKey, Timestamps, table=True):
    """An area a store delivers to.

    Coverage, from broadest to most specific: no region = all of Saudi Arabia;
    a region; specific cities in that region; specific districts of those cities.
    The most specific active zone matching the customer's address applies.
    """

    __tablename__ = "delivery_zones"
    __table_args__ = (
        CheckConstraint("fee >= 0 AND fee <= 1000000", name="fee_range"),
        CheckConstraint("free_delivery_threshold IS NULL OR free_delivery_threshold >= 0", name="threshold_valid"),
        CheckConstraint("eta_min_minutes >= 0 AND eta_max_minutes >= eta_min_minutes", name="eta_valid"),
        CheckConstraint("jsonb_array_length(cities) = 0 OR region IS NOT NULL", name="cities_need_region"),
        CheckConstraint(
            "jsonb_array_length(districts) = 0 OR jsonb_array_length(cities) > 0", name="districts_need_city"
        ),
    )

    store_id: uuid.UUID = Field(foreign_key="stores.id", ondelete="CASCADE", index=True)
    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="CASCADE", index=True)
    name: str = Field(max_length=100)
    region: str | None = Field(default=None, max_length=50)
    cities: list[str] = Field(default_factory=list, sa_type=JSONB)
    districts: list[str] = Field(default_factory=list, sa_type=JSONB)
    fee: int = Field(sa_type=BigInteger)  # halalas, excl. VAT
    free_delivery_threshold: int | None = Field(default=None, sa_type=BigInteger)  # items after discount
    eta_min_minutes: int
    eta_max_minutes: int
    is_active: bool = True


class Delivery(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "deliveries"
    __table_args__ = (
        CheckConstraint("method IN ('DELIVERY', 'PICKUP')", name="method_valid"),
        CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'PREPARING', 'READY_FOR_PICKUP', 'OUT_FOR_DELIVERY',"
            " 'DELIVERED', 'FAILED', 'CANCELLED')",
            name="status_valid",
        ),
        CheckConstraint("method <> 'DELIVERY' OR address IS NOT NULL", name="delivery_has_address"),
        CheckConstraint("method <> 'PICKUP' OR pickup_location IS NOT NULL", name="pickup_has_location"),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)"
            " AND (latitude IS NULL OR latitude BETWEEN -90 AND 90)"
            " AND (longitude IS NULL OR longitude BETWEEN -180 AND 180)",
            name="pin_valid",
        ),
        CheckConstraint("eta_min_minutes >= 0 AND eta_max_minutes >= eta_min_minutes", name="eta_valid"),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
    )

    merchant_order_id: uuid.UUID = Field(foreign_key="merchant_orders.id", ondelete="RESTRICT", unique=True)
    order_id: uuid.UUID = Field(foreign_key="orders.id", ondelete="RESTRICT", index=True)
    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="RESTRICT", index=True)
    store_id: uuid.UUID = Field(foreign_key="stores.id", ondelete="RESTRICT")
    customer_user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    method: str = Field(max_length=20)
    # Who performs the delivery, by provider key (see delivery.providers). The order
    # domain never depends on a specific provider.
    provider: str = Field(max_length=40)
    provider_reference: str | None = Field(default=None, max_length=120)
    status: str = Field(default=DeliveryStatus.PENDING.value, max_length=30, index=True)
    # Snapshots taken at checkout.
    zone_id: uuid.UUID | None = Field(default=None, foreign_key="delivery_zones.id", ondelete="SET NULL")
    zone_name: str | None = Field(default=None, max_length=100)
    address: dict[str, str] | None = Field(default=None, sa_type=JSONB)
    latitude: float | None = None
    longitude: float | None = None
    instructions: str = Field(default="", sa_type=Text)
    pickup_location_id: uuid.UUID | None = Field(default=None, foreign_key="merchant_addresses.id", ondelete="SET NULL")
    pickup_location: dict[str, object] | None = Field(default=None, sa_type=JSONB)
    eta_min_minutes: int
    eta_max_minutes: int
    # Set when the merchant confirms: confirmation time + the promised window.
    estimated_earliest_at: datetime | None = None
    estimated_latest_at: datetime | None = None
    attempts: int = 0
    failure_reason: str | None = Field(default=None, sa_type=Text)
    confirmed_at: datetime | None = None
    ready_at: datetime | None = None
    out_for_delivery_at: datetime | None = None
    delivered_at: datetime | None = None
    failed_at: datetime | None = None
    cancelled_at: datetime | None = None


class DeliveryEvent(UUIDPrimaryKey, CreatedAt, table=True):
    __tablename__ = "delivery_events"

    delivery_id: uuid.UUID = Field(foreign_key="deliveries.id", ondelete="RESTRICT", index=True)
    from_status: str | None = Field(default=None, max_length=30)
    to_status: str = Field(max_length=30)
    source: str = Field(max_length=20)
    actor_user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    note: str | None = Field(default=None, sa_type=Text)
