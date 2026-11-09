"""Inventory reservation for merchant orders (database is the source of truth).

reserve:  checkout — quantity_reserved += qty (rows locked FOR UPDATE)
commit:   verified payment — quantity_on_hand -= qty, quantity_reserved -= qty
release:  failure / expiry / cancellation before payment — quantity_reserved -= qty
restock:  cancellation/refund after payment, before shipment — quantity_on_hand += qty
"""

import uuid

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import Conflict
from app.modules.catalog.models import Inventory
from app.modules.orders.models import InventoryState, ItemType, MerchantOrder


def _quantities(mo: MerchantOrder) -> dict[tuple[uuid.UUID, uuid.UUID | None], int]:
    totals: dict[tuple[uuid.UUID, uuid.UUID | None], int] = {}
    for item in mo.items:
        if item.item_type == ItemType.PRODUCT.value and item.product_id:
            key = (item.product_id, item.variant_id)
            totals[key] = totals.get(key, 0) + item.quantity
    return totals


async def _locked_rows(
    session: AsyncSession, keys: list[tuple[uuid.UUID, uuid.UUID | None]]
) -> dict[tuple[uuid.UUID, uuid.UUID | None], Inventory]:
    if not keys:
        return {}
    product_ids = {k[0] for k in keys}
    rows = await session.exec(
        select(Inventory)
        .where(col(Inventory.product_id).in_(product_ids))
        .order_by(col(Inventory.id))
        .with_for_update()
    )
    return {(i.product_id, i.variant_id): i for i in rows.all()}


async def reserve(session: AsyncSession, mo: MerchantOrder) -> None:
    quantities = _quantities(mo)
    rows = await _locked_rows(session, list(quantities))
    for key, qty in quantities.items():
        inv = rows.get(key)
        if inv is None or inv.available < qty:
            raise Conflict(
                "Some items are no longer in stock.", code="insufficient_stock", details={"product_id": str(key[0])}
            )
        inv.quantity_reserved += qty
    mo.inventory_state = InventoryState.RESERVED.value if quantities else InventoryState.NONE.value


async def commit(session: AsyncSession, mo: MerchantOrder) -> bool:
    """Convert the reservation into a stock decrement. Returns False if not reserved."""
    if mo.inventory_state == InventoryState.COMMITTED.value:
        return True
    if mo.inventory_state != InventoryState.RESERVED.value:
        return mo.inventory_state == InventoryState.NONE.value
    quantities = _quantities(mo)
    rows = await _locked_rows(session, list(quantities))
    for key, qty in quantities.items():
        inv = rows[key]
        inv.quantity_reserved -= qty
        inv.quantity_on_hand -= qty
    mo.inventory_state = InventoryState.COMMITTED.value
    mo.reservation_expires_at = None
    return True


async def release(session: AsyncSession, mo: MerchantOrder) -> None:
    if mo.inventory_state != InventoryState.RESERVED.value:
        return
    quantities = _quantities(mo)
    rows = await _locked_rows(session, list(quantities))
    for key, qty in quantities.items():
        inv = rows.get(key)
        if inv is not None:
            inv.quantity_reserved = max(0, inv.quantity_reserved - qty)
    mo.inventory_state = InventoryState.RELEASED.value
    mo.reservation_expires_at = None


async def restock(session: AsyncSession, mo: MerchantOrder) -> None:
    if mo.inventory_state != InventoryState.COMMITTED.value:
        return
    quantities = _quantities(mo)
    rows = await _locked_rows(session, list(quantities))
    for key, qty in quantities.items():
        inv = rows.get(key)
        if inv is not None:
            inv.quantity_on_hand += qty
    mo.inventory_state = InventoryState.RELEASED.value
