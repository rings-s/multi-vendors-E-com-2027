"""Response builders for orders (customer, merchant and admin views)."""

import uuid

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.auth.models import User
from app.modules.delivery import service as delivery_service
from app.modules.delivery.schemas import DeliveryOut
from app.modules.orders.models import MerchantOrder, Order
from app.modules.orders.schemas import (
    MerchantOrderCustomerView,
    MerchantOrderMerchantView,
    OrderItemOut,
    OrderOut,
    PaymentSummary,
    ShipmentOut,
)
from app.modules.payments.models import Payment
from app.modules.stores.models import Store


def payment_summary(payment: Payment | None) -> PaymentSummary | None:
    if payment is None:
        return None
    return PaymentSummary(
        id=payment.id,
        status=payment.status,
        amount=payment.amount,
        refunded_amount=payment.refunded_amount,
        is_test=payment.is_test,
        provider=payment.provider,
        transaction_url=payment.transaction_url,
        failure_reason=payment.failure_reason,
        created_at=payment.created_at,
    )


async def _payments_by_mo(session: AsyncSession, mo_ids: list[uuid.UUID]) -> dict[uuid.UUID, Payment]:
    if not mo_ids:
        return {}
    rows = await session.exec(
        select(Payment).where(col(Payment.merchant_order_id).in_(mo_ids)).order_by(col(Payment.created_at))
    )
    latest: dict[uuid.UUID, Payment] = {}
    for payment in rows.all():
        current = latest.get(payment.merchant_order_id)
        # Prefer the captured payment, otherwise the most recent attempt.
        if current is None or payment.paid_at is not None or current.paid_at is None:
            latest[payment.merchant_order_id] = payment
    return latest


async def _deliveries(
    session: AsyncSession, mos: list[MerchantOrder], *, merchant_view: bool
) -> dict[uuid.UUID, DeliveryOut]:
    deliveries = await delivery_service.for_merchant_orders(session, [m.id for m in mos])
    timeline = await delivery_service.events(session, [d.id for d in deliveries.values()])
    by_id = {m.id: m for m in mos}
    return {
        mo_id: delivery_service.delivery_out(d, by_id[mo_id], timeline[d.id], merchant_view=merchant_view)
        for mo_id, d in deliveries.items()
    }


async def order_out(session: AsyncSession, order: Order) -> OrderOut:
    mos = order.merchant_orders
    stores = (
        {s.id: s for s in (await session.exec(select(Store).where(col(Store.id).in_([m.store_id for m in mos])))).all()}
        if mos
        else {}
    )
    payments = await _payments_by_mo(session, [m.id for m in mos])
    deliveries = await _deliveries(session, list(mos), merchant_view=False)
    views = []
    for mo in mos:
        store = stores[mo.store_id]
        payment = payments.get(mo.id)
        views.append(
            MerchantOrderCustomerView(
                id=mo.id,
                number=mo.number,
                merchant_id=mo.merchant_id,
                store_id=store.id,
                store_name=store.name,
                store_slug=store.slug,
                status=mo.status,
                fulfillment_type=mo.fulfillment_type,
                items_subtotal=mo.items_subtotal,
                discount_total=mo.discount_total,
                delivery_method=mo.delivery_method,
                delivery_fee=mo.delivery_fee,
                delivery_fee_waived=mo.delivery_fee_waived,
                delivery_vat=mo.delivery_vat,
                vat_rate=mo.vat_rate,
                vat_total=mo.vat_total,
                total=mo.total,
                cancellation_status=mo.cancellation_status,
                reservation_expires_at=mo.reservation_expires_at,
                items=[OrderItemOut.model_validate(i) for i in mo.items],
                shipments=[ShipmentOut.model_validate(s) for s in mo.shipments],
                delivery=deliveries.get(mo.id),
                payment=payment_summary(payment),
                refunded_amount=payment.refunded_amount if payment else 0,
            )
        )
    return OrderOut(
        id=order.id,
        number=order.number,
        status=order.status,
        items_subtotal=order.items_subtotal,
        discount_total=order.discount_total,
        delivery_total=order.delivery_total,
        vat_total=order.vat_total,
        total=order.total,
        contact_name=order.contact_name,
        contact_email=order.contact_email,
        contact_phone=order.contact_phone,
        delivery_address=order.delivery_address,
        created_at=order.created_at,
        merchant_orders=views,
    )


async def merchant_views(session: AsyncSession, mos: list[MerchantOrder]) -> list[MerchantOrderMerchantView]:
    payments = await _payments_by_mo(session, [m.id for m in mos])
    deliveries = await _deliveries(session, mos, merchant_view=True)
    customer_ids = {m.customer_user_id for m in mos}
    names = (
        {u.id: u.full_name for u in (await session.exec(select(User).where(col(User.id).in_(customer_ids)))).all()}
        if customer_ids
        else {}
    )
    out = []
    for mo in mos:
        order = mo.order
        payment = payments.get(mo.id)
        out.append(
            MerchantOrderMerchantView(
                id=mo.id,
                order_id=order.id,
                number=mo.number,
                order_number=order.number,
                status=mo.status,
                fulfillment_type=mo.fulfillment_type,
                customer_name=order.contact_name or names.get(mo.customer_user_id, ""),
                customer_phone=order.contact_phone,
                delivery_address=order.delivery_address,
                items_subtotal=mo.items_subtotal,
                discount_total=mo.discount_total,
                delivery_method=mo.delivery_method,
                delivery_fee=mo.delivery_fee,
                delivery_fee_waived=mo.delivery_fee_waived,
                delivery_vat=mo.delivery_vat,
                delivery_fee_recipient=mo.delivery_fee_recipient,
                delivery_cost_bearer=mo.delivery_cost_bearer,
                vat_total=mo.vat_total,
                total=mo.total,
                commission_total=mo.commission_total,
                delivery_commission=mo.delivery_commission,
                merchant_net=mo.merchant_net,
                merchant_delivery_share=mo.merchant_delivery_share,
                cancellation_status=mo.cancellation_status,
                cancellation_reason=mo.cancellation_reason,
                merchant_note=mo.merchant_note,
                items=[OrderItemOut.model_validate(i) for i in mo.items],
                shipments=[ShipmentOut.model_validate(s) for s in mo.shipments],
                delivery=deliveries.get(mo.id),
                payment=payment_summary(payment),
                refunded_amount=payment.refunded_amount if payment else 0,
                created_at=mo.created_at,
                paid_at=mo.paid_at,
            )
        )
    return out
