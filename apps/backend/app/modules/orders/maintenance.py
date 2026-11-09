"""Periodic maintenance: expire unpaid checkouts and dispatch queued emails.

Runs in-process (no separate queue) because it is light and idempotent; multiple
instances are safe thanks to row locks with SKIP LOCKED.
"""

import asyncio

import structlog
from sqlmodel import col, select

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import utcnow
from app.database.session import get_sessionmaker
from app.integrations.payments.base import PaymentProvider
from app.integrations.payments.factory import get_payment_provider
from app.modules.notifications.service import dispatch_pending_emails
from app.modules.orders import service as orders
from app.modules.orders.models import MerchantOrder, MerchantOrderStatus
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.payments.service import sync_payment

log = structlog.get_logger(__name__)


async def expire_reservations(provider: PaymentProvider, limit: int = 100) -> int:
    expired = 0
    async with get_sessionmaker()() as session:
        rows = (
            await session.exec(
                select(MerchantOrder)
                .where(
                    MerchantOrder.status == MerchantOrderStatus.PENDING_PAYMENT.value,
                    col(MerchantOrder.reservation_expires_at) < utcnow(),
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for mo in rows:
            # Check in-flight payments with the provider first: they may have succeeded.
            pending = (
                await session.exec(
                    select(Payment)
                    .where(
                        Payment.merchant_order_id == mo.id,
                        col(Payment.status).in_([PaymentStatus.PENDING.value, PaymentStatus.AUTHORIZED.value]),
                    )
                    .with_for_update()
                )
            ).all()
            for payment in pending:
                try:
                    async with session.begin_nested():
                        await sync_payment(session, payment, provider)
                except AppError as exc:
                    log.warning("expiry_sync_failed", payment_id=str(payment.id), error=exc.message)
            await session.refresh(mo)
            if mo.status == MerchantOrderStatus.PENDING_PAYMENT.value:
                await orders.cancel_unpaid(session, mo, actor_user_id=None, reason="Checkout expired")
                expired += 1
        await session.commit()
    return expired


async def run_once() -> None:
    provider = get_payment_provider()
    expired = await expire_reservations(provider)
    async with get_sessionmaker()() as session:
        sent = await dispatch_pending_emails(session)
        await session.commit()
    if expired or sent:
        log.info("maintenance_run", expired_checkouts=expired, emails_sent=sent)


async def maintenance_loop() -> None:
    interval = get_settings().maintenance_interval_seconds
    while True:
        try:
            await run_once()
        except Exception as exc:
            log.exception("maintenance_failed", error=str(exc))
        await asyncio.sleep(interval)
