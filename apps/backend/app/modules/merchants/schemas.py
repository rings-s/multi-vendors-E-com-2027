import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from app.core.validators import SaudiIBAN, SaudiMobile, SaudiRegion
from app.modules.auth.schemas import Password
from app.modules.merchants.models import BusinessType

SLUG_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{1,58}[a-z0-9])$"


class MerchantAddressIn(BaseModel):
    region: SaudiRegion
    city: str = Field(min_length=2, max_length=100)
    district: str = Field(default="", max_length=100)
    street: str = Field(default="", max_length=200)
    building_number: str = Field(default="", max_length=20)
    postal_code: str = Field(default="", pattern=r"^(\d{5})?$")


class MerchantRegisterRequest(BaseModel):
    owner_full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: Password
    mobile: SaudiMobile
    business_name: str = Field(min_length=2, max_length=200)
    business_type: BusinessType = BusinessType.ESTABLISHMENT
    store_name: str = Field(min_length=2, max_length=200)
    store_slug: str = Field(pattern=SLUG_PATTERN)
    category_id: uuid.UUID | None = None
    business_description: str = Field(default="", max_length=5000)
    city: str = Field(min_length=2, max_length=100)
    address: MerchantAddressIn
    commercial_registration_number: str | None = Field(default=None, pattern=r"^\d{10}$")
    vat_number: str | None = Field(default=None, pattern=r"^3\d{13}3$")
    preferred_language: Literal["ar", "en"] = "ar"


class OnboardingUpdate(BaseModel):
    business_name: str | None = Field(default=None, min_length=2, max_length=200)
    business_type: BusinessType | None = None
    category_id: uuid.UUID | None = None
    business_description: str | None = Field(default=None, max_length=5000)
    contact_email: EmailStr | None = None
    contact_phone: SaudiMobile | None = None
    website: HttpUrl | None = None
    commercial_registration_number: str | None = Field(default=None, pattern=r"^\d{10}$")
    vat_number: str | None = Field(default=None, pattern=r"^3\d{13}3$")
    address: MerchantAddressIn | None = None


class MerchantAddressOut(MerchantAddressIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    is_primary: bool
    is_pickup_location: bool


class VerificationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: str | None
    to_status: str
    note: str | None
    created_at: datetime


class MerchantOut(BaseModel):
    id: uuid.UUID
    owner_user_id: uuid.UUID
    owner_full_name: str
    business_name: str
    business_type: str
    category_id: uuid.UUID | None
    business_description: str
    contact_email: str
    contact_phone: str
    website: str | None
    commercial_registration_number: str | None
    vat_number: str | None
    status: str
    status_reason: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    created_at: datetime
    store_id: uuid.UUID | None
    store_slug: str | None
    addresses: list[MerchantAddressOut]
    can_accept_payments: bool


class StatusTransition(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class BankAccountIn(BaseModel):
    beneficiary_name: str = Field(min_length=2, max_length=200)
    iban: SaudiIBAN
    bank_name: str | None = Field(default=None, max_length=100)


class PaymentOnboardingRequest(BaseModel):
    bank_account: BankAccountIn
    website: HttpUrl
    owners_count: int = Field(ge=1, le=100)
    signatory: Literal["owner", "commercial_contract", "power_of_attorney"] = "owner"
    signatory_count: int | None = Field(default=None, ge=1, le=100)
    activity_license_required: bool = False


class BankAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    beneficiary_name: str
    bank_name: str | None
    iban_masked: str
    created_at: datetime


class DocumentReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_type: str
    provider_document_id: str | None
    status: str
    updated_at: datetime


class PaymentAccountOut(BaseModel):
    provider: str
    is_test: bool
    provider_account_id: str | None
    recipient_id: str | None
    onboarding_status: str
    verification_status: str | None
    payout_status: str
    required_documents: list[dict[str, object]]
    reasons: list[str]
    attempts: int
    last_error: str | None
    last_synced_at: datetime | None
    can_accept_payments: bool
    bank_account: BankAccountOut | None
    documents: list[DocumentReferenceOut]
