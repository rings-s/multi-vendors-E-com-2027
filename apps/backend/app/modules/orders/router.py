"""/api/v1/checkout and /api/v1/orders (customer)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, status
from fastapi.responses import HTMLResponse
from sqlmodel import col, select

from app.api.deps import CustomerAuth
from app.core.errors import Conflict, NotFound
from app.core.pagination import Page, PageDep, paginate
from app.database.session import DbSession
from app.infrastructure.redis import acquire_lock, release_lock
from app.integrations.payments.factory import ProviderDep
from app.modules.cart import service as cart_service
from app.modules.cart.schemas import QuoteOut, quote_out
from app.modules.catalog.models import Review
from app.modules.catalog.schemas import ReviewIn, ReviewOut
from app.modules.catalog.service import recalculate_store_rating
from app.modules.customers.service import get_address
from app.modules.delivery.schemas import DeliveryChoices
from app.modules.merchants.models import Merchant
from app.modules.orders import service
from app.modules.orders.models import MerchantOrder, MerchantOrderStatus, Order, OrderStatusHistory
from app.modules.orders.receipt import render_receipt
from app.modules.orders.schemas import (
    CancellationRequest,
    CheckoutRequest,
    OrderListItem,
    OrderOut,
    RefundRequestIn,
    StatusHistoryOut,
)
from app.modules.orders.views import order_out
from app.modules.payments import refunds
from app.modules.payments.models import RefundInitiator, RefundScope
from app.modules.payments.schemas import RefundOut
from app.modules.stores.models import Store

checkout_router = APIRouter(prefix="/checkout", tags=["checkout"])
router = APIRouter(prefix="/orders", tags=["orders"])


@checkout_router.post("/quote")
async def checkout_quote(
    ctx: CustomerAuth, db: DbSession, provider: ProviderDep, body: DeliveryChoices | None = None
) -> QuoteOut:
    """Price the cart for the chosen address and delivery/pickup per store.

    Without a body the customer's default address and each store's default method are used.
    """
    cart = await cart_service.get_cart(db, ctx.user_id)
    context = None
    if body is not None and (body.address_id or body.deliveries):
        address = await get_address(db, ctx.user_id, body.address_id) if body.address_id else None
        context = service.delivery_context(
            body, cart_service.address_snapshot(address) if address else None, strict=False
        )
    return quote_out(await cart_service.quote_cart(db, cart, provider.name, delivery=context))


@checkout_router.post("", status_code=status.HTTP_201_CREATED)
async def checkout(
    body: CheckoutRequest,
    ctx: CustomerAuth,
    db: DbSession,
    provider: ProviderDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],
) -> OrderOut:
    lock = f"checkout:{ctx.user_id}"
    if not await acquire_lock(lock, 30):
        raise Conflict("A checkout is already in progress.", code="checkout_in_progress")
    try:
        order = await service.checkout(db, ctx.user, body, provider, idempotency_key)
        return await order_out(db, order)
    finally:
        await release_lock(lock)


@router.get("")
async def list_orders(ctx: CustomerAuth, db: DbSession, page: PageDep) -> Page[OrderListItem]:
    stmt = select(Order).where(col(Order.customer_user_id) == ctx.user_id).order_by(col(Order.created_at).desc())
    rows, total = await paginate(db, stmt, page)
    store_ids = {mo.store_id for o in rows for mo in o.merchant_orders}
    names = (
        {s.id: s.name for s in (await db.exec(select(Store).where(col(Store.id).in_(store_ids)))).all()}
        if store_ids
        else {}
    )
    items = [
        OrderListItem(
            id=o.id,
            number=o.number,
            status=o.status,
            total=o.total,
            store_names=[names.get(mo.store_id, "") for mo in o.merchant_orders],
            created_at=o.created_at,
        )
        for o in rows
    ]
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)


@router.get("/{order_id}")
async def get_order(order_id: uuid.UUID, ctx: CustomerAuth, db: DbSession) -> OrderOut:
    return await order_out(db, await service.get_customer_order(db, ctx.user_id, order_id))


@router.get("/{order_id}/history")
async def order_history(order_id: uuid.UUID, ctx: CustomerAuth, db: DbSession) -> list[StatusHistoryOut]:
    await service.get_customer_order(db, ctx.user_id, order_id)
    rows = await db.exec(
        select(OrderStatusHistory)
        .where(OrderStatusHistory.order_id == order_id)
        .order_by(col(OrderStatusHistory.created_at))
    )
    return [StatusHistoryOut.model_validate(r) for r in rows.all()]


async def _owned_mo(db: DbSession, user_id: uuid.UUID, order_id: uuid.UUID, mo_id: uuid.UUID) -> MerchantOrder:
    mo = await service.get_customer_merchant_order(db, user_id, mo_id)
    if mo.order_id != order_id:
        raise NotFound("Order not found.")
    return mo


@router.post("/{order_id}/merchant-orders/{mo_id}/cancel")
async def request_cancellation(
    order_id: uuid.UUID, mo_id: uuid.UUID, body: CancellationRequest, ctx: CustomerAuth, db: DbSession
) -> OrderOut:
    mo = await _owned_mo(db, ctx.user_id, order_id, mo_id)
    await service.customer_request_cancellation(db, mo, user_id=ctx.user_id, reason=body.reason)
    return await order_out(db, await service.get_customer_order(db, ctx.user_id, order_id))


@router.post("/{order_id}/merchant-orders/{mo_id}/refund-requests", status_code=status.HTTP_201_CREATED)
async def request_refund(
    order_id: uuid.UUID, mo_id: uuid.UUID, body: RefundRequestIn, ctx: CustomerAuth, db: DbSession
) -> RefundOut:
    mo = await _owned_mo(db, ctx.user_id, order_id, mo_id)
    payment = await service.captured_payment(db, mo.id)
    if payment is None:
        raise Conflict("This order has no captured payment.", code="no_payment")
    refund = await refunds.request_refund(
        db,
        payment,
        amount=body.amount,
        initiated_by=RefundInitiator.CUSTOMER,
        actor_user_id=ctx.user_id,
        reason=body.reason,
        scope=RefundScope(body.scope),
    )
    merchant = await db.get(Merchant, mo.merchant_id)
    if merchant is not None:
        from app.modules.notifications.models import NotificationType
        from app.modules.notifications.service import notify

        await notify(
            db,
            merchant.owner_user_id,
            NotificationType.REFUND_STATUS,
            {"order_number": mo.number, "amount": refund.amount, "status": refund.status},
        )
    return RefundOut.model_validate(refund)


@router.get("/{order_id}/merchant-orders/{mo_id}/receipt", response_class=HTMLResponse)
async def receipt(order_id: uuid.UUID, mo_id: uuid.UUID, ctx: CustomerAuth, db: DbSession) -> HTMLResponse:
    order = await service.get_customer_order(db, ctx.user_id, order_id)
    mo = next((m for m in order.merchant_orders if m.id == mo_id), None)
    if mo is None:
        raise NotFound("Order not found.")
    store = await db.get(Store, mo.store_id)
    merchant = await db.get(Merchant, mo.merchant_id)
    assert store is not None and merchant is not None
    payment = await service.captured_payment(db, mo.id) or await service.latest_payment(db, mo.id)
    html = render_receipt(order, mo, store, merchant, payment)
    return HTMLResponse(
        html,
        headers={"Content-Disposition": f'attachment; filename="receipt-{mo.number}.html"'},
    )


@router.post("/{order_id}/merchant-orders/{mo_id}/review", status_code=status.HTTP_201_CREATED)
async def review(order_id: uuid.UUID, mo_id: uuid.UUID, body: ReviewIn, ctx: CustomerAuth, db: DbSession) -> ReviewOut:
    mo = await _owned_mo(db, ctx.user_id, order_id, mo_id)
    if mo.status not in {MerchantOrderStatus.DELIVERED.value, MerchantOrderStatus.COMPLETED.value}:
        raise Conflict("You can review an order once it is delivered or completed.", code="not_reviewable")
    if (
        await db.exec(
            select(Review.id).where(Review.merchant_order_id == mo.id, Review.customer_user_id == ctx.user_id)
        )
    ).first():
        raise Conflict("You have already reviewed this order.", code="already_reviewed")
    item = Review(
        store_id=mo.store_id,
        merchant_order_id=mo.id,
        customer_user_id=ctx.user_id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(item)
    await db.flush()
    await recalculate_store_rating(db, mo.store_id)
    return ReviewOut(
        id=item.id,
        store_id=item.store_id,
        rating=item.rating,
        comment=item.comment,
        customer_name=ctx.user.full_name,
        status=item.status,
        created_at=item.created_at,
    )
