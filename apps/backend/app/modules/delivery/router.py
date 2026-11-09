"""/api/v1/merchant/delivery/* and /api/v1/merchant/orders/{id}/delivery — merchant-managed fulfillment.

Every query is scoped to the authenticated merchant; ids in paths are checked
against that merchant (tenant isolation).
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status
from sqlmodel import col, func, select

from app.api.deps import CurrentMerchant
from app.core.errors import NotFound
from app.core.pagination import Page, PageDep, paginate
from app.database.session import DbSession
from app.modules.admin.settings_service import DeliveryFinanceSettings, get_setting
from app.modules.delivery import service
from app.modules.delivery.models import Delivery, DeliveryMethod, DeliveryStatus, DeliveryZone
from app.modules.delivery.providers.registry import provider_for
from app.modules.delivery.schemas import (
    DeliveryListItem,
    DeliverySettingsIn,
    DeliverySettingsOut,
    DeliveryStatusUpdate,
    ZoneIn,
    ZoneOut,
)
from app.modules.merchants.models import MerchantAddress
from app.modules.merchants.service import get_store
from app.modules.orders import service as orders
from app.modules.orders.models import MerchantOrder, Order
from app.modules.orders.schemas import MerchantOrderMerchantView
from app.modules.orders.views import merchant_views
from app.modules.stores.models import Store

router = APIRouter(prefix="/merchant", tags=["merchant-delivery"])


async def _store(db: DbSession, ctx: CurrentMerchant) -> Store:
    store = await get_store(db, ctx.merchant_id)
    if store is None:
        raise NotFound("Store not found.")
    return store


async def _settings_out(db: DbSession, store: Store) -> DeliverySettingsOut:
    row = await service.get_settings(db, store)
    pickups = (
        await db.exec(
            select(func.count(col(MerchantAddress.id))).where(
                MerchantAddress.merchant_id == store.merchant_id, col(MerchantAddress.is_pickup_location)
            )
        )
    ).first()
    zones = (
        await db.exec(
            select(func.count(col(DeliveryZone.id))).where(
                DeliveryZone.store_id == store.id, col(DeliveryZone.is_active).is_(True)
            )
        )
    ).first()
    terms = provider_for(DeliveryMethod.DELIVERY).terms(DeliveryMethod.DELIVERY)
    finance = await get_setting(db, "delivery", DeliveryFinanceSettings)
    return DeliverySettingsOut(
        delivery_enabled=row.delivery_enabled,
        pickup_enabled=row.pickup_enabled,
        pickup_preparation_minutes=row.pickup_preparation_minutes,
        delivery_policy=row.delivery_policy,
        pickup_locations=int(pickups or 0),
        active_zones=int(zones or 0),
        fee_recipient=terms.fee_recipient.value,
        cost_bearer=terms.cost_bearer.value,
        commission_applies_to=finance.commission_applies_to,
        delivery_commission_rate=str(finance.delivery_commission_rate),
    )


@router.get("/delivery/settings")
async def get_delivery_settings(ctx: CurrentMerchant, db: DbSession) -> DeliverySettingsOut:
    return await _settings_out(db, await _store(db, ctx))


@router.put("/delivery/settings")
async def update_delivery_settings(
    body: DeliverySettingsIn, ctx: CurrentMerchant, db: DbSession
) -> DeliverySettingsOut:
    store = await _store(db, ctx)
    await service.update_settings(db, store, body, actor_user_id=ctx.auth.user_id)
    return await _settings_out(db, store)


@router.get("/delivery/zones")
async def list_zones(ctx: CurrentMerchant, db: DbSession) -> list[ZoneOut]:
    store = await _store(db, ctx)
    return [ZoneOut.model_validate(z) for z in await service.list_zones(db, store.id)]


@router.post("/delivery/zones", status_code=status.HTTP_201_CREATED)
async def create_zone(body: ZoneIn, ctx: CurrentMerchant, db: DbSession) -> ZoneOut:
    return ZoneOut.model_validate(await service.create_zone(db, await _store(db, ctx), body))


@router.put("/delivery/zones/{zone_id}")
async def update_zone(zone_id: uuid.UUID, body: ZoneIn, ctx: CurrentMerchant, db: DbSession) -> ZoneOut:
    zone = await service.get_zone(db, await _store(db, ctx), zone_id)
    return ZoneOut.model_validate(await service.update_zone(db, zone, body))


@router.delete("/delivery/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(zone_id: uuid.UUID, ctx: CurrentMerchant, db: DbSession) -> None:
    await service.delete_zone(db, await service.get_zone(db, await _store(db, ctx), zone_id))


@router.get("/deliveries")
async def list_deliveries(
    ctx: CurrentMerchant,
    db: DbSession,
    page: PageDep,
    status_filter: Annotated[DeliveryStatus | None, Query(alias="status")] = None,
    method: Literal["DELIVERY", "PICKUP"] | None = None,
    active: bool = False,
) -> Page[DeliveryListItem]:
    """The merchant's delivery queue. ``active`` limits it to paid, unfinished deliveries."""
    stmt = (
        select(Delivery, MerchantOrder, Order)
        .join(MerchantOrder, col(MerchantOrder.id) == col(Delivery.merchant_order_id))
        .join(Order, col(Order.id) == col(Delivery.order_id))
        .where(Delivery.merchant_id == ctx.merchant_id, col(MerchantOrder.paid_at).is_not(None))
        .order_by(col(Delivery.created_at).desc(), col(Delivery.id))
    )
    if status_filter:
        stmt = stmt.where(Delivery.status == status_filter.value)
    if method:
        stmt = stmt.where(Delivery.method == method)
    if active:
        stmt = stmt.where(col(Delivery.status).not_in([DeliveryStatus.DELIVERED.value, DeliveryStatus.CANCELLED.value]))
    rows, total = await paginate(db, stmt, page)  # type: ignore[arg-type]
    items = [
        DeliveryListItem(
            id=d.id,
            merchant_order_id=mo.id,
            merchant_order_number=mo.number,
            method=d.method,
            status=d.status,
            customer_name=(d.address or {}).get("recipient_name") or order.contact_name,
            city=(d.address or {}).get("city"),
            district=(d.address or {}).get("district"),
            zone_name=d.zone_name,
            fee=mo.delivery_fee,
            estimated_latest_at=d.estimated_latest_at,
            created_at=d.created_at,
        )
        for d, mo, order in rows
    ]
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)


@router.post("/orders/{mo_id}/delivery/status")
async def update_delivery_status(
    mo_id: uuid.UUID, body: DeliveryStatusUpdate, ctx: CurrentMerchant, db: DbSession
) -> MerchantOrderMerchantView:
    mo = await orders.get_merchant_order_for_merchant(db, ctx.merchant_id, mo_id, lock=True)
    delivery = await service.for_merchant_order(db, mo.id, lock=True)
    if delivery is None:
        raise NotFound("This order has no delivery.")
    await service.transition(db, delivery, mo, body, actor_user_id=ctx.auth.user_id)
    return (await merchant_views(db, [mo]))[0]
