"""Webhook processing: authenticated, persisted, idempotent and order-independent.

1. The provider adapter authenticates the request (documented mechanism only).
2. The event id is persisted (unique per provider). A processed duplicate is a no-op.
3. Processing never trusts the payload's state: it looks up the current state from
   the provider and applies it monotonically, so out-of-order events are harmless.
4. Failures are recorded and answered with HTTP 500 so the provider retries;
   administrators can also reprocess failed events.
"""

import contextlib
import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import AppError, NotFound
from app.core.security import utcnow
from app.integrations.payments.base import (
    InvalidWebhook,
    PaymentProvider,
    WebhookEvent,
    WebhookKind,
    WebhookRequest,
)
from app.modules.merchants.models import MerchantPaymentAccount
from app.modules.merchants.service import sync_payment_account
from app.modules.payments import chargebacks
from app.modules.payments.models import (
    Chargeback,
    ChargebackStatus,
    Payment,
    PaymentWebhookEvent,
    WebhookEventStatus,
)
from app.modules.payments.service import apply_provider_state
from app.modules.settlements.models import ConfirmationSource
from app.modules.settlements.service import record_provider_settlement

log = structlog.get_logger(__name__)


class RetryableWebhookError(Exception):
    """The event cannot be processed yet (e.g. the payment row is not committed)."""


@dataclass
class WebhookResult:
    status_code: int
    outcome: str
    event_id: str | None = None


async def _find_payment(session: AsyncSession, provider: PaymentProvider, object_id: str | None) -> Payment:
    if not object_id:
        raise RetryableWebhookError("Event has no payment id.")
    conditions = [Payment.provider_payment_id == object_id]
    with contextlib.suppress(ValueError):
        conditions.append(Payment.id == uuid.UUID(object_id))  # given_id == our payment id
    payment = (
        await session.exec(select(Payment).where(Payment.provider == provider.name, or_(*conditions)).with_for_update())
    ).first()
    if payment is None:
        raise RetryableWebhookError(f"Payment {object_id} not found yet.")
    return payment


async def _dispatch(session: AsyncSession, provider: PaymentProvider, event: WebhookEvent) -> WebhookEventStatus:
    match event.kind:
        case WebhookKind.PAYMENT:
            payment = await _find_payment(session, provider, event.object_id)
            remote = await provider.retrieve_payment(payment.provider_payment_id or str(payment.id))
            await apply_provider_state(session, payment, remote, provider)
            return WebhookEventStatus.PROCESSED
        case WebhookKind.MERCHANT_ACCOUNT:
            account = (
                await session.exec(
                    select(MerchantPaymentAccount)
                    .where(
                        MerchantPaymentAccount.provider == provider.name,
                        MerchantPaymentAccount.provider_account_id == event.object_id,
                    )
                    .with_for_update()
                )
            ).first()
            if account is None:
                return WebhookEventStatus.IGNORED
            await sync_payment_account(session, account, provider)
            return WebhookEventStatus.PROCESSED
        case WebhookKind.SETTLEMENT:
            if not event.object_id:
                return WebhookEventStatus.IGNORED
            remote_settlement = await provider.get_settlement(event.object_id)
            await record_provider_settlement(
                session,
                provider,
                remote_settlement,
                source=ConfirmationSource.PROVIDER_WEBHOOK,
                reference=event.event_id,
            )
            return WebhookEventStatus.PROCESSED
        case WebhookKind.CHARGEBACK:
            if not event.object_id:
                return WebhookEventStatus.IGNORED
            remote_cb = await provider.get_chargeback(event.object_id)
            payment = await _find_payment(session, provider, remote_cb.provider_payment_id)
            chargeback = (
                await session.exec(
                    select(Chargeback).where(
                        Chargeback.payment_id == payment.id,
                        Chargeback.provider_reference == remote_cb.provider_reference,
                    )
                )
            ).first()
            if chargeback is None:
                chargeback = await chargebacks.open_chargeback(
                    session,
                    payment,
                    amount=remote_cb.amount,
                    provider_reference=remote_cb.provider_reference,
                    reason=remote_cb.reason,
                    actor_user_id=None,
                )
            if remote_cb.status in {"WON", "LOST"}:
                await chargebacks.resolve_chargeback(
                    session, chargeback, outcome=ChargebackStatus(remote_cb.status), actor_user_id=None
                )
            return WebhookEventStatus.PROCESSED
        case _:
            # Stored for manual reconciliation; never applied automatically.
            return WebhookEventStatus.IGNORED


async def _process_event_row(
    session: AsyncSession, provider: PaymentProvider, row: PaymentWebhookEvent, event: WebhookEvent
) -> WebhookResult:
    if row.status in {WebhookEventStatus.PROCESSED.value, WebhookEventStatus.IGNORED.value}:
        return WebhookResult(200, "duplicate", event.event_id)
    row.attempts += 1
    try:
        async with session.begin_nested():
            outcome = await _dispatch(session, provider, event)
    except (RetryableWebhookError, AppError, Exception) as exc:
        row.status = WebhookEventStatus.FAILED.value
        row.last_error = f"{exc.__class__.__name__}: {exc}"[:2000]
        log.warning("webhook_processing_failed", event_id=event.event_id, error=row.last_error)
        await session.flush()
        return WebhookResult(500, "failed", event.event_id)
    row.status = outcome.value
    row.processed_at = utcnow()
    row.last_error = None
    await session.flush()
    return WebhookResult(200, outcome.value.lower(), event.event_id)


async def handle_webhook(session: AsyncSession, provider: PaymentProvider, request: WebhookRequest) -> WebhookResult:
    try:
        event = await provider.verify_webhook(request)
    except InvalidWebhook as exc:
        log.warning("webhook_rejected", provider=provider.name, reason=str(exc))
        return WebhookResult(401, "rejected")

    await session.exec(
        insert(PaymentWebhookEvent)
        .values(
            id=uuid.uuid4(),
            provider=provider.name,
            event_id=event.event_id,
            event_type=event.event_type,
            status=WebhookEventStatus.RECEIVED.value,
            attempts=0,
            is_live=event.is_live,
            payload=event.payload,
        )
        .on_conflict_do_nothing(index_elements=["provider", "event_id"])
    )
    row = (
        await session.exec(
            select(PaymentWebhookEvent)
            .where(PaymentWebhookEvent.provider == provider.name, PaymentWebhookEvent.event_id == event.event_id)
            .with_for_update()
        )
    ).first()
    assert row is not None
    return await _process_event_row(session, provider, row, event)


async def reprocess_event(session: AsyncSession, provider: PaymentProvider, event_row_id: uuid.UUID) -> WebhookResult:
    row = await session.get(PaymentWebhookEvent, event_row_id, with_for_update=True)
    if row is None or row.provider != provider.name:
        raise NotFound("Webhook event not found.")
    payload = row.payload
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    assert isinstance(data, dict)
    kind = provider.classify_event(row.event_type)
    event = WebhookEvent(
        event_id=row.event_id,
        event_type=row.event_type,
        kind=kind,
        object_id=str(data.get("id")) if data.get("id") else None,
        is_live=row.is_live,
        payload=payload,
        data=data,
    )
    if row.status == WebhookEventStatus.FAILED.value:
        row.status = WebhookEventStatus.RECEIVED.value
    return await _process_event_row(session, provider, row, event)
