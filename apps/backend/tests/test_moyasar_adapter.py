"""Moyasar adapter contract tests (no network: httpx.MockTransport).

They pin the adapter to the behaviour verified in docs/architecture/moyasar-verification.md.
"""

import base64
import json
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.errors import ProviderCapabilityUnavailable, ProviderError, ValidationFailed
from app.integrations.payments.base import (
    InvalidWebhook,
    MerchantAccountInput,
    SplitInstruction,
    SplitPaymentRequest,
    WebhookKind,
    WebhookRequest,
)
from app.integrations.payments.moyasar import MoyasarProvider
from app.modules.payments.models import PaymentStatus

FEES = {"mada_charge_rate": 1.7, "mada_charge_fixed": 1.0, "mada_refund_fixed": 1.0}


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "environment": "test",
        "payment_provider": "moyasar",
        "moyasar_secret_key": SecretStr("sk_test_secret"),
        "moyasar_platform_api_key": SecretStr("platform_key"),
        "moyasar_webhook_secret": SecretStr("whsec_payments"),
        "moyasar_platform_webhook_secret": SecretStr("whsec_platform"),
        "moyasar_platform_recipient_id": "platform_entity",
        "moyasar_splits_enabled": True,
        "moyasar_merchant_fees": FEES,
    }
    base.update(overrides)
    return Settings(**base)


class Recorder:
    def __init__(self, response: dict[str, Any], status: int = 200) -> None:
        self.requests: list[httpx.Request] = []
        self.response = response
        self.status = status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.response)

    def provider(self, **overrides: Any) -> MoyasarProvider:
        return MoyasarProvider(settings(**overrides), httpx.AsyncClient(transport=httpx.MockTransport(self)))


def _payment_response(**extra: Any) -> dict[str, Any]:
    return {
        "id": "pay_123",
        "status": "initiated",
        "amount": 11500,
        "currency": "SAR",
        "refunded": 0,
        "fee": 0,
        "live": False,
        "source": {"type": "token", "transaction_url": "https://moyasar.test/3ds"},
        **extra,
    }


def _split_request(**extra: Any) -> SplitPaymentRequest:
    base: dict[str, Any] = {
        "payment_id": "local-uuid",
        "amount": 11500,
        "currency": "SAR",
        "description": "Order ORD-1",
        "callback_url": "https://shop.test/checkout/result",
        "source": {"type": "token", "token": "token_abc"},
        "metadata": {"order": "ORD-1"},
        "splits": (
            SplitInstruction("merchant_entity", 10500, "ORD-1:merchant", False, True),
            SplitInstruction("platform_entity", 1000, "ORD-1:platform", True, True),
        ),
    }
    base.update(extra)
    return SplitPaymentRequest(**base)


async def test_split_payment_request_shape_and_auth() -> None:
    recorder = Recorder(_payment_response())
    payment = await recorder.provider().create_split_payment(_split_request())
    request = recorder.requests[0]
    assert request.method == "POST" and str(request.url) == "https://api.moyasar.com/v1/payments"
    assert request.headers["authorization"] == "Basic " + base64.b64encode(b"sk_test_secret:").decode()
    body = json.loads(request.content)
    assert body["given_id"] == "local-uuid" and body["amount"] == 11500 and body["currency"] == "SAR"
    assert body["splits"] == [
        {"recipient_id": "merchant_entity", "amount": 10500, "reference": "ORD-1:merchant", "fee_source": False,
         "refundable": True},
        {"recipient_id": "platform_entity", "amount": 1000, "reference": "ORD-1:platform", "fee_source": True,
         "refundable": True},
    ]  # fmt: skip
    assert payment.status == PaymentStatus.PENDING
    assert payment.transaction_url == "https://moyasar.test/3ds"


async def test_split_payment_guards() -> None:
    recorder = Recorder(_payment_response())
    with pytest.raises(ProviderCapabilityUnavailable):
        await recorder.provider(moyasar_splits_enabled=False).create_split_payment(_split_request())
    provider = recorder.provider()
    with pytest.raises(ValidationFailed):  # raw card data never passes through the backend
        await provider.create_split_payment(_split_request(source={"type": "creditcard", "number": "4111"}))
    with pytest.raises(ValidationFailed):  # fee source must be explicit
        await provider.create_split_payment(
            _split_request(
                splits=(
                    SplitInstruction("merchant_entity", 10500, "r1", False, True),
                    SplitInstruction("platform_entity", 1000, "r2", False, True),
                )
            )
        )
    with pytest.raises(ValidationFailed):  # sum must match
        await provider.create_split_payment(
            _split_request(splits=(SplitInstruction("merchant_entity", 100, "r1", True, True),))
        )
    assert recorder.requests == []


async def test_paid_and_refund_mapping() -> None:
    recorder = Recorder(_payment_response(status="paid", refunded=3000, fee=250))
    provider = recorder.provider()
    payment = await provider.refund_payment("pay_123", 3000)
    assert str(recorder.requests[0].url) == "https://api.moyasar.com/v1/payments/pay_123/refund"
    assert json.loads(recorder.requests[0].content) == {"amount": 3000}
    assert payment.status == PaymentStatus.PARTIALLY_REFUNDED
    assert payment.refunded_amount == 3000 and payment.fee == 250


async def test_provider_errors_are_surfaced() -> None:
    recorder = Recorder({"type": "invalid_request_error", "message": "Amount is invalid"}, status=400)
    with pytest.raises(ProviderError, match="Amount is invalid"):
        await recorder.provider().retrieve_payment("pay_123")


async def test_missing_credentials_never_call_the_provider() -> None:
    recorder = Recorder(_payment_response())
    # Startup validation refuses this configuration; the adapter also guards at call time.
    unconfigured = settings().model_copy(update={"moyasar_secret_key": None})
    provider = MoyasarProvider(unconfigured, httpx.AsyncClient(transport=httpx.MockTransport(recorder)))
    with pytest.raises(ProviderCapabilityUnavailable):
        await provider.retrieve_payment("pay_123")
    with pytest.raises(ValueError, match="MOYASAR_SECRET_KEY"):
        settings(moyasar_secret_key=None)
    assert recorder.requests == []


def _merchant_input() -> MerchantAccountInput:
    return MerchantAccountInput(
        merchant_id="m-1",
        business_type="establishment",
        name="store_abc",
        public_name="Store ABC",
        email="info@store.test",
        admin_email="owner@store.test",
        website="https://store.test",
        owners_count=1,
        signatory="owner",
        signatory_count=None,
        activity_license_required=False,
    )


async def test_merchant_onboarding_request() -> None:
    recorder = Recorder(
        {"id": "mrc_1", "entity_id": "ent_1", "status": "pending", "required_documents": [], "api_keys": "secret"}
    )
    account = await recorder.provider().create_merchant_account(_merchant_input())
    request = recorder.requests[0]
    assert str(request.url) == "https://apimig.moyasar.com/v1/merchants"
    assert request.headers["authorization"] == "Basic " + base64.b64encode(b"platform_key:").decode()
    body = json.loads(request.content)
    for field in ("type", "name", "public_name", "country", "time_zone", "website", "email", "admin_email",
                  "owners_count", "signatory", "activity_license_required", "enabled_schemes", "fees"):  # fmt: skip
        assert field in body, field
    assert body["fees"] == FEES and body["enabled_schemes"] == ["mada", "visa", "master"]
    assert "signatory_count" not in body
    assert account.provider_account_id == "mrc_1" and account.recipient_id == "ent_1"
    assert "api_keys" not in json.dumps(account.details)


async def test_merchant_onboarding_requires_contractual_fees() -> None:
    recorder = Recorder({})
    with pytest.raises(ProviderCapabilityUnavailable, match="MOYASAR_MERCHANT_FEES"):
        await recorder.provider(moyasar_merchant_fees=None).create_merchant_account(_merchant_input())
    assert recorder.requests == []


async def test_unknown_merchant_status_is_an_error() -> None:
    recorder = Recorder({"id": "mrc_1", "status": "something_new"})
    with pytest.raises(ProviderError):
        await recorder.provider().get_merchant_account("mrc_1")


def _webhook(secret: str | None, *, live: bool = False, event_type: str = "payment_paid") -> WebhookRequest:
    payload = {
        "id": "evt_1",
        "type": event_type,
        "created_at": "2026-11-08T10:00:00Z",
        "secret_token": secret,
        "account_name": "platform",
        "live": live,
        "data": {"id": "pay_123", "status": "paid"},
    }
    return WebhookRequest(headers={}, body=json.dumps(payload).encode())


async def test_webhook_shared_secret_verification() -> None:
    provider = Recorder({}).provider()
    event = await provider.verify_webhook(_webhook("whsec_payments"))
    assert event.kind == WebhookKind.PAYMENT and event.object_id == "pay_123"
    assert "secret_token" not in event.payload  # secrets are never persisted
    merchant_event = await provider.verify_webhook(_webhook("whsec_platform", event_type="merchant_activated"))
    assert merchant_event.kind == WebhookKind.MERCHANT_ACCOUNT
    # Header form (X-Event-Secret) is accepted too.
    body = json.dumps({"id": "evt_2", "type": "payment_paid", "live": False, "data": {"id": "p"}}).encode()
    assert (await provider.verify_webhook(WebhookRequest({"x-event-secret": "whsec_payments"}, body))).event_id
    for bad in (_webhook("wrong"), _webhook(None), _webhook("whsec_payments", live=True)):
        with pytest.raises(InvalidWebhook):
            await provider.verify_webhook(bad)
    with pytest.raises(InvalidWebhook):
        await provider.verify_webhook(WebhookRequest({}, b"not json"))


async def test_undocumented_capabilities_are_refused() -> None:
    provider = Recorder({}).provider()
    unsupported = await provider.verify_webhook(_webhook("whsec_payments", event_type="balance_transferred"))
    assert unsupported.kind == WebhookKind.UNSUPPORTED  # stored for manual reconciliation only
    with pytest.raises(ProviderCapabilityUnavailable):
        await provider.get_settlement("st_1")


def test_mock_provider_cannot_run_in_production() -> None:
    with pytest.raises(ValueError, match="mock payment provider"):
        Settings(environment="production", payment_provider="mock", cookie_secure=True, jwt_secret=SecretStr("x" * 40))
