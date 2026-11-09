"""Provider-independent payment interface.

Business logic depends only on this module. Provider-specific request/response
schemas live inside each adapter (``moyasar.py``, ``mock.py``).
"""

import abc
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.modules.merchants.models import OnboardingStatus
from app.modules.payments.models import PaymentStatus


class WebhookKind(StrEnum):
    PAYMENT = "PAYMENT"
    MERCHANT_ACCOUNT = "MERCHANT_ACCOUNT"
    SETTLEMENT = "SETTLEMENT"
    CHARGEBACK = "CHARGEBACK"
    UNSUPPORTED = "UNSUPPORTED"


class InvalidWebhook(Exception):
    """Raised when a webhook fails authentication or cannot be parsed."""


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_splits: bool
    # Number of merchant recipients a single provider payment may carry. The platform
    # always uses 1 (merchant-specific checkout groups) unless verified otherwise.
    max_merchants_per_payment: int
    supports_settlement_lookup: bool
    supports_chargeback_events: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MerchantAccountInput:
    merchant_id: str
    business_type: str
    name: str  # machine-friendly: alphanumeric and underscores
    public_name: str
    email: str
    admin_email: str
    website: str
    owners_count: int
    signatory: str
    signatory_count: int | None
    activity_license_required: bool
    country: str = "SA"
    time_zone: str = "Asia/Riyadh"


@dataclass(frozen=True)
class ProviderMerchantAccount:
    provider_account_id: str
    recipient_id: str | None
    raw_status: str
    onboarding_status: OnboardingStatus
    payouts_enabled: bool | None
    required_documents: list[dict[str, object]] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    details: dict[str, object] = field(default_factory=dict)  # sanitised, never credentials


@dataclass(frozen=True)
class SplitInstruction:
    recipient_id: str
    amount: int  # halalas
    reference: str
    is_fee_source: bool
    refundable: bool = True


@dataclass(frozen=True)
class PaymentRequest:
    payment_id: str  # our payment id, sent as the provider idempotency id where supported
    amount: int  # halalas
    currency: str
    description: str
    callback_url: str
    source: Mapping[str, object]
    metadata: Mapping[str, str]


@dataclass(frozen=True)
class SplitPaymentRequest(PaymentRequest):
    splits: tuple[SplitInstruction, ...] = ()


@dataclass(frozen=True)
class ProviderPayment:
    provider_payment_id: str
    status: PaymentStatus
    raw_status: str
    amount: int
    refunded_amount: int
    currency: str
    fee: int | None
    transaction_url: str | None
    failure_reason: str | None
    is_live: bool
    payment_method: str | None
    raw: dict[str, object]  # sanitised provider response


@dataclass(frozen=True)
class ProviderSettlement:
    provider_settlement_id: str
    recipient_id: str
    amount: int
    currency: str
    status: str  # "COMPLETED" | "FAILED" | "PROCESSING"
    completed_at: datetime | None
    failure_reason: str | None
    raw: dict[str, object]


@dataclass(frozen=True)
class ProviderChargeback:
    provider_reference: str
    provider_payment_id: str
    amount: int
    status: str  # "OPEN" | "WON" | "LOST"
    reason: str


@dataclass(frozen=True)
class WebhookRequest:
    headers: Mapping[str, str]  # lower-cased header names
    body: bytes


@dataclass(frozen=True)
class WebhookEvent:
    event_id: str
    event_type: str
    kind: WebhookKind
    object_id: str | None
    is_live: bool
    payload: dict[str, object]  # secrets removed
    data: dict[str, object]


class PaymentProvider(abc.ABC):
    name: str
    capabilities: ProviderCapabilities

    @property
    @abc.abstractmethod
    def is_test(self) -> bool:
        """True when no real money can move through this provider instance."""

    @property
    @abc.abstractmethod
    def platform_recipient_id(self) -> str | None: ...

    @abc.abstractmethod
    async def create_payment(self, data: PaymentRequest) -> ProviderPayment: ...

    @abc.abstractmethod
    async def retrieve_payment(self, payment_id: str) -> ProviderPayment: ...

    @abc.abstractmethod
    async def create_merchant_account(self, data: MerchantAccountInput) -> ProviderMerchantAccount: ...

    @abc.abstractmethod
    async def get_merchant_account(self, account_id: str) -> ProviderMerchantAccount: ...

    @abc.abstractmethod
    async def submit_merchant_account(self, account_id: str) -> ProviderMerchantAccount: ...

    @abc.abstractmethod
    async def create_split_payment(self, data: SplitPaymentRequest) -> ProviderPayment: ...

    @abc.abstractmethod
    async def refund_payment(self, payment_id: str, amount: int | None = None) -> ProviderPayment: ...

    @abc.abstractmethod
    async def verify_webhook(self, request: WebhookRequest) -> WebhookEvent: ...

    @abc.abstractmethod
    def classify_event(self, event_type: str) -> WebhookKind:
        """Map a provider event type to the kind of object it concerns."""

    @abc.abstractmethod
    async def get_settlement(self, settlement_id: str) -> ProviderSettlement: ...

    async def get_chargeback(self, reference: str) -> ProviderChargeback:
        from app.core.errors import ProviderCapabilityUnavailable

        raise ProviderCapabilityUnavailable(f"{self.name} chargeback retrieval is not supported.")
