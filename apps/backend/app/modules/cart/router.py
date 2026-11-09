"""/api/v1/cart — always priced by the backend."""

import uuid

from fastapi import APIRouter

from app.api.deps import CustomerAuth
from app.database.session import DbSession
from app.integrations.payments.factory import ProviderDep
from app.modules.cart import service
from app.modules.cart.schemas import CartItemAdd, CartItemUpdate, QuoteOut, quote_out

router = APIRouter(prefix="/cart", tags=["cart"])


async def _respond(db: DbSession, user_id: uuid.UUID, provider_name: str) -> QuoteOut:
    cart = await service.get_cart(db, user_id)
    return quote_out(await service.quote_cart(db, cart, provider_name))


@router.get("")
async def get_cart(ctx: CustomerAuth, db: DbSession, provider: ProviderDep) -> QuoteOut:
    return await _respond(db, ctx.user_id, provider.name)


@router.post("/items")
async def add_item(body: CartItemAdd, ctx: CustomerAuth, db: DbSession, provider: ProviderDep) -> QuoteOut:
    cart = await service.get_cart(db, ctx.user_id, lock=True)
    await service.add_item(db, cart, body)
    return await _respond(db, ctx.user_id, provider.name)


@router.patch("/items/{item_id}")
async def update_item(
    item_id: uuid.UUID, body: CartItemUpdate, ctx: CustomerAuth, db: DbSession, provider: ProviderDep
) -> QuoteOut:
    cart = await service.get_cart(db, ctx.user_id, lock=True)
    await service.update_item(db, cart, item_id, body.quantity)
    return await _respond(db, ctx.user_id, provider.name)


@router.delete("/items/{item_id}")
async def remove_item(item_id: uuid.UUID, ctx: CustomerAuth, db: DbSession, provider: ProviderDep) -> QuoteOut:
    cart = await service.get_cart(db, ctx.user_id, lock=True)
    await service.remove_item(db, cart, item_id)
    return await _respond(db, ctx.user_id, provider.name)


@router.delete("")
async def clear_cart(ctx: CustomerAuth, db: DbSession, provider: ProviderDep) -> QuoteOut:
    cart = await service.get_cart(db, ctx.user_id, lock=True)
    await service.clear(db, cart)
    return await _respond(db, ctx.user_id, provider.name)
