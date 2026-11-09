import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.validators import SaudiRegion
from app.modules.delivery.pricing import normalize_places
from app.modules.delivery.providers.base import DeliveryQuote, PickupPoint

MAX_ETA_MINUTES = 60 * 24 * 60  # 60 days
# What a refund covers: AUTO = items first, then the delivery charge.
RefundScopeLiteral = Literal["AUTO", "ITEMS", "DELIVERY"]

# -- checkout ---------------------------------------------------------------------------


class DeliverySelectionIn(BaseModel):
    store_id: uuid.UUID
    method: Literal["DELIVERY", "PICKUP"]
    pickup_location_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _pickup_only(self) -> "DeliverySelectionIn":
        if self.method == "DELIVERY" and self.pickup_location_id is not None:
            raise ValueError("pickup_location_id is only valid for PICKUP.")
        return self


class DeliveryChoices(BaseModel):
    """Delivery choices sent with a checkout quote or a checkout."""

    address_id: uuid.UUID | None = None
    deliveries: list[DeliverySelectionIn] = Field(default_factory=list, max_length=50)

    @field_validator("deliveries")
    @classmethod
    def _unique_stores(cls, value: list[DeliverySelectionIn]) -> list[DeliverySelectionIn]:
        if len({d.store_id for d in value}) != len(value):
            raise ValueError("Choose one delivery method per store.")
        return value


class PickupPointOut(BaseModel):
    id: uuid.UUID
    label: str
    region: str
    city: str
    district: str
    street: str
    building_number: str
    postal_code: str
    latitude: float | None
    longitude: float | None

    @classmethod
    def of(cls, point: PickupPoint) -> "PickupPointOut":
        return cls(**{k: v for k, v in point.__dict__.items()})


class DeliveryOptionOut(BaseModel):
    method: Literal["DELIVERY", "PICKUP"]
    available: bool
    issue: str | None
    fee: int
    base_fee: int
    fee_waived: int
    free_delivery_threshold: int | None
    eta_min_minutes: int
    eta_max_minutes: int
    zone_name: str | None
    pickup_location: PickupPointOut | None
    pickup_points: list[PickupPointOut]

    @classmethod
    def of(cls, quote: DeliveryQuote) -> "DeliveryOptionOut":
        return cls(
            method=quote.method.value,  # type: ignore[arg-type]
            available=quote.available,
            issue=quote.issue,
            fee=quote.fee,
            base_fee=quote.base_fee,
            fee_waived=quote.fee_waived,
            free_delivery_threshold=quote.free_delivery_threshold,
            eta_min_minutes=quote.eta_min_minutes,
            eta_max_minutes=quote.eta_max_minutes,
            zone_name=quote.zone_name,
            pickup_location=PickupPointOut.of(quote.pickup_location) if quote.pickup_location else None,
            pickup_points=[PickupPointOut.of(p) for p in quote.pickup_points],
        )


# -- merchant configuration ---------------------------------------------------------------


class DeliverySettingsIn(BaseModel):
    delivery_enabled: bool
    pickup_enabled: bool
    pickup_preparation_minutes: int = Field(ge=0, le=43200)
    delivery_policy: str = Field(default="", max_length=10000)


class DeliverySettingsOut(DeliverySettingsIn):
    model_config = ConfigDict(from_attributes=True)

    pickup_locations: int = 0  # number of locations marked as pickup points
    active_zones: int = 0
    fee_recipient: str = "MERCHANT"
    cost_bearer: str = "MERCHANT"
    commission_applies_to: str = "ITEMS_ONLY"
    delivery_commission_rate: str = "0"


class ZoneIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    region: SaudiRegion | None = None
    cities: list[str] = Field(default_factory=list, max_length=50)
    districts: list[str] = Field(default_factory=list, max_length=200)
    fee: int = Field(ge=0, le=1_000_000, description="Halalas, excl. VAT.")
    free_delivery_threshold: int | None = Field(default=None, ge=0, description="Halalas of items after discount.")
    eta_min_minutes: int = Field(ge=0, le=MAX_ETA_MINUTES)
    eta_max_minutes: int = Field(ge=0, le=MAX_ETA_MINUTES)
    is_active: bool = True

    @field_validator("cities", "districts")
    @classmethod
    def _clean(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for name in value:
            name = " ".join(name.split())
            if len(name) > 100:
                raise ValueError("Place names are limited to 100 characters.")
            key = normalize_places([name])
            if key and key[0] not in seen:
                seen.add(key[0])
                cleaned.append(name)
        return cleaned

    @model_validator(mode="after")
    def _coverage(self) -> "ZoneIn":
        if self.cities and self.region is None:
            raise ValueError("Choose the region the cities belong to.")
        if self.districts and not self.cities:
            raise ValueError("Districts need at least one city.")
        if self.eta_max_minutes < self.eta_min_minutes:
            raise ValueError("The latest delivery time must not be before the earliest.")
        return self


class ZoneOut(ZoneIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# -- deliveries ---------------------------------------------------------------------------


class DeliveryEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: str | None
    to_status: str
    source: str
    note: str | None
    created_at: datetime


class DeliveryOut(BaseModel):
    """A delivery as the customer and the merchant see it."""

    id: uuid.UUID
    merchant_order_id: uuid.UUID
    method: str
    provider: str
    status: str
    zone_name: str | None
    address: dict[str, str] | None
    latitude: float | None
    longitude: float | None
    instructions: str
    pickup_location: dict[str, object] | None
    eta_min_minutes: int
    eta_max_minutes: int
    estimated_earliest_at: datetime | None
    estimated_latest_at: datetime | None
    attempts: int
    failure_reason: str | None
    confirmed_at: datetime | None
    ready_at: datetime | None
    out_for_delivery_at: datetime | None
    delivered_at: datetime | None
    failed_at: datetime | None
    cancelled_at: datetime | None
    # Financial terms recorded on the merchant order.
    fee: int
    fee_waived: int
    vat: int
    fee_recipient: str | None
    cost_bearer: str | None
    # Status changes the viewer may make now (merchant view only; empty for customers).
    next_statuses: list[str] = Field(default_factory=list)
    events: list[DeliveryEventOut] = Field(default_factory=list)


class DeliveryStatusUpdate(BaseModel):
    status: Literal["CONFIRMED", "PREPARING", "READY_FOR_PICKUP", "OUT_FOR_DELIVERY", "DELIVERED", "FAILED"]
    note: str | None = Field(default=None, max_length=2000)
    failure_reason: str | None = Field(default=None, min_length=3, max_length=2000)
    # Optional courier details when the merchant hands the parcel to a courier itself.
    carrier: str | None = Field(default=None, max_length=100)
    tracking_number: str | None = Field(default=None, max_length=100)
    tracking_url: str | None = Field(default=None, max_length=500, pattern=r"^https://")

    @model_validator(mode="after")
    def _failure_reason(self) -> "DeliveryStatusUpdate":
        if self.status == "FAILED" and not self.failure_reason:
            raise ValueError("Explain why the delivery failed.")
        if self.status != "FAILED" and self.failure_reason:
            raise ValueError("failure_reason is only used with FAILED.")
        return self


class DeliveryListItem(BaseModel):
    id: uuid.UUID
    merchant_order_id: uuid.UUID
    merchant_order_number: str
    method: str
    status: str
    customer_name: str
    city: str | None
    district: str | None
    zone_name: str | None
    fee: int
    estimated_latest_at: datetime | None
    created_at: datetime
