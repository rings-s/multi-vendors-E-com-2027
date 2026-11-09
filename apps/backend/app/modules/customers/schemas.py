import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.validators import SaudiMobile, SaudiRegion


class AddressBase(BaseModel):
    label: str = Field(default="", max_length=100)
    recipient_name: str = Field(min_length=2, max_length=200)
    phone: SaudiMobile
    region: SaudiRegion
    city: str = Field(min_length=2, max_length=100)
    district: str = Field(default="", max_length=100)
    street: str = Field(default="", max_length=200)
    building_number: str = Field(default="", max_length=20)
    postal_code: str = Field(default="", pattern=r"^(\d{5})?$")
    additional_info: str = Field(default="", max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    delivery_instructions: str = Field(default="", max_length=500)
    is_default: bool = False

    @model_validator(mode="after")
    def _pin_is_complete(self) -> "AddressBase":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=100)
    recipient_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: SaudiMobile | None = None
    region: SaudiRegion | None = None
    city: str | None = Field(default=None, min_length=2, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    street: str | None = Field(default=None, max_length=200)
    building_number: str | None = Field(default=None, max_length=20)
    postal_code: str | None = Field(default=None, pattern=r"^(\d{5})?$")
    additional_info: str | None = Field(default=None, max_length=300)
    delivery_instructions: str | None = Field(default=None, max_length=500)
    # The pin is replaced as a pair; send clear_location to remove it.
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    clear_location: bool = False
    is_default: bool | None = None

    @model_validator(mode="after")
    def _pin_is_complete(self) -> "AddressUpdate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.clear_location and self.latitude is not None:
            raise ValueError("Use either a new location or clear_location, not both")
        return self


class AddressOut(AddressBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class PreferencesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    marketing_emails: bool
    notification_settings: dict[str, bool]


class PreferencesUpdate(BaseModel):
    marketing_emails: bool | None = None
    notification_settings: dict[str, bool] | None = None


class CustomerMe(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    preferred_language: str
    display_name: str | None
    preferences: PreferencesOut
