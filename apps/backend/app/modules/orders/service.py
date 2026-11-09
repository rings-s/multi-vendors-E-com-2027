"""Checkout, order creation, fulfillment workflows and cancellations."""

import secrets
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.core.money import ONE_HUNDRED
from app.core.security import utcnow
from app.integrations.payments.base import PaymentProvider
from app.modules.admin.settings_service import PaymentSettings, get_setting
from app.modules.auth.models import User
from app.modules.cart import service as cart_service
from app.modules.cart.pricing import MerchantGroup
from app.modules.commissions.models import CommissionTransaction
from app.modules.commissions.service import line_commission
from app.modules.customers.service import get_address
from app.modules.delivery import service as delivery_service
from app.modules.delivery.models import DeliveryMethod, DeliveryStatus
from app.modules.delivery.providers.base import AddressSnapshot
from app.modules.delivery.quoting import DeliveryContext, DeliverySelection
from app.modules.delivery.schemas import DeliveryChoices, DeliveryStatusUpdate
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import notify
from app.modules.orders import inventory
from app.modules.orders.models import (
    CancellationStatus,
    FulfillmentType,
    MerchantOrder,
    MerchantOrderStatus,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    Shipment,
    ShipmentStatus,
)
from app.modules.orders.schemas import CheckoutRequest, FulfillmentUpdate
from app.modules.payments.models import FeeBearer, Payment, PaymentStatus

PAID_LIKE = {
    MerchantOrderStatus.PAID,
    MerchantOrderStatus.ACCEPTED,
    MerchantOrderStatus.PROCESSING,
    MerchantOrderStatus.SHIPPED,
}
FULFILLED = {MerchantOrderStatus.DELIVERED, MerchantOrderStatus.COMPLETED}
CLOSED_UNFULFILLED = {MerchantOrderStatus.CANCELLED, MerchantOrderStatus.REFUNDED, MerchantOrderStatus.REJECTED}

PHYSICAL_FLOW: dict[MerchantOrderStatus, set[MerchantOrderStatus]] = {
    MerchantOrderStatus.PAID: {MerchantOrderStatus.ACCEPTED},
    MerchantOrderStatus.ACCEPTED: {MerchantOrderStatus.PROCESSING, MerchantOrderStatus.SHIPPED},
    MerchantOrderStatus.PROCESSING: {MerchantOrderStatus.SHIPPED},
    MerchantOrderStatus.SHIPPED: {MerchantOrderStatus.DELIVERED},
}
SERVICE_FLOW: dict[MerchantOrderStatus, set[MerchantOrderStatus]] = {
    MerchantOrderStatus.PAID: {MerchantOrderStatus.ACCEPTED},
    MerchantOrderStatus.ACCEPTED: {MerchantOrderStatus.PROCESSING, MerchantOrderStatus.COMPLETED},
    MerchantOrderStatus.PROCESSING: {MerchantOrderStatus.COMPLETED},
}
CANCELLABLE_BY_REQUEST = {MerchantOrderStatus.PAID, MerchantOrderStatus.ACCEPTED, MerchantOrderStatus.PROCESSING}
FULFILLMENT_TO_DELIVERY: dict[MerchantOrderStatus, DeliveryStatus] = {
    MerchantOrderStatus.ACCEPTED: DeliveryStatus.CONFIRMED,
    MerchantOrderStatus.PROCESSING: DeliveryStatus.PREPARING,
    MerchantOrderStatus.SHIPPED: DeliveryStatus.OUT_FOR_DELIVERY,
    MerchantOrderStatus.DELIVERED: DeliveryStatus.DELIVERED,
}


def _number() -> str:
    return f"ORD-{utcnow():%y%m%d}-{secrets.token_hex(3).upper()}"


async def record_history(
    session: AsyncSession,
    mo: MerchantOrder | None,
    order_id: uuid.UUID,
    from_status: str | None,
    to_status: str,
    actor_user_id: uuid.UUID | None,
    note: str | None = None,
) -> None:
    session.add(
        OrderStatusHistory(
            order_id=order_id,
            merchant_order_id=mo.id if mo else None,
            from_status=from_status,
            to_status=to_status,
            actor_user_id=actor_user_id,
            note=note,
        )
    )


async def set_merchant_order_status(
    session: AsyncSession,
    mo: MerchantOrder,
    to_status: MerchantOrderStatus,
    *,
    actor_user_id: uuid.UUID | None,
    note: str | None = None,
    notify_customer: bool = True,
) -> None:
    from_status = mo.status
    if from_status == to_status.value:
        return
    mo.status = to_status.value
    now = utcnow()
    if to_status == MerchantOrderStatus.ACCEPTED:
        mo.accepted_at = now
    elif to_status in FULFILLED:
        mo.fulfilled_at = now
    elif to_status in CLOSED_UNFULFILLED and mo.cancelled_at is None:
        mo.cancelled_at = now
    if to_status in CLOSED_UNFULFILLED:
        from app.modules.delivery import service as delivery_service

        await delivery_service.cancel_for_order(session, mo, actor_user_id=actor_user_id, note=note)
    await record_history(session, mo, mo.order_id, from_status, to_status.value, actor_user_id, note)
    if notify_customer:
        await notify(
            session,
            mo.customer_user_id,
            NotificationType.ORDER_STATUS_CHANGED,
            {"order_number": mo.number, "status": to_status.value, "merchant_order_id": str(mo.id)},
        )
    await refresh_order_status(session, mo.order_id)


async def refresh_order_status(session: AsyncSession, order_id: uuid.UUID) -> None:
    order = await session.get(Order, order_id)
    if order is None:
        return
    await session.refresh(order, ["merchant_orders"])
    statuses = {MerchantOrderStatus(mo.status) for mo in order.merchant_orders}
    if statuses == {MerchantOrderStatus.PENDING_PAYMENT}:
        new = OrderStatus.PENDING_PAYMENT
    elif statuses <= {MerchantOrderStatus.CANCELLED}:
        new = OrderStatus.CANCELLED
    elif MerchantOrderStatus.PENDING_PAYMENT in statuses:
        new = OrderStatus.PARTIALLY_PAID
    elif statuses <= FULFILLED:
        new = OrderStatus.COMPLETED
    elif statuses & PAID_LIKE:
        new = OrderStatus.PAID
    else:
        new = OrderStatus.CLOSED
    if order.status != new.value:
        await record_history(session, None, order.id, order.status, new.value, None)
        order.status = new.value


# -- checkout ------------------------------------------------------------------------


async def create_payment_record(
    session: AsyncSession, mo: MerchantOrder, provider: PaymentProvider, fee_bearer: FeeBearer
) -> Payment:
    from app.modules.merchants.models import Merchant
    from app.modules.merchants.service import get_payment_account, merchant_can_accept_payments
    from app.modules.payments.allocation import build_allocations
    from app.modules.payments.models import PaymentAllocation

    merchant = await session.get(Merchant, mo.merchant_id)
    assert merchant is not None
    account = await get_payment_account(session, mo.merchant_id, provider.name)
    allocations = build_allocations(
        total=mo.total,
        commission=mo.commission_total,
        delivery_platform=mo.platform_delivery_share,
        delivery_merchant=mo.merchant_delivery_share,
        merchant_id=mo.merchant_id,
        merchant_recipient_id=account.recipient_id if account else None,
        platform_recipient_id=provider.platform_recipient_id,
        merchant_can_accept_payments=await merchant_can_accept_payments(session, merchant, provider.name),
        fee_bearer=fee_bearer,
    )
    payment = Payment(
        order_id=mo.order_id,
        merchant_order_id=mo.id,
        merchant_id=mo.merchant_id,
        customer_user_id=mo.customer_user_id,
        provider=provider.name,
        is_test=provider.is_test,
        status=PaymentStatus.CREATED.value,
        amount=mo.total,
        currency=mo.currency,
        refunded_amount=0,
        fee_bearer=fee_bearer.value,
    )
    session.add(payment)
    await session.flush()
    for spec in allocations:
        session.add(
            PaymentAllocation(
                payment_id=payment.id,
                recipient_type=spec.recipient_type.value,
                merchant_id=spec.merchant_id,
                recipient_id=spec.recipient_id,
                amount=spec.amount,
                delivery_amount=spec.delivery_amount,
                is_fee_source=spec.is_fee_source,
                refundable=spec.refundable,
            )
        )
    await session.flush()
    await session.refresh(payment, ["allocations"])
    return payment


async def _create_merchant_order(
    session: AsyncSession,
    order: Order,
    group: MerchantGroup,
    index: int,
    *,
    customer_id: uuid.UUID,
    reservation_expires_at: datetime,
    fee_bearer: FeeBearer,
) -> MerchantOrder:
    now = utcnow()
    charge = group.charge
    mo = MerchantOrder(
        order_id=order.id,
        merchant_id=group.merchant.id,
        store_id=group.store.id,
        customer_user_id=customer_id,
        number=f"{order.number}-{index}",
        status=MerchantOrderStatus.PENDING_PAYMENT.value,
        fulfillment_type=group.fulfillment_type.value,
        currency="SAR",
        items_subtotal=group.items_subtotal,
        discount_total=group.discount_total,
        delivery_method=group.delivery.method.value,
        delivery_fee=charge.fee,
        delivery_fee_waived=charge.fee_waived,
        delivery_vat=charge.vat,
        delivery_fee_recipient=charge.fee_recipient.value if charge.fee_recipient else None,
        delivery_cost_bearer=charge.cost_bearer.value if charge.cost_bearer else None,
        delivery_commission=charge.commission,
        delivery_commission_rate=charge.commission_rate,
        vat_rate=group.vat_rate,
        vat_total=group.vat_total,
        total=group.total,
        commission_total=0,
        merchant_net=group.total - charge.platform_share,
        reservation_expires_at=reservation_expires_at,
        items=[],
        shipments=[],
    )
    session.add(mo)
    await session.flush()
    commission_total = 0
    for line in group.lines:
        commission = await line_commission(
            session,
            merchant_id=group.merchant.id,
            category_id=line.category_id,
            line_total=line.line_total,
            quantity=line.quantity,
            at=now,
        )
        commission_total += commission.amount
        mo.items.append(
            OrderItem(
                merchant_order_id=mo.id,
                item_type=line.item_type.value,
                product_id=line.input.product_id,
                variant_id=line.input.variant_id,
                service_id=line.input.service_id,
                category_id=line.category_id,
                title=line.title,
                sku=line.sku,
                requires_shipping=line.requires_shipping,
                unit_price=line.unit_price,
                unit_discount=line.unit_discount,
                quantity=line.quantity,
                line_subtotal=line.line_subtotal,
                line_discount=line.line_discount,
                line_total=line.line_total,
                commission_rule_id=commission.rule_id,
                commission_rate_type=commission.rate_type.value,
                commission_rate=commission.rate,
                commission_fixed=commission.fixed,
                commission_amount=commission.amount,
            )
        )
    mo.commission_total = commission_total
    mo.merchant_net = mo.total - commission_total - charge.platform_share
    base = group.items_net
    session.add(
        CommissionTransaction(
            order_id=order.id,
            merchant_order_id=mo.id,
            merchant_id=group.merchant.id,
            gross_amount=mo.total,
            commission_base=base,
            commission_rate=(Decimal(commission_total) * ONE_HUNDRED / Decimal(base)).quantize(Decimal("0.0001"))
            if base
            else Decimal("0"),
            commission_amount=commission_total,
            delivery_fee=charge.fee,
            delivery_commission_rate=charge.commission_rate,
            delivery_commission_amount=charge.commission,
            platform_delivery_amount=charge.platform_share - charge.commission,
            processing_fee=None,
            fee_bearer=fee_bearer.value,
            seller_net_amount=mo.merchant_net,
        )
    )
    await session.flush()
    await inventory.reserve(session, mo)
    await record_history(session, mo, order.id, None, mo.status, customer_id)
    return mo


def delivery_context(data: DeliveryChoices, address: AddressSnapshot | None, *, strict: bool) -> DeliveryContext:
    return DeliveryContext(
        address=address,
        selections={
            d.store_id: DeliverySelection(method=DeliveryMethod(d.method), pickup_location_id=d.pickup_location_id)
            for d in data.deliveries
        },
        strict=strict,
    )


async def checkout(
    session: AsyncSession,
    user: User,
    data: CheckoutRequest,
    provider: PaymentProvider,
    idempotency_key: str,
) -> Order:
    existing = (
        await session.exec(
            select(Order).where(Order.customer_user_id == user.id, Order.idempotency_key == idempotency_key)
        )
    ).first()
    if existing is not None:
        return existing
    if not data.accept_terms:
        raise ValidationFailed("You must accept the terms and conditions.", code="terms_not_accepted")

    cart = await cart_service.get_cart(session, user.id, lock=True)
    address = await get_address(session, user.id, data.address_id) if data.address_id else None
    snapshot = cart_service.address_snapshot(address) if address else None
    context = delivery_context(data, snapshot, strict=True)
    quote = await cart_service.quote_cart(session, cart, provider.name, lock_inventory=True, delivery=context)
    if not quote.groups:
        raise ValidationFailed("Your cart is empty.", code="cart_empty")
    if quote.needs_address and snapshot is None:
        raise ValidationFailed("A delivery address is required.", code="address_required")
    if not quote.can_checkout:
        issues = [
            {
                "store": g.store.slug,
                "issues": g.issues,
                "lines": [{"title": line.title, "issues": line.issues} for line in g.lines if line.issues],
            }
            for g in quote.groups
            if not g.can_checkout
        ]
        raise ValidationFailed("Some items cannot be purchased.", code="cart_not_purchasable", details=issues)

    delivery_address = snapshot.as_dict() if quote.needs_address and snapshot else None
    instructions = (data.delivery_instructions or (address.delivery_instructions if address else "")).strip()

    payment_settings = await get_setting(session, "payments", PaymentSettings)
    fee_bearer = FeeBearer(payment_settings.fee_bearer)
    order = Order(
        number=_number(),
        customer_user_id=user.id,
        idempotency_key=idempotency_key,
        status=OrderStatus.PENDING_PAYMENT.value,
        currency="SAR",
        items_subtotal=quote.items_subtotal,
        discount_total=quote.discount_total,
        delivery_total=quote.delivery_total,
        vat_total=quote.vat_total,
        total=quote.total,
        contact_name=data.contact_name or user.full_name,
        contact_email=str(data.contact_email or user.email),
        contact_phone=data.contact_phone,
        delivery_address=delivery_address,
        terms_accepted_at=utcnow(),
        merchant_orders=[],
    )
    session.add(order)
    await session.flush()
    expires = utcnow() + timedelta(minutes=get_settings().inventory_reservation_minutes)
    for index, group in enumerate(quote.groups, start=1):
        mo = await _create_merchant_order(
            session, order, group, index, customer_id=user.id, reservation_expires_at=expires, fee_bearer=fee_bearer
        )
        await delivery_service.create_for_merchant_order(
            session, mo, group.delivery, address=snapshot, instructions=instructions, actor_user_id=user.id
        )
        await create_payment_record(session, mo, provider, fee_bearer)
    await record_history(session, None, order.id, None, order.status, user.id)
    await cart_service.clear(session, cart)
    await session.flush()
    await session.refresh(order, ["merchant_orders"])
    return order


# -- queries ---------------------------------------------------------------------------


async def get_customer_order(session: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    # Flush pending changes first (autoflush is off), then reload so relationships are current.
    await session.flush()
    order = await session.get(Order, order_id, populate_existing=True)
    if order is None or order.customer_user_id != user_id:
        raise NotFound("Order not found.")
    return order


async def get_customer_merchant_order(session: AsyncSession, user_id: uuid.UUID, mo_id: uuid.UUID) -> MerchantOrder:
    mo = await session.get(MerchantOrder, mo_id, with_for_update=True)
    if mo is None or mo.customer_user_id != user_id:
        raise NotFound("Order not found.")
    return mo


async def get_merchant_order_for_merchant(
    session: AsyncSession, merchant_id: uuid.UUID, mo_id: uuid.UUID, *, lock: bool = False
) -> MerchantOrder:
    mo = await session.get(MerchantOrder, mo_id, with_for_update=lock)
    if mo is None or mo.merchant_id != merchant_id:
        raise NotFound("Order not found.")  # tenant isolation
    return mo


async def latest_payment(session: AsyncSession, mo_id: uuid.UUID, *, lock: bool = False) -> Payment | None:
    stmt = (
        select(Payment).where(col(Payment.merchant_order_id) == mo_id).order_by(col(Payment.created_at).desc()).limit(1)
    )
    if lock:
        stmt = stmt.with_for_update()
    return (await session.exec(stmt)).first()


async def captured_payment(session: AsyncSession, mo_id: uuid.UUID, *, lock: bool = False) -> Payment | None:
    from app.modules.payments.models import CAPTURED_STATUSES

    stmt = select(Payment).where(
        col(Payment.merchant_order_id) == mo_id, col(Payment.status).in_([s.value for s in CAPTURED_STATUSES])
    )
    if lock:
        stmt = stmt.with_for_update()
    return (await session.exec(stmt)).first()


async def count_orders_today(session: AsyncSession, merchant_id: uuid.UUID) -> int:
    start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        (
            await session.exec(
                select(func.count(col(MerchantOrder.id))).where(
                    MerchantOrder.merchant_id == merchant_id,
                    col(MerchantOrder.paid_at) >= start,
                )
            )
        ).first()
        or 0
    )


# -- fulfillment (merchant) -----------------------------------------------------------


async def update_fulfillment(
    session: AsyncSession, mo: MerchantOrder, data: FulfillmentUpdate, *, actor_user_id: uuid.UUID
) -> MerchantOrder:
    current = MerchantOrderStatus(mo.status)
    target = MerchantOrderStatus(data.status)
    delivery = await delivery_service.for_merchant_order(session, mo.id, lock=True)
    if delivery is not None:
        # Physical orders are fulfilled through their delivery; map the order status.
        status = FULFILLMENT_TO_DELIVERY.get(target)
        if status == DeliveryStatus.OUT_FOR_DELIVERY and delivery.method == DeliveryMethod.PICKUP.value:
            status = DeliveryStatus.READY_FOR_PICKUP
        if status is None:
            raise Conflict(f"Cannot move this order from {current} to {target}.", code="invalid_transition")
        await delivery_service.transition(
            session,
            delivery,
            mo,
            DeliveryStatusUpdate(
                status=status.value,  # type: ignore[arg-type]
                note=data.note,
                carrier=data.carrier,
                tracking_number=data.tracking_number,
                tracking_url=data.tracking_url,
            ),
            actor_user_id=actor_user_id,
        )
        return mo
    flow = PHYSICAL_FLOW if mo.fulfillment_type == FulfillmentType.PHYSICAL.value else SERVICE_FLOW
    if target not in flow.get(current, set()):
        raise Conflict(f"Cannot move this order from {current} to {target}.", code="invalid_transition")
    if mo.cancellation_status == CancellationStatus.REQUESTED.value and target != MerchantOrderStatus.ACCEPTED:
        raise Conflict("Resolve the customer's cancellation request first.", code="cancellation_pending")
    now = utcnow()
    if target == MerchantOrderStatus.SHIPPED:
        mo.shipments.append(
            Shipment(
                merchant_order_id=mo.id,
                carrier=data.carrier or "",
                tracking_number=data.tracking_number,
                tracking_url=data.tracking_url,
                status=ShipmentStatus.SHIPPED.value,
                shipped_at=now,
            )
        )
    if target == MerchantOrderStatus.DELIVERED:
        for shipment in mo.shipments:
            if shipment.status != ShipmentStatus.DELIVERED.value:
                shipment.status = ShipmentStatus.DELIVERED.value
                shipment.delivered_at = now
    if data.note:
        mo.merchant_note = data.note
    await set_merchant_order_status(session, mo, target, actor_user_id=actor_user_id, note=data.note)
    await session.flush()
    return mo


# -- cancellations ---------------------------------------------------------------------


async def cancel_unpaid(
    session: AsyncSession, mo: MerchantOrder, *, actor_user_id: uuid.UUID | None, reason: str
) -> None:
    """Cancel a merchant order that has not been paid: release stock and void pending payments."""
    if mo.status != MerchantOrderStatus.PENDING_PAYMENT.value:
        raise Conflict("Only unpaid orders can be cancelled directly.", code="invalid_transition")
    payments = (await session.exec(select(Payment).where(Payment.merchant_order_id == mo.id).with_for_update())).all()
    for payment in payments:
        if payment.status == PaymentStatus.CREATED.value:
            payment.status = PaymentStatus.CANCELLED.value
        # PENDING/AUTHORIZED payments stay as reported by the provider; if one is captured
        # later it is refunded automatically (late payment for a cancelled order).
    await inventory.release(session, mo)
    mo.cancellation_reason = reason
    await set_merchant_order_status(
        session, mo, MerchantOrderStatus.CANCELLED, actor_user_id=actor_user_id, note=reason
    )


async def customer_request_cancellation(
    session: AsyncSession, mo: MerchantOrder, *, user_id: uuid.UUID, reason: str
) -> MerchantOrder:
    status = MerchantOrderStatus(mo.status)
    if status == MerchantOrderStatus.PENDING_PAYMENT:
        await cancel_unpaid(session, mo, actor_user_id=user_id, reason=reason)
        return mo
    if status not in CANCELLABLE_BY_REQUEST:
        raise Conflict("This order can no longer be cancelled.", code="not_cancellable")
    if mo.cancellation_status == CancellationStatus.REQUESTED.value:
        raise Conflict("A cancellation request is already pending.", code="cancellation_pending")
    mo.cancellation_status = CancellationStatus.REQUESTED.value
    mo.cancellation_reason = reason
    mo.cancellation_requested_at = utcnow()
    await record_history(session, mo, mo.order_id, mo.status, mo.status, user_id, f"Cancellation requested: {reason}")
    from app.modules.merchants.models import Merchant

    merchant = await session.get(Merchant, mo.merchant_id)
    if merchant is not None:
        await notify(
            session,
            merchant.owner_user_id,
            NotificationType.ORDER_STATUS_CHANGED,
            {"order_number": mo.number, "status": "CANCELLATION_REQUESTED", "merchant_order_id": str(mo.id)},
        )
    await session.flush()
    return mo


async def cancel_paid_order(
    session: AsyncSession,
    mo: MerchantOrder,
    provider: PaymentProvider,
    *,
    actor_user_id: uuid.UUID,
    initiated_by: str,
    reason: str,
    final_status: MerchantOrderStatus = MerchantOrderStatus.CANCELLED,
) -> MerchantOrder:
    """Cancel/reject a paid merchant order with a full refund of the remaining amount."""
    from app.modules.payments import refunds
    from app.modules.payments.models import RefundInitiator, RefundStatus

    if MerchantOrderStatus(mo.status) not in CANCELLABLE_BY_REQUEST:
        # After dispatch an order can still be cancelled (with a refund) if delivery failed.
        delivery = await delivery_service.for_merchant_order(session, mo.id)
        if delivery is None or delivery.status != DeliveryStatus.FAILED.value or mo.status not in PAID_LIKE:
            raise Conflict("This order can no longer be cancelled.", code="not_cancellable")
    payment = await captured_payment(session, mo.id, lock=True)
    if payment is None:
        raise Conflict("No captured payment found for this order.", code="no_payment")
    refund = None
    if payment.refundable_amount > 0:
        refund = await refunds.create_and_process(
            session,
            payment,
            provider,
            amount=None,
            initiated_by=RefundInitiator(initiated_by),
            actor_user_id=actor_user_id,
            reason=reason,
            restock=True,
            update_order_status=False,
        )
    if refund is None or refund.status == RefundStatus.SUCCEEDED.value:
        if mo.cancellation_status == CancellationStatus.REQUESTED.value:
            mo.cancellation_status = CancellationStatus.APPROVED.value
        await set_merchant_order_status(session, mo, final_status, actor_user_id=actor_user_id, note=reason)
    await session.flush()
    return mo


async def decide_cancellation(
    session: AsyncSession,
    mo: MerchantOrder,
    provider: PaymentProvider,
    *,
    approve: bool,
    actor_user_id: uuid.UUID,
    initiated_by: str,
    note: str | None,
) -> MerchantOrder:
    if mo.cancellation_status != CancellationStatus.REQUESTED.value:
        raise Conflict("There is no pending cancellation request.", code="no_cancellation_request")
    if not approve:
        mo.cancellation_status = CancellationStatus.REJECTED.value
        await record_history(
            session, mo, mo.order_id, mo.status, mo.status, actor_user_id, f"Cancellation rejected: {note or ''}"
        )
        await notify(
            session,
            mo.customer_user_id,
            NotificationType.ORDER_STATUS_CHANGED,
            {"order_number": mo.number, "status": "CANCELLATION_REJECTED", "merchant_order_id": str(mo.id)},
        )
        await session.flush()
        return mo
    return await cancel_paid_order(
        session,
        mo,
        provider,
        actor_user_id=actor_user_id,
        initiated_by=initiated_by,
        reason=mo.cancellation_reason or note or "Cancellation approved",
    )


def ensure_owner(mo: MerchantOrder, merchant_id: uuid.UUID) -> None:
    if mo.merchant_id != merchant_id:
        raise PermissionDenied("You do not have access to this order.")
