import uuid

from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import NotFound, ValidationFailed
from app.modules.cart.models import Cart, CartItem
from app.modules.cart.pricing import LineInput, Quote, build_quote
from app.modules.cart.schemas import CartItemAdd
from app.modules.catalog.models import CatalogStatus, Product, ProductVariant, Service
from app.modules.customers.models import CustomerAddress
from app.modules.delivery.providers.base import AddressSnapshot
from app.modules.delivery.quoting import DeliveryContext

MAX_CART_LINES = 100


async def get_cart(session: AsyncSession, user_id: uuid.UUID, *, lock: bool = False) -> Cart:
    stmt = select(Cart).where(Cart.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()
    cart = (await session.exec(stmt)).first()
    if cart is None:
        cart = Cart(user_id=user_id, currency="SAR", items=[])
        session.add(cart)
        await session.flush()
    return cart


def cart_lines(cart: Cart) -> list[LineInput]:
    return [
        LineInput(
            quantity=item.quantity,
            product_id=item.product_id,
            variant_id=item.variant_id,
            service_id=item.service_id,
            cart_item_id=item.id,
        )
        for item in cart.items
    ]


async def quote_cart(
    session: AsyncSession,
    cart: Cart,
    provider_name: str,
    *,
    lock_inventory: bool = False,
    delivery: DeliveryContext | None = None,
) -> Quote:
    if delivery is None:
        # Browsing the cart: estimate delivery for the customer's default address.
        default = (
            await session.exec(
                select(CustomerAddress).where(
                    CustomerAddress.user_id == cart.user_id,
                    col(CustomerAddress.is_default).is_(True),
                    col(CustomerAddress.is_deleted).is_(False),
                )
            )
        ).first()
        delivery = DeliveryContext(address=address_snapshot(default) if default else None)
    return await build_quote(
        session, cart_lines(cart), provider_name=provider_name, lock_inventory=lock_inventory, delivery=delivery
    )


def address_snapshot(address: CustomerAddress) -> AddressSnapshot:
    return AddressSnapshot(
        recipient_name=address.recipient_name,
        phone=address.phone,
        region=address.region,
        city=address.city,
        district=address.district,
        street=address.street,
        building_number=address.building_number,
        postal_code=address.postal_code,
        additional_info=address.additional_info,
        latitude=address.latitude,
        longitude=address.longitude,
    )


async def add_item(session: AsyncSession, cart: Cart, data: CartItemAdd) -> CartItem:
    if data.product_id:
        product = await session.get(Product, data.product_id)
        if product is None or product.status != CatalogStatus.ACTIVE.value:
            raise NotFound("Product not found.")
        if product.variants and data.variant_id is None:
            raise ValidationFailed("Please choose a variant.", code="variant_required")
        if data.variant_id:
            variant = await session.get(ProductVariant, data.variant_id)
            if variant is None or variant.product_id != product.id or not variant.is_active:
                raise NotFound("Variant not found.")
    else:
        service = await session.get(Service, data.service_id)
        if service is None or service.status != CatalogStatus.ACTIVE.value:
            raise NotFound("Service not found.")

    for item in cart.items:
        if (
            item.product_id == data.product_id
            and item.variant_id == data.variant_id
            and item.service_id == data.service_id
        ):
            item.quantity = min(item.quantity + data.quantity, 999)
            await session.flush()
            return item
    if len(cart.items) >= MAX_CART_LINES:
        raise ValidationFailed("Your cart is full.", code="cart_full")
    item = CartItem(
        cart_id=cart.id,
        product_id=data.product_id,
        variant_id=data.variant_id,
        service_id=data.service_id,
        quantity=data.quantity,
    )
    cart.items.append(item)
    await session.flush()
    return item


def _find_item(cart: Cart, item_id: uuid.UUID) -> CartItem:
    for item in cart.items:
        if item.id == item_id:
            return item
    raise NotFound("Cart item not found.")


async def update_item(session: AsyncSession, cart: Cart, item_id: uuid.UUID, quantity: int) -> None:
    _find_item(cart, item_id).quantity = quantity
    await session.flush()


async def remove_item(session: AsyncSession, cart: Cart, item_id: uuid.UUID) -> None:
    cart.items.remove(_find_item(cart, item_id))
    await session.flush()


async def clear(session: AsyncSession, cart: Cart) -> None:
    await session.exec(delete(CartItem).where(col(CartItem.cart_id) == cart.id))
    await session.refresh(cart, ["items"])
