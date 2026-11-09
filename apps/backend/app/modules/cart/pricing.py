"""Server-side pricing for carts and checkout.

Frontend-provided prices are never trusted: every amount is recalculated from the
catalog. Lines are grouped per merchant ("checkout groups"); each group becomes one
merchant order and is paid by its own payment transaction.

Pricing rules:
* Unit prices come from the product/variant/service (discounted price when set).
* Delivery: groups containing items that need delivery get a delivery quote from the
  delivery module (merchant delivery zones or customer pickup); the delivery fee is
  calculated independently of item prices and commissions
  (see ``app.modules.delivery``).
* VAT: added at the platform VAT rate for VAT-registered merchants only, on items
  after discount, and on the delivery fee when configured. Prices exclude VAT.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.money import percentage_of
from app.modules.admin.settings_service import DeliveryFinanceSettings, TaxSettings, get_setting
from app.modules.catalog.models import (
    CatalogStatus,
    Inventory,
    Product,
    ProductVariant,
    Service,
    ServiceAvailability,
)
from app.modules.catalog.service import unit_prices
from app.modules.delivery.models import DeliveryMethod
from app.modules.delivery.pricing import DeliveryCharge
from app.modules.delivery.quoting import DeliveryContext, GroupDelivery, load_store_delivery, quote_group
from app.modules.merchants.models import Merchant, MerchantStatus
from app.modules.merchants.service import can_accept_payments, get_payment_account
from app.modules.orders.models import FulfillmentType, ItemType
from app.modules.stores.models import Store, StoreStatus


@dataclass(frozen=True)
class LineInput:
    quantity: int
    product_id: uuid.UUID | None = None
    variant_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    cart_item_id: uuid.UUID | None = None


@dataclass
class PricedLine:
    input: LineInput
    item_type: ItemType
    title: str
    sku: str | None
    image_url: str | None
    category_id: uuid.UUID | None
    requires_shipping: bool
    unit_price: int
    unit_discount: int
    quantity: int
    available_quantity: int | None
    issues: list[str] = field(default_factory=list)

    @property
    def line_subtotal(self) -> int:
        return self.unit_price * self.quantity

    @property
    def line_discount(self) -> int:
        return self.unit_discount * self.quantity

    @property
    def line_total(self) -> int:
        return self.line_subtotal - self.line_discount


@dataclass
class MerchantGroup:
    merchant: Merchant
    store: Store
    lines: list[PricedLine] = field(default_factory=list)
    delivery: GroupDelivery = field(default_factory=lambda: GroupDelivery(method=DeliveryMethod.NONE))
    vat_rate: Decimal = Decimal("0")
    items_vat: int = 0
    issues: list[str] = field(default_factory=list)

    @property
    def charge(self) -> DeliveryCharge:
        return self.delivery.charge

    @property
    def delivery_fee(self) -> int:
        return self.delivery.charge.fee

    @property
    def vat_total(self) -> int:
        return self.items_vat + self.delivery.charge.vat

    @property
    def items_subtotal(self) -> int:
        return sum(line.line_subtotal for line in self.lines)

    @property
    def discount_total(self) -> int:
        return sum(line.line_discount for line in self.lines)

    @property
    def items_net(self) -> int:
        return self.items_subtotal - self.discount_total

    @property
    def total(self) -> int:
        return self.items_net + self.delivery_fee + self.vat_total

    @property
    def requires_delivery(self) -> bool:
        return any(line.requires_shipping for line in self.lines)

    @property
    def fulfillment_type(self) -> FulfillmentType:
        if any(line.item_type == ItemType.PRODUCT for line in self.lines):
            return FulfillmentType.PHYSICAL
        return FulfillmentType.SERVICE

    @property
    def can_checkout(self) -> bool:
        return not self.issues and all(not line.issues for line in self.lines)


@dataclass
class Quote:
    groups: list[MerchantGroup]
    currency: str = "SAR"

    @property
    def items_subtotal(self) -> int:
        return sum(g.items_subtotal for g in self.groups)

    @property
    def discount_total(self) -> int:
        return sum(g.discount_total for g in self.groups)

    @property
    def delivery_total(self) -> int:
        return sum(g.delivery_fee for g in self.groups)

    @property
    def vat_total(self) -> int:
        return sum(g.vat_total for g in self.groups)

    @property
    def total(self) -> int:
        return sum(g.total for g in self.groups)

    @property
    def requires_delivery(self) -> bool:
        return any(g.requires_delivery for g in self.groups)

    @property
    def needs_address(self) -> bool:
        return any(g.delivery.method == DeliveryMethod.DELIVERY for g in self.groups if g.requires_delivery)

    @property
    def can_checkout(self) -> bool:
        return bool(self.groups) and all(g.can_checkout for g in self.groups)


async def build_quote(
    session: AsyncSession,
    lines: list[LineInput],
    *,
    provider_name: str,
    lock_inventory: bool = False,
    delivery: DeliveryContext | None = None,
) -> Quote:
    product_ids = {line.product_id for line in lines if line.product_id}
    service_ids = {line.service_id for line in lines if line.service_id}
    variant_ids = {line.variant_id for line in lines if line.variant_id}
    products = (
        {p.id: p for p in (await session.exec(select(Product).where(col(Product.id).in_(product_ids)))).all()}
        if product_ids
        else {}
    )
    services = (
        {s.id: s for s in (await session.exec(select(Service).where(col(Service.id).in_(service_ids)))).all()}
        if service_ids
        else {}
    )
    variants = (
        {
            v.id: v
            for v in (await session.exec(select(ProductVariant).where(col(ProductVariant.id).in_(variant_ids)))).all()
        }
        if variant_ids
        else {}
    )
    inventory: dict[tuple[uuid.UUID, uuid.UUID | None], Inventory] = {}
    if product_ids:
        stmt = select(Inventory).where(col(Inventory.product_id).in_(product_ids)).order_by(col(Inventory.id))
        if lock_inventory:
            stmt = stmt.with_for_update()  # consistent ordering avoids deadlocks
        inventory = {(i.product_id, i.variant_id): i for i in (await session.exec(stmt)).all()}

    store_ids = {p.store_id for p in products.values()} | {s.store_id for s in services.values()}
    stores = (
        {s.id: s for s in (await session.exec(select(Store).where(col(Store.id).in_(store_ids)))).all()}
        if store_ids
        else {}
    )
    merchant_ids = {s.merchant_id for s in stores.values()}
    merchants = (
        {m.id: m for m in (await session.exec(select(Merchant).where(col(Merchant.id).in_(merchant_ids)))).all()}
        if merchant_ids
        else {}
    )

    tax = await get_setting(session, "tax", TaxSettings)
    groups: dict[uuid.UUID, MerchantGroup] = {}
    requested: dict[tuple[uuid.UUID, uuid.UUID | None], int] = {}

    for line in lines:
        priced: PricedLine
        store: Store | None = None
        if line.product_id:
            product = products.get(line.product_id)
            if product is None:
                continue  # deleted product: silently dropped from the quote
            store = stores[product.store_id]
            variant = variants.get(line.variant_id) if line.variant_id else None
            price, discounted = unit_prices(product, variant)
            key = (product.id, variant.id if variant else None)
            inv = inventory.get(key)
            priced = PricedLine(
                input=line,
                item_type=ItemType.PRODUCT,
                title=product.title + (f" — {variant.name}" if variant else ""),
                sku=variant.sku if variant else product.sku,
                image_url=product.images[0].url if product.images else None,
                category_id=product.category_id,
                requires_shipping=product.requires_shipping,
                unit_price=price,
                unit_discount=(price - discounted) if discounted is not None and discounted < price else 0,
                quantity=line.quantity,
                available_quantity=inv.available if inv else 0,
            )
            if product.status != CatalogStatus.ACTIVE.value or not product.is_available:
                priced.issues.append("unavailable")
            if product.variants and variant is None:
                priced.issues.append("variant_required")
            if variant is not None and (variant.product_id != product.id or not variant.is_active):
                priced.issues.append("unavailable")
            requested[key] = requested.get(key, 0) + line.quantity
            if inv is None or inv.available < requested[key]:
                priced.issues.append("insufficient_stock" if inv and inv.available > 0 else "out_of_stock")
        elif line.service_id:
            service = services.get(line.service_id)
            if service is None:
                continue
            store = stores[service.store_id]
            discounted = service.discounted_price
            priced = PricedLine(
                input=line,
                item_type=ItemType.SERVICE,
                title=service.title,
                sku=None,
                image_url=service.images[0].url if service.images else None,
                category_id=service.category_id,
                requires_shipping=False,
                unit_price=service.price,
                unit_discount=(service.price - discounted)
                if discounted is not None and discounted < service.price
                else 0,
                quantity=line.quantity,
                available_quantity=None,
            )
            if (
                service.status != CatalogStatus.ACTIVE.value
                or service.availability != ServiceAvailability.AVAILABLE.value
            ):
                priced.issues.append("unavailable")
        else:
            continue

        merchant = merchants[store.merchant_id]
        group = groups.get(merchant.id)
        if group is None:
            group = MerchantGroup(merchant=merchant, store=store)
            if merchant.status != MerchantStatus.APPROVED.value or store.status != StoreStatus.ACTIVE.value:
                group.issues.append("store_unavailable")
            elif not store.is_open:
                group.issues.append("store_closed")
            elif not can_accept_payments(
                merchant, store, await get_payment_account(session, merchant.id, provider_name)
            ):
                group.issues.append("merchant_cannot_accept_payments")
            groups[merchant.id] = group
        group.lines.append(priced)

    context = delivery or DeliveryContext()
    delivering = [g for g in groups.values() if g.requires_delivery]
    if delivering:
        finance = await get_setting(session, "delivery", DeliveryFinanceSettings)
        store_data = await load_store_delivery(session, [g.store for g in delivering])
        for group in delivering:
            group.delivery = await quote_group(
                store=group.store,
                merchant=group.merchant,
                data=store_data[group.store.id],
                items_net=group.items_net,
                context=context,
                tax=tax,
                finance=finance,
            )
            if group.delivery.issue:
                group.issues.append(group.delivery.issue)
    for group in groups.values():
        if group.merchant.is_vat_registered:
            group.vat_rate = tax.vat_rate
            group.items_vat = percentage_of(group.items_net, tax.vat_rate)

    ordered = sorted(groups.values(), key=lambda g: g.store.name)
    return Quote(groups=ordered)
