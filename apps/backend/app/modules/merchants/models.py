"""Merchants: Merchant, MerchantProfile, MerchantAddress, MerchantVerification,
MerchantPaymentAccount, MerchantBankAccountReference, MerchantDocumentReference."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import CheckConstraint, Field, Relationship, Text, UniqueConstraint

from app.database.base import CreatedAt, Timestamps, UUIDPrimaryKey


class MerchantStatus(StrEnum):
    """Verification statuses (docs/product/requirements.md §2.2)."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ADDITIONAL_INFO_REQUIRED = "ADDITIONAL_INFO_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class BusinessType(StrEnum):
    # Values accepted by the Moyasar Platform "Create Merchant" API `type` field.
    FREELANCER = "freelancer"
    ESTABLISHMENT = "establishment"
    COMPANY = "company"
    FOREIGN_COMPANY = "foreign_company"
    GOVERNMENT = "government"
    CHARITY = "charity"


class OnboardingStatus(StrEnum):
    """Provider-independent payment onboarding status."""

    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    UNDER_REVIEW = "UNDER_REVIEW"
    SEMI_ACTIVE = "SEMI_ACTIVE"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    REJECTED = "REJECTED"
    DISABLED = "DISABLED"
    FAILED = "FAILED"


class PayoutStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


_MERCHANT_STATUSES = ", ".join(f"'{s.value}'" for s in MerchantStatus)


class MerchantProfile(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "merchant_profiles"

    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="CASCADE", unique=True)
    owner_full_name: str = Field(max_length=200)
    contact_email: str = Field(max_length=320)
    contact_phone: str = Field(max_length=20)
    business_description: str = Field(default="", sa_type=Text)
    website: str | None = Field(default=None, max_length=300)


class Merchant(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "merchants"
    __table_args__ = (CheckConstraint(f"status IN ({_MERCHANT_STATUSES})", name="status_valid"),)

    owner_user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT", unique=True)
    business_name: str = Field(max_length=200)
    business_type: str = Field(default=BusinessType.ESTABLISHMENT.value, max_length=30)
    category_id: uuid.UUID | None = Field(default=None, foreign_key="categories.id", ondelete="SET NULL")
    commercial_registration_number: str | None = Field(default=None, max_length=30)
    vat_number: str | None = Field(default=None, max_length=20)
    status: str = Field(default=MerchantStatus.DRAFT.value, max_length=30, index=True)
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    status_reason: str | None = Field(default=None, sa_type=Text)

    profile: MerchantProfile = Relationship(sa_relationship_kwargs={"lazy": "selectin", "uselist": False})

    @property
    def is_vat_registered(self) -> bool:
        return bool(self.vat_number)


class MerchantAddress(UUIDPrimaryKey, Timestamps, table=True):
    __tablename__ = "merchant_addresses"

    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="CASCADE", index=True)
    label: str = Field(default="", max_length=100)
    region: str = Field(max_length=50)
    city: str = Field(max_length=100)
    district: str = Field(default="", max_length=100)
    street: str = Field(default="", max_length=200)
    building_number: str = Field(default="", max_length=20)
    postal_code: str = Field(default="", max_length=10)
    is_primary: bool = False
    is_pickup_location: bool = False
    # WGS84 map pin; both set or both null (enforced by the API schema and a DB check).
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)


class MerchantVerification(UUIDPrimaryKey, CreatedAt, table=True):
    """Append-only history of verification status changes."""

    __tablename__ = "merchant_verifications"

    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="CASCADE", index=True)
    from_status: str | None = Field(default=None, max_length=30)
    to_status: str = Field(max_length=30)
    actor_user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    note: str | None = Field(default=None, sa_type=Text)


class MerchantPaymentAccount(UUIDPrimaryKey, Timestamps, table=True):
    """Provider identifiers and onboarding status (no credentials are stored)."""

    __tablename__ = "merchant_payment_accounts"
    __table_args__ = (UniqueConstraint("merchant_id", "provider"),)

    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="RESTRICT", index=True)
    provider: str = Field(max_length=30)
    provider_account_id: str | None = Field(default=None, max_length=100, index=True)
    # The identifier used as the split recipient (Moyasar: `entity_id`).
    recipient_id: str | None = Field(default=None, max_length=100)
    onboarding_status: str = Field(default=OnboardingStatus.NOT_STARTED.value, max_length=30)
    verification_status: str | None = Field(default=None, max_length=50)  # raw provider status
    payout_status: str = Field(default=PayoutStatus.UNKNOWN.value, max_length=30)
    provider_details: dict[str, object] = Field(default_factory=dict, sa_type=JSONB)
    is_test: bool = True
    attempts: int = 0
    last_error: str | None = Field(default=None, sa_type=Text)
    last_synced_at: datetime | None = None


class MerchantBankAccountReference(UUIDPrimaryKey, Timestamps, table=True):
    """Masked bank account reference. The full IBAN is never stored."""

    __tablename__ = "merchant_bank_account_references"

    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="CASCADE", index=True)
    beneficiary_name: str = Field(max_length=200)
    bank_name: str | None = Field(default=None, max_length=100)
    iban_masked: str = Field(max_length=34)
    iban_last4: str = Field(max_length=4)
    provider_reference: str | None = Field(default=None, max_length=100)
    is_active: bool = True


class DocumentStatus(StrEnum):
    REQUIRED = "REQUIRED"  # requested by the provider, not yet supplied
    SATISFIED = "SATISFIED"  # no longer requested by the provider


class MerchantDocumentReference(UUIDPrimaryKey, Timestamps, table=True):
    """Reference to a document held by the payment provider (files are not stored here)."""

    __tablename__ = "merchant_document_references"

    merchant_id: uuid.UUID = Field(foreign_key="merchants.id", ondelete="CASCADE", index=True)
    provider: str = Field(max_length=30)
    document_type: str = Field(max_length=60)
    provider_document_id: str | None = Field(default=None, max_length=100)
    status: str = Field(default="REQUIRED", max_length=30)
