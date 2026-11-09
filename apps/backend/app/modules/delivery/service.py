"""Delivery configuration and the delivery lifecycle.

The delivery status is the fulfillment state machine of physical merchant orders;
the merchant order status follows it:

=================  ==========================
Delivery status    Merchant order status
=================  ==========================
PENDING            PENDING_PAYMENT / PAID
CONFIRMED          ACCEPTED
PREPARING          PROCESSING
READY_FOR_PICKUP   PROCESSING
OUT_FOR_DELIVERY   SHIPPED
DELIVERED          DELIVERED
FAILED             (unchanged; can be retried or cancelled with a refund)
CANCELLED          CANCELLED / REJECTED / REFUNDED
=================  ==========================

Which manual changes are allowed comes from the delivery provider. Statuses are only
ever changed by an authenticated actor (or the system for cancellations); there is
no simulated tracking.
"""

import uuid
from datetime import timedelta

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import Conflict, NotFound
from app.core.security import utcnow
from app.modules.admin.audit import record_audit
from app.modules.delivery.models import (
    TERMINAL_DELIVERY_STATUSES,
    Delivery,
    DeliveryEvent,
    DeliveryMethod,
    DeliveryStatus,
    DeliveryZone,
    EventSource,
    StoreDeliverySettings,
)
from app.modules.delivery.providers.base import AddressSnapshot
from app.modules.delivery.providers.registry import get_provider
from app.modules.delivery.quoting import GroupDelivery
from app.modules.delivery.schemas import (
    DeliveryEventOut,
    DeliveryOut,
    DeliverySettingsIn,
    DeliveryStatusUpdate,
    ZoneIn,
)
from app.modules.notifications.models import NotificationType
from app.modules.notifications.service import notify
from app.modules.orders.models import (
    CancellationStatus,
    MerchantOrder,
    MerchantOrderStatus,
    Shipment,
    ShipmentStatus,
)
from app.modules.stores.models import Store

S = DeliveryStatus
MO = MerchantOrderStatus

ORDER_STATUS_FOR: dict[DeliveryStatus, MerchantOrderStatus] = {
    S.CONFIRMED: MO.ACCEPTED,
    S.PREPARING: MO.PROCESSING,
    S.READY_FOR_PICKUP: MO.PROCESSING,
    S.OUT_FOR_DELIVERY: MO.SHIPPED,
    S.DELIVERED: MO.DELIVERED,
}
# Merchant order statuses in which the delivery can still progress.
ACTIVE_ORDER_STATUSES = {MO.PAID, MO.ACCEPTED, MO.PROCESSING, MO.SHIPPED}
MAX_ZONES_PER_STORE = 200


# -- configuration ------------------------------------------------------------------------


async def get_settings(session: AsyncSession, store: Store, *, lock: bool = False) -> StoreDeliverySettings:
    stmt = select(StoreDeliverySettings).where(StoreDeliverySettings.store_id == store.id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await session.exec(stmt)).first()
    if row is None:
        row = StoreDeliverySettings(store_id=store.id, merchant_id=store.merchant_id)
        session.add(row)
        await session.flush()
    return row


async def update_settings(
    session: AsyncSession, store: Store, data: DeliverySettingsIn, *, actor_user_id: uuid.UUID
) -> StoreDeliverySettings:
    row = await get_settings(session, store, lock=True)
    before = {k: getattr(row, k) for k in DeliverySettingsIn.model_fields}
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    await record_audit(
        session,
        actor_user_id=actor_user_id,
        action="delivery.settings.update",
        entity_type="store",
        entity_id=store.id,
        before=before,
        after=data.model_dump(),
    )
    await session.flush()
    return row


async def list_zones(session: AsyncSession, store_id: uuid.UUID) -> list[DeliveryZone]:
    rows = await session.exec(
        select(DeliveryZone)
        .where(DeliveryZone.store_id == store_id)
        .order_by(col(DeliveryZone.is_active).desc(), col(DeliveryZone.created_at))
    )
    return list(rows.all())


async def get_zone(session: AsyncSession, store: Store, zone_id: uuid.UUID) -> DeliveryZone:
    zone = await session.get(DeliveryZone, zone_id, with_for_update=True)
    if zone is None or zone.store_id != store.id:
        raise NotFound("Delivery zone not found.")  # tenant isolation
    return zone


async def create_zone(session: AsyncSession, store: Store, data: ZoneIn) -> DeliveryZone:
    if len(await list_zones(session, store.id)) >= MAX_ZONES_PER_STORE:
        raise Conflict("A store can have at most 200 delivery zones.", code="too_many_zones")
    zone = DeliveryZone(store_id=store.id, merchant_id=store.merchant_id, **data.model_dump())
    session.add(zone)
    await session.flush()
    return zone


async def update_zone(session: AsyncSession, zone: DeliveryZone, data: ZoneIn) -> DeliveryZone:
    # Orders keep their own snapshot (fee on the merchant order, zone name and ETA on
    # the delivery), so editing a zone only affects future checkouts.
    for key, value in data.model_dump().items():
        setattr(zone, key, value)
    await session.flush()
    return zone


async def delete_zone(session: AsyncSession, zone: DeliveryZone) -> None:
    await session.delete(zone)
    await session.flush()


# -- creation at checkout -----------------------------------------------------------------


async def create_for_merchant_order(
    session: AsyncSession,
    mo: MerchantOrder,
    group: GroupDelivery,
    *,
    address: AddressSnapshot | None,
    instructions: str,
    actor_user_id: uuid.UUID,
) -> Delivery | None:
    if group.method == DeliveryMethod.NONE:
        return None
    quote = group.quote
    assert quote is not None and quote.available, "checkout must only create priced deliveries"
    delivery = Delivery(
        merchant_order_id=mo.id,
        order_id=mo.order_id,
        merchant_id=mo.merchant_id,
        store_id=mo.store_id,
        customer_user_id=mo.customer_user_id,
        method=quote.method.value,
        provider=quote.provider,
        status=S.PENDING.value,
        zone_id=quote.zone_id,
        zone_name=quote.zone_name,
        address=address.as_dict() if address and quote.method == DeliveryMethod.DELIVERY else None,
        latitude=address.latitude if address and quote.method == DeliveryMethod.DELIVERY else None,
        longitude=address.longitude if address and quote.method == DeliveryMethod.DELIVERY else None,
        instructions=instructions,
        pickup_location_id=quote.pickup_location.id if quote.pickup_location else None,
        pickup_location=quote.pickup_location.as_dict() if quote.pickup_location else None,
        eta_min_minutes=quote.eta_min_minutes,
        eta_max_minutes=quote.eta_max_minutes,
    )
    session.add(delivery)
    await session.flush()
    session.add(
        DeliveryEvent(
            delivery_id=delivery.id,
            from_status=None,
            to_status=S.PENDING.value,
            source=EventSource.CUSTOMER.value,
            actor_user_id=actor_user_id,
            note=None,
        )
    )
    return delivery


# -- queries --------------------------------------------------------------------------------


async def for_merchant_order(session: AsyncSession, mo_id: uuid.UUID, *, lock: bool = False) -> Delivery | None:
    stmt = select(Delivery).where(Delivery.merchant_order_id == mo_id)
    if lock:
        stmt = stmt.with_for_update()
    return (await session.exec(stmt)).first()


async def for_merchant_orders(session: AsyncSession, mo_ids: list[uuid.UUID]) -> dict[uuid.UUID, Delivery]:
    if not mo_ids:
        return {}
    rows = await session.exec(select(Delivery).where(col(Delivery.merchant_order_id).in_(mo_ids)))
    return {d.merchant_order_id: d for d in rows.all()}


async def events(session: AsyncSession, delivery_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[DeliveryEvent]]:
    out: dict[uuid.UUID, list[DeliveryEvent]] = {d: [] for d in delivery_ids}
    if not delivery_ids:
        return out
    rows = await session.exec(
        select(DeliveryEvent)
        .where(col(DeliveryEvent.delivery_id).in_(delivery_ids))
        .order_by(col(DeliveryEvent.created_at), col(DeliveryEvent.id))
    )
    for event in rows.all():
        out[event.delivery_id].append(event)
    return out


def next_statuses(delivery: Delivery, mo: MerchantOrder) -> list[DeliveryStatus]:
    """Status changes the merchant may make now."""
    status = DeliveryStatus(delivery.status)
    if status in TERMINAL_DELIVERY_STATUSES or MerchantOrderStatus(mo.status) not in ACTIVE_ORDER_STATUSES:
        return []
    provider = get_provider(delivery.provider)
    if not provider.capabilities.manual_status_updates:
        return []
    if status == S.PENDING:
        return [S.CONFIRMED] if mo.status == MO.PAID.value else []
    if mo.cancellation_status == CancellationStatus.REQUESTED.value:
        return []  # resolve the customer's cancellation request first
    allowed = provider.manual_transitions(DeliveryMethod(delivery.method)).get(status, frozenset())
    order = list(DeliveryStatus)
    return sorted(allowed, key=order.index)


def delivery_out(
    delivery: Delivery, mo: MerchantOrder, event_rows: list[DeliveryEvent], *, merchant_view: bool
) -> DeliveryOut:
    return DeliveryOut(
        id=delivery.id,
        merchant_order_id=delivery.merchant_order_id,
        method=delivery.method,
        provider=delivery.provider,
        status=delivery.status,
        zone_name=delivery.zone_name,
        address=delivery.address,
        latitude=delivery.latitude,
        longitude=delivery.longitude,
        instructions=delivery.instructions,
        pickup_location=delivery.pickup_location,
        eta_min_minutes=delivery.eta_min_minutes,
        eta_max_minutes=delivery.eta_max_minutes,
        estimated_earliest_at=delivery.estimated_earliest_at,
        estimated_latest_at=delivery.estimated_latest_at,
        attempts=delivery.attempts,
        failure_reason=delivery.failure_reason,
        confirmed_at=delivery.confirmed_at,
        ready_at=delivery.ready_at,
        out_for_delivery_at=delivery.out_for_delivery_at,
        delivered_at=delivery.delivered_at,
        failed_at=delivery.failed_at,
        cancelled_at=delivery.cancelled_at,
        fee=mo.delivery_fee,
        fee_waived=mo.delivery_fee_waived,
        vat=mo.delivery_vat,
        fee_recipient=mo.delivery_fee_recipient,
        cost_bearer=mo.delivery_cost_bearer,
        next_statuses=[s.value for s in next_statuses(delivery, mo)] if merchant_view else [],
        events=[DeliveryEventOut.model_validate(e) for e in event_rows],
    )


# -- lifecycle ------------------------------------------------------------------------------


def _record(
    session: AsyncSession,
    delivery: Delivery,
    from_status: str | None,
    to_status: DeliveryStatus,
    *,
    source: EventSource,
    actor_user_id: uuid.UUID | None,
    note: str | None,
) -> None:
    session.add(
        DeliveryEvent(
            delivery_id=delivery.id,
            from_status=from_status,
            to_status=to_status.value,
            source=source.value,
            actor_user_id=actor_user_id,
            note=note,
        )
    )


async def transition(
    session: AsyncSession,
    delivery: Delivery,
    mo: MerchantOrder,
    data: DeliveryStatusUpdate,
    *,
    actor_user_id: uuid.UUID,
    source: EventSource = EventSource.MERCHANT,
) -> Delivery:
    """Apply a manual status change and move the merchant order along with it."""
    from app.modules.orders import service as orders

    target = DeliveryStatus(data.status)
    current = DeliveryStatus(delivery.status)
    if target not in next_statuses(delivery, mo):
        if mo.cancellation_status == CancellationStatus.REQUESTED.value and current != S.PENDING:
            raise Conflict("Resolve the customer's cancellation request first.", code="cancellation_pending")
        raise Conflict(f"Cannot move this delivery from {current} to {target}.", code="invalid_transition")

    now = utcnow()
    delivery.status = target.value
    if target == S.CONFIRMED:
        delivery.confirmed_at = now
        delivery.estimated_earliest_at = now + timedelta(minutes=delivery.eta_min_minutes)
        delivery.estimated_latest_at = now + timedelta(minutes=delivery.eta_max_minutes)
    elif target in {S.OUT_FOR_DELIVERY, S.READY_FOR_PICKUP}:
        delivery.attempts += 1
        delivery.failure_reason = None
        if target == S.OUT_FOR_DELIVERY:
            delivery.out_for_delivery_at = now
        else:
            delivery.ready_at = now
    elif target == S.DELIVERED:
        delivery.delivered_at = now
    elif target == S.FAILED:
        delivery.failed_at = now
        delivery.failure_reason = data.failure_reason

    if target == S.OUT_FOR_DELIVERY and (data.carrier or data.tracking_number or data.tracking_url):
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
    if target == S.DELIVERED:
        for shipment in mo.shipments:
            if shipment.status != ShipmentStatus.DELIVERED.value:
                shipment.status = ShipmentStatus.DELIVERED.value
                shipment.delivered_at = now

    note = data.failure_reason if target == S.FAILED else data.note
    _record(session, delivery, current.value, target, source=source, actor_user_id=actor_user_id, note=note)
    if data.note:
        mo.merchant_note = data.note

    provider = get_provider(delivery.provider)
    if target == S.CONFIRMED:
        await provider.on_confirmed(delivery)

    order_status = ORDER_STATUS_FOR.get(target)
    if order_status is not None and order_status.value != mo.status:
        await orders.set_merchant_order_status(
            session, mo, order_status, actor_user_id=actor_user_id, note=note, notify_customer=False
        )
    await notify(
        session,
        mo.customer_user_id,
        NotificationType.DELIVERY_STATUS_CHANGED,
        {
            "order_number": mo.number,
            "status": target.value,
            "method": delivery.method,
            "merchant_order_id": str(mo.id),
        },
    )
    await session.flush()
    return delivery


async def cancel_for_order(
    session: AsyncSession, mo: MerchantOrder, *, actor_user_id: uuid.UUID | None, note: str | None
) -> None:
    """Called when a merchant order is cancelled, rejected or refunded before delivery."""
    delivery = await for_merchant_order(session, mo.id, lock=True)
    if delivery is None or DeliveryStatus(delivery.status) in TERMINAL_DELIVERY_STATUSES:
        return
    previous = delivery.status
    delivery.status = S.CANCELLED.value
    delivery.cancelled_at = utcnow()
    _record(
        session,
        delivery,
        previous,
        S.CANCELLED,
        source=EventSource.SYSTEM,  # follows the order's cancellation; the actor is recorded
        actor_user_id=actor_user_id,
        note=note,
    )
    await get_provider(delivery.provider).on_cancelled(delivery)
