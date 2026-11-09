"""Payment lifecycle.

Only verified provider data (a server-to-server API response or an authenticated
webhook followed by a provider lookup) can move a payment to PAID. Browser
redirects are never trusted: the redirect handler only triggers a provider lookup.

``apply_provider_state`` is the single place where provider state is applied. It is
idempotent and tolerant of out-of-order delivery because it always applies the
provider's *current* state and only moves forward through the lifecycle.
"""

import uuid
from typing import Any

import structlog
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, Conflict, NotFound, ProviderCapabilityUnavailable, ValidationFailed
from app.core.security import utcnow
from app.integrations.payments.base import PaymentProvider, ProviderPayment, SplitPaymentRequest
from app.modules.commissions.models import CommissionTransaction
from app.modules.ledger import service as ledger
from app.modules.ledger.models import AccountType, Direction, LedgerComponent, LedgerTransactionType
from app.modules.merchants.models import Merchant
from app.modules.merchants.service import merchant_can_accept_payments
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import notify
from app.modules.orders import inventory
from app.modules.orders import service as orders
from app.modules.orders.models import MerchantOrder, MerchantOrderStatus, Order
from app.modules.payments.allocation import AllocationSpec, to_split_instructions, validate_allocations
from app.modules.payments.models import (
    CAPTURED_STATUSES,
    FeeBearer,
    Payment,
    PaymentAllocation,
    PaymentStatus,
    RecipientType,
    RefundInitiator,
)
from app.modules.stores.models import Store

log = structlog.get_logger(__name__)

OPEN_STATUSES = {PaymentStatus.CREATED, PaymentStatus.PENDING, PaymentStatus.AUTHORIZED}
CAPTURED = set(CAPTURED_STATUSES)


class PaymentMismatch(AppError):
    code = "payment_mismatch"


async def get_payment_for_customer(
    session: AsyncSession, user_id: uuid.UUID, payment_id: uuid.UUID, *, lock: bool = False
) -> Payment:
    payment = await session.get(Payment, payment_id, with_for_update=lock)
    if payment is None or payment.customer_user_id != user_id:
        raise NotFound("Payment not found.")
    return payment


def _allocation(payment: Payment, recipient: RecipientType) -> PaymentAllocation:
    for allocation in payment.allocations:
        if allocation.recipient_type == recipient.value:
            return allocation
    raise PaymentMismatch(f"Payment {payment.id} has no {recipient.value} allocation.")


def _allocation_specs(payment: Payment) -> list[AllocationSpec]:
    return [
        AllocationSpec(
            recipient_type=RecipientType(a.recipient_type),
            recipient_id=a.recipient_id,
            amount=a.amount,
            merchant_id=a.merchant_id,
            is_fee_source=a.is_fee_source,
            refundable=a.refundable,
            delivery_amount=a.delivery_amount,
        )
        for a in payment.allocations
    ]


async def start_payment(
    session: AsyncSession,
    payment: Payment,
    provider: PaymentProvider,
    *,
    source: dict[str, Any],
) -> Payment:
    """Submit the payment to the provider (one merchant per provider payment)."""
    if payment.provider != provider.name:
        raise Conflict("This payment belongs to a different provider.", code="provider_mismatch")
    if PaymentStatus(payment.status) != PaymentStatus.CREATED:
        raise Conflict("This payment has already been submitted.", code="payment_already_started")
    mo = await session.get(MerchantOrder, payment.merchant_order_id, with_for_update=True)
    assert mo is not None
    if mo.status != MerchantOrderStatus.PENDING_PAYMENT.value:
        raise Conflict("This order is not awaiting payment.", code="order_not_payable")
    if mo.reservation_expires_at is not None and mo.reservation_expires_at < utcnow():
        raise Conflict("The checkout session has expired.", code="checkout_expired")
    merchant = await session.get(Merchant, payment.merchant_id)
    assert merchant is not None
    if not await merchant_can_accept_payments(session, merchant, provider.name):
        raise ValidationFailed(
            "This merchant cannot accept payments right now.", code="merchant_cannot_accept_payments"
        )
    if provider.capabilities.max_merchants_per_payment < 1 or not provider.capabilities.supports_splits:
        raise ProviderCapabilityUnavailable("Split payments are not available with the configured provider.")

    validate_allocations(payment.amount, _allocation_specs(payment))
    splits = to_split_instructions(_allocation_specs(payment), reference=mo.number)
    order = await session.get(Order, payment.order_id)
    assert order is not None
    callback = f"{get_settings().frontend_url}/checkout/result?payment_id={payment.id}"
    request = SplitPaymentRequest(
        payment_id=str(payment.id),
        amount=payment.amount,
        currency=payment.currency,
        description=f"Order {mo.number}",
        callback_url=callback,
        source=source,
        metadata={"payment_id": str(payment.id), "merchant_order": mo.number, "order": order.number},
        splits=splits,
    )
    payment.status = PaymentStatus.PENDING.value
    await session.flush()
    try:
        remote = await provider.create_split_payment(request)
    except ProviderCapabilityUnavailable:
        raise
    except ValidationFailed:
        raise
    except AppError as exc:
        # The provider rejected the request; record the failure so the customer can retry.
        payment.status = PaymentStatus.FAILED.value
        payment.failure_reason = exc.message
        await notify(session, payment.customer_user_id, NotificationType.PAYMENT_FAILED, {"order_number": mo.number})
        await session.flush()
        return payment
    await apply_provider_state(session, payment, remote, provider)
    return payment


async def sync_payment(session: AsyncSession, payment: Payment, provider: PaymentProvider) -> Payment:
    """Fetch the authoritative state from the provider and apply it."""
    if not payment.provider_payment_id:
        return payment
    remote = await provider.retrieve_payment(payment.provider_payment_id)
    await apply_provider_state(session, payment, remote, provider)
    return payment


async def retry_payment(session: AsyncSession, mo: MerchantOrder, provider: PaymentProvider) -> Payment:
    """Create a fresh payment attempt for an unpaid merchant order after a failure."""
    if mo.status != MerchantOrderStatus.PENDING_PAYMENT.value:
        raise Conflict("This order is not awaiting payment.", code="order_not_payable")
    if mo.reservation_expires_at is not None and mo.reservation_expires_at < utcnow():
        raise Conflict("The checkout session has expired.", code="checkout_expired")
    latest = await orders.latest_payment(session, mo.id, lock=True)
    if latest is not None and PaymentStatus(latest.status) not in {PaymentStatus.FAILED, PaymentStatus.CANCELLED}:
        if PaymentStatus(latest.status) == PaymentStatus.CREATED:
            return latest
        raise Conflict("A payment for this order is already in progress.", code="payment_in_progress")
    fee_bearer = FeeBearer(latest.fee_bearer) if latest else FeeBearer.PLATFORM
    return await orders.create_payment_record(session, mo, provider, fee_bearer)


async def apply_provider_state(
    session: AsyncSession, payment: Payment, remote: ProviderPayment, provider: PaymentProvider
) -> None:
    """Apply verified provider state to a (locked) payment. Idempotent and monotonic."""
    if remote.currency != payment.currency:
        raise PaymentMismatch("Provider currency does not match; currency is never converted.")
    if remote.amount != payment.amount:
        raise PaymentMismatch(
            f"Provider amount {remote.amount} does not match expected {payment.amount}.",
        )
    if remote.is_live == payment.is_test:
        raise PaymentMismatch("Provider live/test mode does not match the payment record.")

    payment.provider_payment_id = payment.provider_payment_id or remote.provider_payment_id
    payment.provider_response = remote.raw
    payment.transaction_url = remote.transaction_url
    payment.payment_method = remote.payment_method or payment.payment_method
    payment.last_synced_at = utcnow()
    current = PaymentStatus(payment.status)
    target = remote.status

    if current == PaymentStatus.DISPUTED:
        return  # disputes are resolved through the chargeback workflow

    if target in {PaymentStatus.PAID, PaymentStatus.PARTIALLY_REFUNDED, PaymentStatus.REFUNDED}:
        if current not in CAPTURED:
            await _on_captured(session, payment, remote, provider)
        if remote.fee is not None and payment.fee is None:
            await _record_fee(session, payment, remote.fee)
        if remote.refunded_amount > payment.refunded_amount:
            from app.modules.payments import refunds

            await refunds.sync_provider_refunds(session, payment, remote.refunded_amount)
        return

    if target == PaymentStatus.CANCELLED and current in CAPTURED:
        # A void after capture reverses the payment entirely (splits are reversed).
        from app.modules.payments import refunds

        await refunds.sync_provider_refunds(session, payment, payment.amount)
        return

    if current not in OPEN_STATUSES:
        log.info("payment_state_ignored", payment_id=str(payment.id), current=current, target=target)
        return

    if target == PaymentStatus.FAILED:
        await _on_failed(session, payment, remote.failure_reason or "Payment failed")
    elif target == PaymentStatus.CANCELLED:
        payment.status = PaymentStatus.CANCELLED.value
    elif target == PaymentStatus.AUTHORIZED and current in {PaymentStatus.CREATED, PaymentStatus.PENDING}:
        payment.status = PaymentStatus.AUTHORIZED.value
    elif target == PaymentStatus.PENDING and current == PaymentStatus.CREATED:
        payment.status = PaymentStatus.PENDING.value
    await session.flush()


async def _on_failed(session: AsyncSession, payment: Payment, reason: str) -> None:
    payment.status = PaymentStatus.FAILED.value
    payment.failure_reason = reason
    mo = await session.get(MerchantOrder, payment.merchant_order_id)
    assert mo is not None
    await notify(session, payment.customer_user_id, NotificationType.PAYMENT_FAILED, {"order_number": mo.number})


async def _on_captured(
    session: AsyncSession, payment: Payment, remote: ProviderPayment, provider: PaymentProvider
) -> None:
    payment.status = PaymentStatus.PAID.value
    payment.paid_at = utcnow()
    payment.failure_reason = None
    await session.flush()  # the partial unique index guarantees one captured payment per order

    merchant_alloc = _allocation(payment, RecipientType.MERCHANT)
    platform_alloc = _allocation(payment, RecipientType.PLATFORM)
    if merchant_alloc.amount + platform_alloc.amount != payment.amount:
        raise PaymentMismatch("Allocations do not sum to the payment amount.")
    mo = await session.get(MerchantOrder, payment.merchant_order_id, with_for_update=True)
    assert mo is not None
    await ledger.post(
        session,
        transaction_type=LedgerTransactionType.PAYMENT_CAPTURED,
        source_type="payment",
        source_id=payment.id,
        merchant_id=payment.merchant_id,
        description=f"Payment captured for merchant order {payment.merchant_order_id}",
        is_test=payment.is_test,
        lines=[
            ledger.Line(AccountType.PROVIDER_CLEARING, Direction.DEBIT, payment.amount),
            ledger.Line(
                AccountType.MERCHANT_PAYABLE,
                Direction.CREDIT,
                merchant_alloc.amount - merchant_alloc.delivery_amount,
                payment.merchant_id,
                "Items",
                LedgerComponent.GOODS,
            ),
            ledger.Line(
                AccountType.MERCHANT_PAYABLE,
                Direction.CREDIT,
                merchant_alloc.delivery_amount,
                payment.merchant_id,
                "Delivery fee",
                LedgerComponent.DELIVERY,
            ),
            ledger.Line(
                AccountType.PLATFORM_COMMISSION,
                Direction.CREDIT,
                platform_alloc.amount - platform_alloc.delivery_amount,
                None,
                "Item commission",
                LedgerComponent.GOODS,
            ),
            ledger.Line(
                ledger.delivery_platform_account(mo.delivery_fee_recipient),
                Direction.CREDIT,
                platform_alloc.delivery_amount,
                None,
                "Delivery commission" if mo.delivery_fee_recipient != "PLATFORM" else "Delivery fee",
                LedgerComponent.DELIVERY,
            ),
        ],
    )

    late = mo.status != MerchantOrderStatus.PENDING_PAYMENT.value or not await inventory.commit(session, mo)
    if late:
        # Payment captured for an order that was cancelled/expired: refund it in full.
        log.warning("late_payment_refund", payment_id=str(payment.id), merchant_order=mo.number)
        from app.modules.payments import refunds

        if remote.fee is not None and payment.fee is None:
            await _record_fee(session, payment, remote.fee)
        await refunds.create_and_process(
            session,
            payment,
            provider,
            amount=None,
            initiated_by=RefundInitiator.PLATFORM,
            actor_user_id=None,
            reason="Payment received after the order was cancelled or expired.",
            restock=False,
            update_order_status=False,
        )
        if mo.status == MerchantOrderStatus.PENDING_PAYMENT.value:
            await orders.set_merchant_order_status(
                session, mo, MerchantOrderStatus.CANCELLED, actor_user_id=None, note="Checkout expired"
            )
        return

    mo.paid_at = utcnow()
    await orders.set_merchant_order_status(
        session, mo, MerchantOrderStatus.PAID, actor_user_id=None, note="Payment verified", notify_customer=False
    )
    store = await session.get(Store, mo.store_id)
    if store is not None:
        store.orders_count += 1
    await notify(
        session,
        payment.customer_user_id,
        NotificationType.PAYMENT_SUCCEEDED,
        {"order_number": mo.number, "amount": payment.amount, "is_test": payment.is_test},
    )
    merchant = await session.get(Merchant, mo.merchant_id)
    if merchant is not None:
        await notify(
            session,
            merchant.owner_user_id,
            NotificationType.NEW_ORDER,
            {"order_number": mo.number, "amount": mo.total, "merchant_order_id": str(mo.id)},
        )


async def _record_fee(session: AsyncSession, payment: Payment, fee: int) -> None:
    """Record the provider-reported processing fee against its explicit bearer."""
    if fee <= 0:
        payment.fee = max(fee, 0)
        return
    payment.fee = fee
    bearer = FeeBearer(payment.fee_bearer)
    debit = (
        ledger.Line(AccountType.MERCHANT_PAYABLE, Direction.DEBIT, fee, payment.merchant_id, "Processing fee")
        if bearer == FeeBearer.MERCHANT
        else ledger.Line(AccountType.PROCESSING_FEES, Direction.DEBIT, fee, None, "Processing fee")
    )
    await ledger.post(
        session,
        transaction_type=LedgerTransactionType.PROCESSING_FEE,
        source_type="payment",
        source_id=payment.id,
        merchant_id=payment.merchant_id,
        description=f"Processing fee borne by {bearer.value.lower()}",
        is_test=payment.is_test,
        lines=[debit, ledger.Line(AccountType.PROVIDER_CLEARING, Direction.CREDIT, fee)],
    )
    commission = (
        await session.exec(
            select(CommissionTransaction).where(CommissionTransaction.merchant_order_id == payment.merchant_order_id)
        )
    ).first()
    if commission is not None:
        commission.processing_fee = fee
        if bearer == FeeBearer.MERCHANT:
            commission.seller_net_amount = (
                commission.gross_amount
                - commission.commission_amount
                - commission.delivery_commission_amount
                - commission.platform_delivery_amount
                - fee
            )
    await session.flush()
