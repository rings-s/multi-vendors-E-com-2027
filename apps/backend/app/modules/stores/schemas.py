import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.core.validators import SaudiMobile, SaudiRegion
from app.modules.catalog.schemas import MediaUrl


class StoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_id: uuid.UUID
    slug: str
    name: str
    description: str
    logo_url: str | None
    cover_url: str | None
    region: str
    city: str
    contact_email: str | None
    contact_phone: str | None
    status: str
    is_open: bool
    shipping_policy: str
    return_policy: str
    rating_avg: float
    rating_count: int
    orders_count: int
    category_ids: list[uuid.UUID] = Field(default_factory=list)
    created_at: datetime


class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    logo_url: MediaUrl | None = None
    cover_url: MediaUrl | None = None
    region: SaudiRegion | None = None
    city: str | None = Field(default=None, min_length=2, max_length=100)
    contact_email: EmailStr | None = None
    contact_phone: SaudiMobile | None = None
    is_open: bool | None = None
    shipping_policy: str | None = Field(default=None, max_length=10000)
    return_policy: str | None = Field(default=None, max_length=10000)
    category_ids: list[uuid.UUID] | None = Field(default=None, max_length=10)


class LocationIn(BaseModel):
    label: str = Field(default="", max_length=100)
    region: SaudiRegion
    city: str = Field(min_length=2, max_length=100)
    district: str = Field(default="", max_length=100)
    street: str = Field(default="", max_length=200)
    building_number: str = Field(default="", max_length=20)
    postal_code: str = Field(default="", pattern=r"^(\d{5})?$")
    is_pickup_location: bool = False
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def _pin_is_complete(self) -> "LocationIn":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class PublicLocationOut(BaseModel):
    """A pickup point as customers see it. Only locations the merchant marked as pickup are public."""

    model_config = ConfigDict(from_attributes=True)

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


class LocationOut(LocationIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_primary: bool
