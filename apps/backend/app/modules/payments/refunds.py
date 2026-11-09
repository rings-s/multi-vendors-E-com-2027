"""Refunds (full and partial) that account for the original split allocation.

A payment has two components: GOODS (items incl. their VAT) and DELIVERY (the
delivery fee incl. its VAT). Each refund (and lost chargeback) is first assigned to
components by its scope:

* AUTO — items first; the delivery charge only once the items are fully refunded
  (a full refund therefore covers both);
* ITEMS — items only;
* DELIVERY — the delivery charge only (e.g. a failed or late delivery).

Within a component, the reversal between platform and merchant is proportional and
cumulative so rounding never drifts: after refunding a cumulative amount R of a
component with total T and platform part P, the platform has reversed
round_half_up(R * P / T); the merchant reverses the rest. A full refund therefore
reverses each allocation exactly. Without a delivery charge this is exactly the
single-component calculation.

The provider's actual recovery behaviour is configured per split (``refundable``);
reconciliation compares provider records with this ledger.
"""

import uuid
from dataclasses import dataclass

import structlog
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import AppError, Conflict, NotFound, ValidationFailed
from app.core.money import proportional_share
from app.core.security import utcnow
from app.integrations.payments.base import PaymentProvider
from app.modules.ledger import service as ledger
from app.modules.ledger.models import AccountType, Direction, LedgerComponent, LedgerTransactionType
from app.modules.merchants.models import Merchant
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import notify
from app.modules.orders import inventory
from app.modules.orders import service as orders
from app.modules.orders.models import MerchantOrder, MerchantOrderStatus
from app.modules.payments.models import (
    ACTIVE_REFUND_STATUSES,
    Chargeback,
    ChargebackStatus,
    Payment,
    PaymentStatus,
    RecipientType,
    Refund,
    RefundInitiator,
    RefundScope,
    RefundStatus,
)

log = structlog.get_logger(__name__)
REFUNDABLE_PAYMENT_STATUSES = {PaymentStatus.PAID.value, PaymentStatus.PARTIALLY_REFUNDED.value}
SHIPPED_OR_LATER = {
    MerchantOrderStatus.SHIPPED.value,
    MerchantOrderStatus.DELIVERED.value,
    MerchantOrderStatus.COMPLETED.value,
}


@dataclass(frozen=True)
class Reversed:
    """What active refunds and lost chargebacks have already reversed on a payment."""

    amount: int = 0
    platform: int = 0
    delivery: int = 0
    delivery_platform: int = 0


@dataclass(frozen=True)
class Portions:
    merchant: int
    platform: int
    delivery: int  # part of the amount reversing the delivery charge
    delivery_platform: int  # platform's share of ``delivery``

    @property
    def amount(self) -> int:
        return self.merchant + self.platform


@dataclass(frozen=True)
class Components:
    """A payment's component totals and what remains refundable of each."""

    goods_total: int
    goods_platform: int
    delivery_total: int
    delivery_platform: int
    goods_left: int
    delivery_left: int


async def reversed_totals(session: AsyncSession, payment_id: uuid.UUID) -> Reversed:
    def sums(model: type[Refund] | type[Chargeback]) -> tuple[object, ...]:
        return (
            func.coalesce(func.sum(model.amount), 0),
            func.coalesce(func.sum(model.platform_portion), 0),
            func.coalesce(func.sum(model.delivery_portion), 0),
            func.coalesce(func.sum(model.delivery_platform_portion), 0),
        )

    refunds = (
        await session.exec(
            select(*sums(Refund)).where(  # type: ignore[call-overload]
                Refund.payment_id == payment_id, col(Refund.status).in_([s.value for s in ACTIVE_REFUND_STATUSES])
            )
        )
    ).one()
    chargebacks = (
        await session.exec(
            select(*sums(Chargeback)).where(  # type: ignore[call-overload]
                Chargeback.payment_id == payment_id, Chargeback.status == ChargebackStatus.LOST.value
            )
        )
    ).one()
    values = [int(a) + int(b) for a, b in zip(refunds, chargebacks, strict=True)]
    return Reversed(*values)


def components(payment: Payment, already: Reversed) -> Components:
    merchant = next(a for a in payment.allocations if a.recipient_type == RecipientType.MERCHANT.value)
    platform = next(a for a in payment.allocations if a.recipient_type == RecipientType.PLATFORM.value)
    delivery_total = merchant.delivery_amount + platform.delivery_amount
    goods_total = payment.amount - delivery_total
    return Components(
        goods_total=goods_total,
        goods_platform=platform.amount - platform.delivery_amount,
        delivery_total=delivery_total,
        delivery_platform=platform.delivery_amount,
        goods_left=max(goods_total - (already.amount - already.delivery), 0),
        delivery_left=max(delivery_total - already.delivery, 0),
    )


def refundable_for(comp: Components, scope: RefundScope) -> int:
    if scope == RefundScope.ITEMS:
        return comp.goods_left
    if scope == RefundScope.DELIVERY:
        return comp.delivery_left
    return comp.goods_left + comp.delivery_left


async def refundable_amount(session: AsyncSession, payment: Payment, scope: RefundScope = RefundScope.AUTO) -> int:
    return refundable_for(components(payment, await reversed_totals(session, payment.id)), scope)


def _cumulative_share(total: int, platform_total: int, already: int, already_platform: int, amount: int) -> int:
    if amount <= 0 or total <= 0:
        return 0
    after = proportional_share(total, platform_total, already + amount)
    return max(0, min(after - already_platform, amount, platform_total - already_platform))


def split_portions(payment: Payment, amount: int, already: Reversed, scope: RefundScope = RefundScope.AUTO) -> Portions:
    """Assign ``amount`` to components, then split each between platform and merchant."""
    comp = components(payment, already)
    if amount > refundable_for(comp, scope):
        raise ValidationFailed(
            "The refund amount exceeds the refundable amount.",
            code="refund_exceeds_refundable",
            details={"refundable": refundable_for(comp, scope)},
        )
    if scope == RefundScope.DELIVERY:
        goods, delivery = 0, amount
    elif scope == RefundScope.ITEMS:
        goods, delivery = amount, 0
    else:
        goods = min(amount, comp.goods_left)
        delivery = amount - goods
    goods_platform = _cumulative_share(
        comp.goods_total,
        comp.goods_platform,
        already.amount - already.delivery,
        already.platform - already.delivery_platform,
        goods,
    )
    delivery_platform = _cumulative_share(
        comp.delivery_total, comp.delivery_platform, already.delivery, already.delivery_platform, delivery
    )
    platform = goods_platform + delivery_platform
    return Portions(
        merchant=amount - platform, platform=platform, delivery=delivery, delivery_platform=delivery_platform
    )


async def post_reversal(
    session: AsyncSession,
    payment: Payment,
    *,
    source_type: str,
    source_id: uuid.UUID,
    transaction_type: LedgerTransactionType,
    portions: Portions,
    description: str,
) -> None:
    mo = await session.get(MerchantOrder, payment.merchant_order_id)
    assert mo is not None
    merchant_delivery = portions.delivery - portions.delivery_platform
    await ledger.post(
        session,
        transaction_type=transaction_type,
        source_type=source_type,
        source_id=source_id,
        merchant_id=payment.merchant_id,
        description=description,
        is_test=payment.is_test,
        lines=[
            ledger.Line(
                AccountType.MERCHANT_PAYABLE,
                Direction.DEBIT,
                portions.merchant - merchant_delivery,
                payment.merchant_id,
                "Items",
                LedgerComponent.GOODS,
            ),
            ledger.Line(
                AccountType.MERCHANT_PAYABLE,
                Direction.DEBIT,
                merchant_delivery,
                payment.merchant_id,
                "Delivery fee",
                LedgerComponent.DELIVERY,
            ),
            ledger.Line(
                AccountType.PLATFORM_COMMISSION,
                Direction.DEBIT,
                portions.platform - portions.delivery_platform,
                None,
                "Item commission",
                LedgerComponent.GOODS,
            ),
            ledger.Line(
                ledger.delivery_platform_account(mo.delivery_fee_recipient),
                Direction.DEBIT,
                portions.delivery_platform,
                None,
                "Delivery",
                LedgerComponent.DELIVERY,
            ),
            ledger.Line(AccountType.PROVIDER_CLEARING, Direction.CREDIT, portions.amount),
        ],
    )


def _apply(record: Refund | Chargeback, portions: Portions) -> None:
    record.merchant_portion = portions.merchant
    record.platform_portion = portions.platform
    record.delivery_portion = portions.delivery
    record.delivery_platform_portion = portions.delivery_platform


async def _lock_payment(session: AsyncSession, payment_id: uuid.UUID) -> Payment:
    await session.flush()  # never discard unflushed changes when reloading
    payment = await session.get(Payment, payment_id, with_for_update=True, populate_existing=True)
    if payment is None:
        raise NotFound("Payment not found.")
    return payment


async def request_refund(
    session: AsyncSession,
    payment: Payment,
    *,
    amount: int | None,
    initiated_by: RefundInitiator,
    actor_user_id: uuid.UUID | None,
    reason: str,
    restock: bool = False,
    scope: RefundScope = RefundScope.AUTO,
) -> Refund:
    payment = await _lock_payment(session, payment.id)
    if payment.status not in REFUNDABLE_PAYMENT_STATUSES:
        raise Conflict("This payment cannot be refunded.", code="not_refundable")
    available = await refundable_amount(session, payment, scope)
    amount = available if amount is None else amount
    if amount <= 0 or amount > available:
        raise ValidationFailed(
            "The refund amount exceeds the refundable amount.",
            code="refund_exceeds_refundable",
            details={"refundable": available},
        )
    refund = Refund(
        payment_id=payment.id,
        merchant_order_id=payment.merchant_order_id,
        merchant_id=payment.merchant_id,
        amount=amount,
        merchant_portion=amount,
        platform_portion=0,
        scope=scope.value,
        currency=payment.currency,
        status=RefundStatus.REQUESTED.value,
        initiated_by=initiated_by.value,
        requested_by_user_id=actor_user_id,
        reason=reason,
        restock=restock and scope != RefundScope.DELIVERY,  # a delivery refund returns no items
    )
    session.add(refund)
    await session.flush()
    return refund


async def process_refund(
    session: AsyncSession,
    refund: Refund,
    provider: PaymentProvider,
    *,
    reviewer_id: uuid.UUID | None,
    update_order_status: bool = True,
) -> Refund:
    if refund.status != RefundStatus.REQUESTED.value:
        raise Conflict("This refund has already been processed.", code="refund_processed")
    payment = await _lock_payment(session, refund.payment_id)
    if payment.status not in REFUNDABLE_PAYMENT_STATUSES:
        raise Conflict("This payment cannot be refunded.", code="not_refundable")
    already = await reversed_totals(session, payment.id)
    portions = split_portions(payment, refund.amount, already, RefundScope(refund.scope))
    _apply(refund, portions)
    refund.reviewed_by_user_id = reviewer_id
    refund.status = RefundStatus.PROCESSING.value
    await session.flush()

    assert payment.provider_payment_id
    try:
        remote = await provider.refund_payment(payment.provider_payment_id, refund.amount)
    except AppError as exc:
        refund.status = RefundStatus.FAILED.value
        refund.failure_reason = exc.message
        await _notify(session, refund, payment)
        await session.flush()
        return refund

    refund.status = RefundStatus.SUCCEEDED.value
    refund.completed_at = utcnow()
    refund.provider_reference = f"{remote.provider_payment_id}:refunded:{remote.refunded_amount}"
    refund.provider_response = remote.raw
    payment.refunded_amount += refund.amount
    await post_reversal(
        session,
        payment,
        source_type="refund",
        source_id=refund.id,
        transaction_type=LedgerTransactionType.REFUND,
        portions=portions,
        description=f"Refund {refund.id}" + (" (delivery charge)" if portions.delivery == refund.amount else ""),
    )
    await _after_refund(session, payment, refund, update_order_status=update_order_status)
    if remote.refunded_amount > payment.refunded_amount:
        await sync_provider_refunds(session, payment, remote.refunded_amount)
    await session.flush()
    return refund


async def _after_refund(
    session: AsyncSession, payment: Payment, refund: Refund, *, update_order_status: bool = True
) -> None:
    payment.status = (
        PaymentStatus.REFUNDED.value
        if payment.refunded_amount >= payment.amount
        else PaymentStatus.PARTIALLY_REFUNDED.value
    )
    mo = await session.get(MerchantOrder, payment.merchant_order_id, with_for_update=True)
    assert mo is not None
    if refund.restock and mo.status not in SHIPPED_OR_LATER:
        await inventory.restock(session, mo)
    if (
        update_order_status
        and payment.status == PaymentStatus.REFUNDED.value
        and mo.status
        not in {
            MerchantOrderStatus.CANCELLED.value,
            MerchantOrderStatus.REJECTED.value,
            MerchantOrderStatus.REFUNDED.value,
            MerchantOrderStatus.PENDING_PAYMENT.value,
        }
    ):
        await orders.set_merchant_order_status(
            session, mo, MerchantOrderStatus.REFUNDED, actor_user_id=refund.reviewed_by_user_id, note="Fully refunded"
        )
    await _notify(session, refund, payment)


async def _notify(session: AsyncSession, refund: Refund, payment: Payment) -> None:
    mo = await session.get(MerchantOrder, payment.merchant_order_id)
    data = {"order_number": mo.number if mo else "", "amount": refund.amount, "status": refund.status}
    await notify(session, payment.customer_user_id, NotificationType.REFUND_STATUS, data)
    merchant = await session.get(Merchant, payment.merchant_id)
    if merchant is not None:
        await notify(session, merchant.owner_user_id, NotificationType.REFUND_STATUS, data)


async def create_and_process(
    session: AsyncSession,
    payment: Payment,
    provider: PaymentProvider,
    *,
    amount: int | None,
    initiated_by: RefundInitiator,
    actor_user_id: uuid.UUID | None,
    reason: str,
    restock: bool,
    update_order_status: bool = True,
    scope: RefundScope = RefundScope.AUTO,
) -> Refund:
    refund = await request_refund(
        session,
        payment,
        amount=amount,
        initiated_by=initiated_by,
        actor_user_id=actor_user_id,
        reason=reason,
        restock=restock,
        scope=scope,
    )
    return await process_refund(
        session, refund, provider, reviewer_id=actor_user_id, update_order_status=update_order_status
    )


async def reject_refund(session: AsyncSession, refund: Refund, *, reviewer_id: uuid.UUID, note: str | None) -> Refund:
    if refund.status != RefundStatus.REQUESTED.value:
        raise Conflict("This refund has already been processed.", code="refund_processed")
    refund.status = RefundStatus.REJECTED.value
    refund.reviewed_by_user_id = reviewer_id
    refund.failure_reason = note
    payment = await session.get(Payment, refund.payment_id)
    assert payment is not None
    await _notify(session, refund, payment)
    await session.flush()
    return refund


async def sync_provider_refunds(session: AsyncSession, payment: Payment, provider_refunded: int) -> None:
    """Record refunds the provider reports that this system did not initiate."""
    delta = min(provider_refunded, payment.amount) - payment.refunded_amount
    if delta <= 0:
        return
    already = await reversed_totals(session, payment.id)
    delta = min(delta, payment.amount - already.amount)
    if delta <= 0:
        return
    portions = split_portions(payment, delta, already)
    refund = Refund(
        payment_id=payment.id,
        merchant_order_id=payment.merchant_order_id,
        merchant_id=payment.merchant_id,
        amount=delta,
        merchant_portion=portions.merchant,
        platform_portion=portions.platform,
        delivery_portion=portions.delivery,
        delivery_platform_portion=portions.delivery_platform,
        scope=RefundScope.AUTO.value,
        currency=payment.currency,
        status=RefundStatus.SUCCEEDED.value,
        initiated_by=RefundInitiator.PLATFORM.value,
        reason="Refund reported by the payment provider.",
        provider_reference=f"{payment.provider_payment_id}:refunded:{provider_refunded}",
        completed_at=utcnow(),
    )
    session.add(refund)
    await session.flush()
    payment.refunded_amount += delta
    await post_reversal(
        session,
        payment,
        source_type="refund",
        source_id=refund.id,
        transaction_type=LedgerTransactionType.REFUND,
        portions=portions,
        description="Provider-reported refund",
    )
    log.info("provider_refund_recorded", payment_id=str(payment.id), amount=delta)
    await _after_refund(session, payment, refund)
