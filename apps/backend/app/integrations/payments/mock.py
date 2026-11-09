"""Mock payment provider for development and automated tests.

It simulates a marketplace provider (merchant onboarding, split payments, refunds,
settlements, chargebacks and signed webhooks) without moving any money. Every
payment it creates is flagged ``is_test`` and the provider refuses to run in
production (see ``Settings._guard_production``).
"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings
from app.core.errors import NotFound, ProviderError, ValidationFailed
from app.core.money import percentage_of
from app.core.security import constant_time_equals
from app.integrations.payments.base import (
    InvalidWebhook,
    MerchantAccountInput,
    PaymentProvider,
    PaymentRequest,
    ProviderCapabilities,
    ProviderChargeback,
    ProviderMerchantAccount,
    ProviderPayment,
    ProviderSettlement,
    SplitPaymentRequest,
    WebhookEvent,
    WebhookKind,
    WebhookRequest,
)
from app.integrations.payments.mock_models import MockProviderRecord, MockRecordKind
from app.modules.merchants.models import OnboardingStatus
from app.modules.payments.models import PaymentStatus

MOCK_PLATFORM_RECIPIENT_ID = "mock_platform"
SIGNATURE_HEADER = "x-mock-signature"
# Deterministic mock processing fee: 1.5% + 0.50 SAR.
MOCK_FEE_RATE = Decimal("1.5")
MOCK_FEE_FIXED = 50

_MERCHANT_STATUS = {
    "pending": OnboardingStatus.PENDING,
    "under_review": OnboardingStatus.UNDER_REVIEW,
    "missing_docs": OnboardingStatus.ACTION_REQUIRED,
    "active": OnboardingStatus.ACTIVE,
    "rejected": OnboardingStatus.REJECTED,
    "disabled": OnboardingStatus.DISABLED,
}


def mock_fee(amount: int) -> int:
    return percentage_of(amount, MOCK_FEE_RATE) + MOCK_FEE_FIXED


def _status(raw: str, amount: int, refunded: int) -> PaymentStatus:
    if raw == "paid":
        if refunded >= amount:
            return PaymentStatus.REFUNDED
        return PaymentStatus.PARTIALLY_REFUNDED if refunded else PaymentStatus.PAID
    return {
        "initiated": PaymentStatus.PENDING,
        "authorized": PaymentStatus.AUTHORIZED,
        "failed": PaymentStatus.FAILED,
        "voided": PaymentStatus.CANCELLED,
    }[raw]


class MockPaymentProvider(PaymentProvider):
    name = "mock"
    capabilities = ProviderCapabilities(
        supports_splits=True,
        max_merchants_per_payment=1,
        supports_settlement_lookup=True,
        supports_chargeback_events=True,
        notes=("Mock provider: no real money is processed.",),
    )

    def __init__(self, settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._settings = settings
        self._sessionmaker = sessionmaker

    @property
    def is_test(self) -> bool:
        return True

    @property
    def platform_recipient_id(self) -> str:
        return MOCK_PLATFORM_RECIPIENT_ID

    # -- record helpers (the mock "remote" system commits independently) ---------------

    async def _get(self, session: AsyncSession, kind: MockRecordKind, external_id: str) -> MockProviderRecord:
        record = (
            await session.exec(
                select(MockProviderRecord)
                .where(MockProviderRecord.kind == kind.value, MockProviderRecord.external_id == external_id)
                .with_for_update()
            )
        ).first()
        if record is None:
            raise NotFound(f"Mock {kind.value.lower()} {external_id} not found.")
        return record

    async def read(self, kind: MockRecordKind, external_id: str) -> dict[str, Any]:
        async with self._sessionmaker() as session:
            record = await self._get(session, kind, external_id)
            return dict(record.data)

    async def write(self, kind: MockRecordKind, external_id: str, data: dict[str, Any]) -> dict[str, Any]:
        async with self._sessionmaker() as session, session.begin():
            record = (
                await session.exec(
                    select(MockProviderRecord)
                    .where(MockProviderRecord.kind == kind.value, MockProviderRecord.external_id == external_id)
                    .with_for_update()
                )
            ).first()
            if record is None:
                session.add(MockProviderRecord(kind=kind.value, external_id=external_id, data=data))
            else:
                record.data = data
        return data

    def _to_payment(self, data: dict[str, Any]) -> ProviderPayment:
        return ProviderPayment(
            provider_payment_id=data["id"],
            status=_status(data["status"], data["amount"], data["refunded"]),
            raw_status=data["status"],
            amount=data["amount"],
            refunded_amount=data["refunded"],
            currency=data["currency"],
            fee=data.get("fee"),
            transaction_url=data.get("transaction_url"),
            failure_reason=data.get("failure_reason"),
            is_live=False,
            payment_method="mock",
            raw=data,
        )

    def _to_merchant(self, data: dict[str, Any]) -> ProviderMerchantAccount:
        return ProviderMerchantAccount(
            provider_account_id=data["id"],
            recipient_id=data["entity_id"],
            raw_status=data["status"],
            onboarding_status=_MERCHANT_STATUS[data["status"]],
            payouts_enabled=data["status"] == "active",
            required_documents=[{"type": t} for t in data.get("required_documents", [])],
            reasons=list(data.get("reasons", [])),
            details={"mock": True},
        )

    # -- payments -------------------------------------------------------------------------

    async def _create(self, data: PaymentRequest, splits: list[dict[str, Any]]) -> ProviderPayment:
        if data.currency != "SAR":
            raise ValidationFailed("Mock provider only supports SAR.")
        source_type = data.source.get("type")
        if source_type != "mock":
            raise ValidationFailed("The mock provider requires source.type = 'mock'.")
        outcome = data.source.get("outcome", "redirect")
        record: dict[str, Any] = {
            "id": data.payment_id,  # mirrors `given_id` semantics
            "amount": data.amount,
            "currency": data.currency,
            "refunded": 0,
            "fee": None,
            "status": "initiated",
            "splits": splits,
            "callback_url": data.callback_url,
            "metadata": dict(data.metadata),
            "transaction_url": (
                f"{self._settings.public_api_url}/api/v1/mock-provider/payments/{data.payment_id}/checkout"
            ),
            "failure_reason": None,
        }
        if outcome == "paid":
            record.update(status="paid", fee=mock_fee(data.amount), transaction_url=None)
        elif outcome == "failed":
            record.update(status="failed", failure_reason="Card declined (mock)", transaction_url=None)
        async with self._sessionmaker() as session:
            exists = (
                await session.exec(
                    select(MockProviderRecord.id).where(
                        MockProviderRecord.kind == MockRecordKind.PAYMENT.value,
                        MockProviderRecord.external_id == data.payment_id,
                    )
                )
            ).first()
        if exists:  # idempotent create, like `given_id`
            return self._to_payment(await self.read(MockRecordKind.PAYMENT, data.payment_id))
        await self.write(MockRecordKind.PAYMENT, data.payment_id, record)
        return self._to_payment(record)

    async def create_payment(self, data: PaymentRequest) -> ProviderPayment:
        return await self._create(data, [])

    async def create_split_payment(self, data: SplitPaymentRequest) -> ProviderPayment:
        if sum(s.amount for s in data.splits) != data.amount:
            raise ValidationFailed("Split totals must equal the payment amount.")
        if sum(1 for s in data.splits if s.is_fee_source) > 1:
            raise ValidationFailed("At most one split can be the fee source.")
        splits = [
            {
                "recipient_id": s.recipient_id,
                "amount": s.amount,
                "reference": s.reference,
                "fee_source": s.is_fee_source,
                "refundable": s.refundable,
            }
            for s in data.splits
        ]
        return await self._create(data, splits)

    async def retrieve_payment(self, payment_id: str) -> ProviderPayment:
        return self._to_payment(await self.read(MockRecordKind.PAYMENT, payment_id))

    async def complete_hosted_payment(self, payment_id: str, outcome: str) -> ProviderPayment:
        """Simulates the payer completing (or failing) the hosted payment step."""
        data = await self.read(MockRecordKind.PAYMENT, payment_id)
        if data["status"] != "initiated":
            return self._to_payment(data)
        if outcome == "paid":
            data.update(status="paid", fee=mock_fee(data["amount"]))
        else:
            data.update(status="failed", failure_reason="Card declined (mock)")
        data["transaction_url"] = None
        await self.write(MockRecordKind.PAYMENT, payment_id, data)
        return self._to_payment(data)

    async def refund_payment(self, payment_id: str, amount: int | None = None) -> ProviderPayment:
        data = await self.read(MockRecordKind.PAYMENT, payment_id)
        if data["status"] != "paid":
            raise ProviderError("Only paid payments can be refunded.")
        remaining = data["amount"] - data["refunded"]
        refund = remaining if amount is None else amount
        if refund <= 0 or refund > remaining:
            raise ProviderError("Refund amount exceeds the refundable amount.")
        data["refunded"] += refund
        await self.write(MockRecordKind.PAYMENT, payment_id, data)
        return self._to_payment(data)

    # -- merchants ------------------------------------------------------------------------

    async def create_merchant_account(self, data: MerchantAccountInput) -> ProviderMerchantAccount:
        account_id = f"mock_merchant_{uuid.uuid4().hex[:16]}"
        record = {
            "id": account_id,
            "entity_id": f"mock_entity_{uuid.uuid4().hex[:16]}",
            "status": "pending",
            "name": data.name,
            "reasons": [],
        }
        await self.write(MockRecordKind.MERCHANT, account_id, record)
        return self._to_merchant(record)

    async def get_merchant_account(self, account_id: str) -> ProviderMerchantAccount:
        return self._to_merchant(await self.read(MockRecordKind.MERCHANT, account_id))

    async def submit_merchant_account(self, account_id: str) -> ProviderMerchantAccount:
        data = await self.read(MockRecordKind.MERCHANT, account_id)
        data["status"] = "active" if self._settings.mock_auto_activate_merchants else "under_review"
        data["reasons"] = []
        await self.write(MockRecordKind.MERCHANT, account_id, data)
        return self._to_merchant(data)

    async def set_merchant_status(
        self, account_id: str, status: str, reasons: list[str], required_documents: list[str] | None = None
    ) -> ProviderMerchantAccount:
        if status not in _MERCHANT_STATUS:
            raise ValidationFailed(f"Unknown mock merchant status {status!r}.")
        data = await self.read(MockRecordKind.MERCHANT, account_id)
        data.update(status=status, reasons=reasons, required_documents=required_documents or [])
        await self.write(MockRecordKind.MERCHANT, account_id, data)
        return self._to_merchant(data)

    # -- settlements & chargebacks ------------------------------------------------------

    async def create_settlement(self, recipient_id: str, amount: int, *, failed: bool = False) -> ProviderSettlement:
        settlement_id = f"mock_settlement_{uuid.uuid4().hex[:16]}"
        record = {
            "id": settlement_id,
            "recipient_id": recipient_id,
            "amount": amount,
            "currency": "SAR",
            "status": "FAILED" if failed else "COMPLETED",
            "completed_at": None if failed else datetime.now(UTC).isoformat(),
            "failure_reason": "Beneficiary bank rejected the transfer (mock)" if failed else None,
        }
        await self.write(MockRecordKind.SETTLEMENT, settlement_id, record)
        return self._to_settlement(record)

    def _to_settlement(self, data: dict[str, Any]) -> ProviderSettlement:
        completed = data.get("completed_at")
        return ProviderSettlement(
            provider_settlement_id=data["id"],
            recipient_id=data["recipient_id"],
            amount=data["amount"],
            currency=data["currency"],
            status=data["status"],
            completed_at=datetime.fromisoformat(completed) if completed else None,
            failure_reason=data.get("failure_reason"),
            raw=data,
        )

    async def get_settlement(self, settlement_id: str) -> ProviderSettlement:
        return self._to_settlement(await self.read(MockRecordKind.SETTLEMENT, settlement_id))

    async def upsert_chargeback(
        self, provider_payment_id: str, amount: int, status: str, reference: str | None = None
    ) -> ProviderChargeback:
        reference = reference or f"mock_cb_{uuid.uuid4().hex[:12]}"
        record = {
            "id": reference,
            "payment_id": provider_payment_id,
            "amount": amount,
            "status": status,
            "reason": "Cardholder dispute (mock)",
        }
        await self.write(MockRecordKind.CHARGEBACK, reference, record)
        return self._to_chargeback(record)

    def _to_chargeback(self, data: dict[str, Any]) -> ProviderChargeback:
        return ProviderChargeback(
            provider_reference=data["id"],
            provider_payment_id=data["payment_id"],
            amount=data["amount"],
            status=data["status"],
            reason=data["reason"],
        )

    async def get_chargeback(self, reference: str) -> ProviderChargeback:
        return self._to_chargeback(await self.read(MockRecordKind.CHARGEBACK, reference))

    # -- webhooks -------------------------------------------------------------------------

    def _sign(self, body: bytes) -> str:
        secret = self._settings.mock_webhook_secret.get_secret_value().encode()
        return hmac.new(secret, body, hashlib.sha256).hexdigest()

    def build_webhook(self, event_type: str, data: dict[str, Any], event_id: str | None = None) -> WebhookRequest:
        payload = {
            "id": event_id or str(uuid.uuid4()),
            "type": event_type,
            "created_at": datetime.now(UTC).isoformat(),
            "live": False,
            "data": data,
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        return WebhookRequest(headers={SIGNATURE_HEADER: self._sign(body)}, body=body)

    def classify_event(self, event_type: str) -> WebhookKind:
        return {
            "payment": WebhookKind.PAYMENT,
            "merchant": WebhookKind.MERCHANT_ACCOUNT,
            "settlement": WebhookKind.SETTLEMENT,
            "chargeback": WebhookKind.CHARGEBACK,
        }.get(event_type.split(".")[0], WebhookKind.UNSUPPORTED)

    async def verify_webhook(self, request: WebhookRequest) -> WebhookEvent:
        signature = request.headers.get(SIGNATURE_HEADER)
        if not signature or not constant_time_equals(signature, self._sign(request.body)):
            raise InvalidWebhook("Invalid mock webhook signature.")
        try:
            payload = json.loads(request.body)
        except ValueError as exc:
            raise InvalidWebhook("Malformed JSON payload.") from exc
        event_type = str(payload.get("type", ""))
        kind = self.classify_event(event_type)
        data = payload.get("data") or {}
        return WebhookEvent(
            event_id=str(payload["id"]),
            event_type=event_type,
            kind=kind,
            object_id=str(data.get("id")) if data.get("id") else None,
            is_live=False,
            payload=payload,
            data=data,
        )
