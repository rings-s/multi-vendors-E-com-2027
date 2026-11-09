"""Chargebacks (disputes).

Opening a chargeback marks the payment DISPUTED (refunds are blocked meanwhile).
A LOST chargeback reverses the allocations proportionally in the ledger, exactly
like a refund; a WON chargeback restores the previous payment status.

Moyasar chargeback events/APIs are not part of the verified documentation, so with
Moyasar chargebacks are recorded by an administrator from the provider's notice.
"""

import uuid

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.security import utcnow
from app.modules.admin.audit import record_audit
from app.modules.ledger.models import LedgerTransactionType
from app.modules.payments.models import CAPTURED_STATUSES, Chargeback, ChargebackStatus, Payment, PaymentStatus
from app.modules.payments.refunds import post_reversal, reversed_totals, split_portions


async def open_chargeback(
    session: AsyncSession,
    payment: Payment,
    *,
    amount: int,
    provider_reference: str,
    reason: str,
    actor_user_id: uuid.UUID | None,
) -> Chargeback:
    await session.flush()  # never discard unflushed changes when reloading
    payment = await session.get(Payment, payment.id, with_for_update=True, populate_existing=True)  # type: ignore[assignment]
    assert payment is not None
    existing = (
        await session.exec(
            select(Chargeback).where(
                Chargeback.payment_id == payment.id, Chargeback.provider_reference == provider_reference
            )
        )
    ).first()
    if existing is not None:
        return existing
    if payment.status not in {s.value for s in CAPTURED_STATUSES} or payment.status == PaymentStatus.DISPUTED.value:
        raise Conflict("Only captured, undisputed payments can be disputed.", code="not_disputable")
    already = await reversed_totals(session, payment.id)
    if amount <= 0 or amount > payment.amount - already.amount:
        raise ValidationFailed("Chargeback amount exceeds the remaining captured amount.", code="invalid_amount")
    chargeback = Chargeback(
        payment_id=payment.id,
        merchant_id=payment.merchant_id,
        amount=amount,
        currency=payment.currency,
        status=ChargebackStatus.OPEN.value,
        reason=reason,
        provider_reference=provider_reference,
        previous_payment_status=payment.status,
        recorded_by_user_id=actor_user_id,
        opened_at=utcnow(),
    )
    session.add(chargeback)
    payment.status = PaymentStatus.DISPUTED.value
    await session.flush()
    await record_audit(
        session,
        actor_user_id=actor_user_id,
        action="chargeback.open",
        entity_type="chargeback",
        entity_id=chargeback.id,
        after={"payment_id": str(payment.id), "amount": amount, "reference": provider_reference},
    )
    return chargeback


async def resolve_chargeback(
    session: AsyncSession, chargeback: Chargeback, *, outcome: ChargebackStatus, actor_user_id: uuid.UUID | None
) -> Chargeback:
    if chargeback.status != ChargebackStatus.OPEN.value:
        if chargeback.status == outcome.value:
            return chargeback  # idempotent
        raise Conflict("This chargeback is already resolved.", code="chargeback_resolved")
    if outcome == ChargebackStatus.OPEN:
        raise ValidationFailed("Outcome must be WON or LOST.")
    await session.flush()  # never discard unflushed changes when reloading
    payment = await session.get(Payment, chargeback.payment_id, with_for_update=True, populate_existing=True)
    assert payment is not None
    if outcome == ChargebackStatus.LOST:
        already = await reversed_totals(session, payment.id)
        portions = split_portions(payment, chargeback.amount, already)
        chargeback.merchant_portion = portions.merchant
        chargeback.platform_portion = portions.platform
        chargeback.delivery_portion = portions.delivery
        chargeback.delivery_platform_portion = portions.delivery_platform
        await post_reversal(
            session,
            payment,
            source_type="chargeback",
            source_id=chargeback.id,
            transaction_type=LedgerTransactionType.CHARGEBACK,
            portions=portions,
            description=f"Chargeback lost {chargeback.provider_reference}",
        )
        # The payment stays DISPUTED as the record of a lost dispute.
    else:
        payment.status = chargeback.previous_payment_status
    chargeback.status = outcome.value
    chargeback.resolved_at = utcnow()
    await record_audit(
        session,
        actor_user_id=actor_user_id,
        action=f"chargeback.{outcome.value.lower()}",
        entity_type="chargeback",
        entity_id=chargeback.id,
        after={"status": outcome.value},
    )
    await session.flush()
    return chargeback


async def get_chargeback(session: AsyncSession, chargeback_id: uuid.UUID) -> Chargeback:
    chargeback = await session.get(Chargeback, chargeback_id, with_for_update=True)
    if chargeback is None:
        raise NotFound("Chargeback not found.")
    return chargeback
