"""Moyasar adapter.

Implemented only from behaviour verified in the official documentation
(see docs/architecture/moyasar-verification.md):

* Payments API (https://api.moyasar.com/v1, HTTP Basic, secret key as username,
  empty password): ``POST /payments`` (``amount`` in the smallest currency unit,
  ``given_id`` for idempotency, ``splits``), ``GET /payments/:id``,
  ``POST /payments/:id/refund`` (optional ``amount``; full refund when omitted).
* Platform API (``https://apimig.moyasar.com/v1``): ``POST /merchants`` (requires
  ``enabled_schemes`` and the contractual ``fees`` object), ``GET /merchants/:id``,
  ``POST /merchants/:id/review``; HTTP Basic with the platform key, empty password.
* Webhooks: envelope ``{id, type, created_at, secret_token, account_name, live, data}``;
  authenticity is established by comparing ``secret_token`` with the configured
  shared secret (no signature scheme is documented).

Not verified / not implemented (raises ``ProviderCapabilityUnavailable``):
settlement lookup, chargeback events, and the payload of balance-transfer events.
Splitting requires Moyasar to enable it for the platform (``MOYASAR_SPLITS_ENABLED``).
"""

import json
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import ProviderCapabilityUnavailable, ProviderError, ValidationFailed
from app.core.security import constant_time_equals
from app.integrations.payments.base import (
    InvalidWebhook,
    MerchantAccountInput,
    PaymentProvider,
    PaymentRequest,
    ProviderCapabilities,
    ProviderMerchantAccount,
    ProviderPayment,
    ProviderSettlement,
    SplitPaymentRequest,
    WebhookEvent,
    WebhookKind,
    WebhookRequest,
)
from app.modules.merchants.models import OnboardingStatus
from app.modules.payments.models import PaymentStatus

# Source types that never carry raw card data to our servers. Raw `creditcard`
# sources are rejected: card data must be tokenised client-side with the publishable key.
ALLOWED_SOURCE_TYPES = frozenset({"token", "applepay", "samsungpay", "stcpay"})

_MERCHANT_STATUS_MAP: dict[str, OnboardingStatus] = {
    "pending": OnboardingStatus.PENDING,
    "missing_docs": OnboardingStatus.ACTION_REQUIRED,
    "under_review": OnboardingStatus.UNDER_REVIEW,
    # The meaning of `semi_active` is not documented; it is treated as not able to sell.
    "semi_active": OnboardingStatus.SEMI_ACTIVE,
    "active": OnboardingStatus.ACTIVE,
    "hold": OnboardingStatus.ON_HOLD,
    "rejected": OnboardingStatus.REJECTED,
    "disabled": OnboardingStatus.DISABLED,
}

_PAYMENT_EVENT_TYPES = frozenset(
    {
        "payment_paid",
        "payment_failed",
        "payment_faild",  # spelling as it appears in the webhook reference
        "payment_refunded",
        "payment_voided",
        "payment_authorized",
        "payment_captured",
        "payment_verified",
        "payment_abandoned",
    }
)
_MERCHANT_EVENT_TYPES = frozenset(
    {
        "merchant_created",
        "merchant_updated",
        "merchant_semi_activated",
        "merchant_activated",
        "merchant_un_hold",
        "merchant_review_failed",
        "merchant_disabled",
        "merchant_hold",
        "merchant_rejected",
        "merchant_contract_generated",
    }
)
_SECRET_FIELDS = ("secret_token", "api_keys", "secret_key")


def _strip_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_secrets(v) for k, v in value.items() if k not in _SECRET_FIELDS}
    if isinstance(value, list):
        return [_strip_secrets(v) for v in value]
    return value


def map_payment_status(raw_status: str, amount: int, refunded: int) -> PaymentStatus:
    match raw_status:
        case "initiated" | "verified":
            return PaymentStatus.PENDING
        case "authorized":
            return PaymentStatus.AUTHORIZED
        case "paid" | "captured":
            if refunded >= amount > 0:
                return PaymentStatus.REFUNDED
            return PaymentStatus.PARTIALLY_REFUNDED if refunded > 0 else PaymentStatus.PAID
        case "refunded":
            return PaymentStatus.REFUNDED if refunded >= amount else PaymentStatus.PARTIALLY_REFUNDED
        case "voided":
            return PaymentStatus.CANCELLED
        case "failed" | "expired":
            return PaymentStatus.FAILED
        case _:
            raise ProviderError(f"Unknown Moyasar payment status: {raw_status!r}")


class MoyasarProvider(PaymentProvider):
    name = "moyasar"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(20.0))
        self.capabilities = ProviderCapabilities(
            supports_splits=settings.moyasar_splits_enabled,
            max_merchants_per_payment=1,
            supports_settlement_lookup=False,
            supports_chargeback_events=False,
            notes=(
                "Splitting must be enabled for the platform by Moyasar.",
                "Maximum recipients per payment is not documented; one merchant per payment is used.",
                "Settlement lookup and chargeback APIs are not documented in the verified sources.",
            ),
        )

    @property
    def is_test(self) -> bool:
        return not self._settings.moyasar_live

    @property
    def platform_recipient_id(self) -> str | None:
        return self._settings.moyasar_platform_recipient_id

    # -- HTTP helpers -----------------------------------------------------------------

    async def _request(self, method: str, url: str, key: str | None, body: dict[str, Any] | None = None) -> Any:
        if not key:
            raise ProviderCapabilityUnavailable("Moyasar credentials are not configured.")
        try:
            response = await self._client.request(method, url, json=body, auth=(key, ""))
        except httpx.HTTPError as exc:
            raise ProviderError(f"Moyasar request failed: {exc.__class__.__name__}") from exc
        if response.status_code >= 400:
            try:
                error = response.json()
            except ValueError:
                error = {"message": response.text[:500]}
            raise ProviderError(
                str(error.get("message") or "Moyasar rejected the request."),
                details={"status": response.status_code, "type": error.get("type"), "errors": error.get("errors")},
            )
        return response.json()

    def _payments_url(self, path: str) -> str:
        return f"{self._settings.moyasar_api_base.rstrip('/')}{path}"

    def _platform_url(self, path: str) -> str:
        return f"{self._settings.moyasar_platform_api_base.rstrip('/')}{path}"

    def _secret_key(self) -> str | None:
        key = self._settings.moyasar_secret_key
        return key.get_secret_value() if key else None

    def _platform_key(self) -> str | None:
        key = self._settings.moyasar_platform_api_key
        return key.get_secret_value() if key else None

    # -- Payments ---------------------------------------------------------------------

    def _to_payment(self, data: dict[str, Any]) -> ProviderPayment:
        amount = int(data["amount"])
        refunded = int(data.get("refunded") or 0)
        source = data.get("source") or {}
        return ProviderPayment(
            provider_payment_id=str(data["id"]),
            status=map_payment_status(str(data["status"]), amount, refunded),
            raw_status=str(data["status"]),
            amount=amount,
            refunded_amount=refunded,
            currency=str(data.get("currency", "")),
            fee=int(data["fee"]) if data.get("fee") is not None else None,
            transaction_url=source.get("transaction_url"),
            failure_reason=source.get("message") if data.get("status") == "failed" else None,
            is_live=not self.is_test,
            payment_method=source.get("type"),
            raw=_strip_secrets(data),
        )

    def _payment_body(self, data: PaymentRequest) -> dict[str, Any]:
        source = dict(data.source)
        if source.get("type") not in ALLOWED_SOURCE_TYPES:
            raise ValidationFailed(
                "Unsupported payment source. Card details must be tokenised on the client.",
                details={"allowed": sorted(ALLOWED_SOURCE_TYPES)},
            )
        return {
            "given_id": data.payment_id,
            "amount": data.amount,
            "currency": data.currency,
            "description": data.description,
            "callback_url": data.callback_url,
            "source": source,
            "metadata": dict(data.metadata),
        }

    async def create_payment(self, data: PaymentRequest) -> ProviderPayment:
        body = self._payment_body(data)
        return self._to_payment(await self._request("POST", self._payments_url("/payments"), self._secret_key(), body))

    async def create_split_payment(self, data: SplitPaymentRequest) -> ProviderPayment:
        if not self.capabilities.supports_splits:
            raise ProviderCapabilityUnavailable(
                "Moyasar payment splitting is not enabled for this platform. It must be enabled by Moyasar."
            )
        fee_sources = [s for s in data.splits if s.is_fee_source]
        if len(fee_sources) > 1:
            raise ValidationFailed("At most one split can be the fee source.")
        if sum(s.amount for s in data.splits) != data.amount:
            raise ValidationFailed("Split totals must equal the payment amount.")
        if any(s.amount <= 0 for s in data.splits):
            raise ValidationFailed("Split amounts sent to Moyasar must be positive.")
        if not fee_sources:
            # Without an explicit fee source Moyasar charges the highest split (the merchant);
            # fees must never be silently deducted from the seller.
            raise ValidationFailed("A fee-source split is required so processing fees are explicit.")
        body = self._payment_body(data)
        body["splits"] = [
            {
                "recipient_id": s.recipient_id,
                "amount": s.amount,
                "reference": s.reference,
                "fee_source": s.is_fee_source,
                "refundable": s.refundable,
            }
            for s in data.splits
        ]
        return self._to_payment(await self._request("POST", self._payments_url("/payments"), self._secret_key(), body))

    async def retrieve_payment(self, payment_id: str) -> ProviderPayment:
        data = await self._request("GET", self._payments_url(f"/payments/{payment_id}"), self._secret_key())
        return self._to_payment(data)

    async def refund_payment(self, payment_id: str, amount: int | None = None) -> ProviderPayment:
        body = {"amount": amount} if amount is not None else {}
        data = await self._request(
            "POST", self._payments_url(f"/payments/{payment_id}/refund"), self._secret_key(), body
        )
        return self._to_payment(data)

    # -- Merchant onboarding (Platform API) --------------------------------------------

    def _to_merchant(self, data: dict[str, Any]) -> ProviderMerchantAccount:
        raw_status = str(data.get("status", ""))
        status = _MERCHANT_STATUS_MAP.get(raw_status)
        if status is None:
            raise ProviderError(f"Unknown Moyasar merchant status: {raw_status!r}")
        sanitized = _strip_secrets(data)
        return ProviderMerchantAccount(
            provider_account_id=str(data["id"]),
            recipient_id=str(data["entity_id"]) if data.get("entity_id") else None,
            raw_status=raw_status,
            onboarding_status=status,
            payouts_enabled=None,  # payout state is not part of the documented merchant object
            required_documents=list(data.get("required_documents") or []),
            reasons=[str(r) for r in data.get("reasons") or []],
            details={
                k: sanitized.get(k)
                for k in ("documents_complete", "signature", "comment", "documents", "fees", "payment_methods")
            },
        )

    async def create_merchant_account(self, data: MerchantAccountInput) -> ProviderMerchantAccount:
        fees = self._settings.moyasar_merchant_fees
        if not fees:
            raise ProviderCapabilityUnavailable(
                "The merchant fee schedule agreed with Moyasar is not configured (MOYASAR_MERCHANT_FEES)."
            )
        body: dict[str, Any] = {
            "type": data.business_type,
            "name": data.name,
            "public_name": data.public_name,
            "country": data.country,
            "website": data.website,
            "email": data.email,
            "admin_email": data.admin_email,
            "owners_count": data.owners_count,
            "signatory": data.signatory,
            "activity_license_required": data.activity_license_required,
            "time_zone": data.time_zone,
            "enabled_schemes": list(self._settings.moyasar_enabled_schemes),
            "fees": dict(fees),
        }
        if data.signatory_count is not None:
            body["signatory_count"] = data.signatory_count
        # The response contains merchant API keys; they are discarded by `_to_merchant`
        # and never stored (the platform creates payments with its own key).
        response = await self._request("POST", self._platform_url("/merchants"), self._platform_key(), body)
        return self._to_merchant(response)

    async def get_merchant_account(self, account_id: str) -> ProviderMerchantAccount:
        data = await self._request("GET", self._platform_url(f"/merchants/{account_id}"), self._platform_key())
        return self._to_merchant(data)

    async def submit_merchant_account(self, account_id: str) -> ProviderMerchantAccount:
        data = await self._request("POST", self._platform_url(f"/merchants/{account_id}/review"), self._platform_key())
        return self._to_merchant(data)

    # -- Webhooks -----------------------------------------------------------------------

    async def verify_webhook(self, request: WebhookRequest) -> WebhookEvent:
        try:
            payload = json.loads(request.body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise InvalidWebhook("Malformed JSON payload.") from exc
        if not isinstance(payload, dict):
            raise InvalidWebhook("Unexpected payload.")

        presented = payload.get("secret_token") or request.headers.get("x-event-secret")
        secrets = [
            s.get_secret_value()
            for s in (self._settings.moyasar_webhook_secret, self._settings.moyasar_platform_webhook_secret)
            if s is not None
        ]
        if not isinstance(presented, str) or not any(constant_time_equals(presented, s) for s in secrets):
            raise InvalidWebhook("Webhook secret does not match.")

        is_live = bool(payload.get("live"))
        if is_live != self._settings.moyasar_live:
            raise InvalidWebhook("Webhook mode (live/test) does not match this environment.")

        event_id = payload.get("id")
        event_type = payload.get("type")
        data = payload.get("data") or {}
        if not isinstance(event_id, str) or not isinstance(event_type, str) or not isinstance(data, dict):
            raise InvalidWebhook("Missing event id, type or data.")

        kind = self.classify_event(event_type)
        object_id = data.get("id")
        return WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            kind=kind,
            object_id=str(object_id) if object_id else None,
            is_live=is_live,
            payload=_strip_secrets(payload),
            data=_strip_secrets(data),
        )

    def classify_event(self, event_type: str) -> WebhookKind:
        if event_type in _PAYMENT_EVENT_TYPES:
            return WebhookKind.PAYMENT
        if event_type in _MERCHANT_EVENT_TYPES:
            return WebhookKind.MERCHANT_ACCOUNT
        # Includes `balance_transferred` / `merchant_balance_transferred`, whose payload
        # schema is not documented: stored for manual reconciliation, never auto-applied.
        return WebhookKind.UNSUPPORTED

    # -- Settlements --------------------------------------------------------------------

    async def get_settlement(self, settlement_id: str) -> ProviderSettlement:
        raise ProviderCapabilityUnavailable("Moyasar settlement retrieval is not part of the verified documentation.")
