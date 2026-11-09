"""Catalog: categories, products, variants, inventory, services and reviews."""

import re
import secrets
import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy.exc import IntegrityError
from sqlmodel import and_, col, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import Select

from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.modules.catalog.models import (
    CatalogStatus,
    Category,
    Inventory,
    Product,
    ProductImage,
    ProductVariant,
    Review,
    ReviewStatus,
    Service,
    ServiceImage,
)
from app.modules.catalog.schemas import (
    CategoryOut,
    ImageIn,
    ImageOut,
    InventoryAdjust,
    InventoryOut,
    ProductIn,
    ProductOut,
    ProductUpdate,
    ServiceIn,
    ServiceOut,
    ServiceUpdate,
    StoreSummary,
    VariantIn,
    VariantOut,
)
from app.modules.merchants.models import Merchant, MerchantStatus
from app.modules.stores.models import Store, StoreStatus

# -- helpers ----------------------------------------------------------------------------


def slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]
    return f"{base or 'item'}-{secrets.token_hex(3)}"


def public_store_conditions() -> list[ColumnElement[bool]]:
    """Only approved and active merchants are visible publicly."""
    return [col(Store.status) == StoreStatus.ACTIVE.value, col(Merchant.status) == MerchantStatus.APPROVED.value]


def store_summary(store: Store) -> StoreSummary:
    return StoreSummary(
        id=store.id,
        slug=store.slug,
        name=store.name,
        city=store.city,
        logo_url=store.logo_url,
        rating_avg=float(store.rating_avg),
        rating_count=store.rating_count,
    )


async def category_with_descendants(session: AsyncSession, category_id: uuid.UUID) -> list[uuid.UUID]:
    tree = select(Category.id).where(Category.id == category_id).cte(recursive=True)
    tree = tree.union_all(select(Category.id).where(Category.parent_id == tree.c.id))
    return list((await session.exec(select(tree.c.id))).all())


async def category_ancestors(session: AsyncSession, category_id: uuid.UUID) -> list[uuid.UUID]:
    """Category id followed by its ancestors, nearest first."""
    chain: list[uuid.UUID] = []
    current: uuid.UUID | None = category_id
    while current is not None and current not in chain and len(chain) < 20:
        chain.append(current)
        current = (await session.exec(select(Category.parent_id).where(Category.id == current))).first()
    return chain


async def resolve_category_slug(session: AsyncSession, slug: str) -> Category:
    category = (
        await session.exec(select(Category).where(Category.slug == slug, col(Category.is_active).is_(True)))
    ).first()
    if category is None:
        raise NotFound("Category not found.")
    return category


async def list_categories(session: AsyncSession, *, include_inactive: bool = False) -> list[CategoryOut]:
    stmt = select(Category).order_by(col(Category.sort_order), col(Category.name_en))
    if not include_inactive:
        stmt = stmt.where(col(Category.is_active).is_(True))
    return [CategoryOut.model_validate(c) for c in (await session.exec(stmt)).all()]


async def _validate_category(session: AsyncSession, category_id: uuid.UUID | None, kind: str) -> None:
    if category_id is None:
        return
    category = await session.get(Category, category_id)
    if category is None or not category.is_active:
        raise ValidationFailed("Unknown category.", code="invalid_category")
    if category.kind not in ("BOTH", kind):
        raise ValidationFailed(f"Category does not accept {kind.lower()}s.", code="invalid_category")


# -- inventory ---------------------------------------------------------------------------


async def _inventory_map(
    session: AsyncSession, product_ids: Sequence[uuid.UUID]
) -> dict[tuple[uuid.UUID, uuid.UUID | None], Inventory]:
    if not product_ids:
        return {}
    rows = await session.exec(select(Inventory).where(col(Inventory.product_id).in_(product_ids)))
    return {(i.product_id, i.variant_id): i for i in rows.all()}


def unit_prices(product: Product, variant: ProductVariant | None) -> tuple[int, int | None]:
    """Single source of truth for (price, discounted_price) of a product or variant."""
    if variant is None:
        return product.price, product.discounted_price
    if variant.price is not None:
        return variant.price, variant.discounted_price
    discounted = variant.discounted_price if variant.discounted_price is not None else product.discounted_price
    return product.price, discounted


def _available(inv: Inventory | None) -> int:
    return inv.available if inv else 0


def product_out(
    product: Product, store: Store, inventory: dict[tuple[uuid.UUID, uuid.UUID | None], Inventory]
) -> ProductOut:
    variants = [
        VariantOut(
            id=v.id,
            sku=v.sku,
            name=v.name,
            options=v.options,
            price=unit_prices(product, v)[0],
            discounted_price=unit_prices(product, v)[1],
            is_active=v.is_active,
            available_quantity=_available(inventory.get((product.id, v.id))),
        )
        for v in product.variants
    ]
    if product.variants:
        available = sum(v.available_quantity for v in variants if v.is_active)
    else:
        available = _available(inventory.get((product.id, None)))
    return ProductOut(
        id=product.id,
        merchant_id=product.merchant_id,
        store=store_summary(store),
        category_id=product.category_id,
        title=product.title,
        slug=product.slug,
        description=product.description,
        sku=product.sku,
        price=product.price,
        discounted_price=product.discounted_price,
        status=product.status,
        is_available=product.is_available,
        requires_shipping=product.requires_shipping,
        weight_grams=product.weight_grams,
        in_stock=product.is_available and available > 0,
        available_quantity=available,
        images=[ImageOut.model_validate(i) for i in product.images],
        variants=variants,
        is_featured=product.is_featured,
        moderation_note=product.moderation_note,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


async def products_out(session: AsyncSession, rows: Sequence[tuple[Product, Store]]) -> list[ProductOut]:
    inventory = await _inventory_map(session, [p.id for p, _ in rows])
    return [product_out(p, s, inventory) for p, s in rows]


def service_out(service: Service, store: Store) -> ServiceOut:
    return ServiceOut(
        id=service.id,
        merchant_id=service.merchant_id,
        store=store_summary(store),
        category_id=service.category_id,
        title=service.title,
        slug=service.slug,
        description=service.description,
        price=service.price,
        discounted_price=service.discounted_price,
        duration_minutes=service.duration_minutes,
        availability=service.availability,
        location_type=service.location_type,
        location=service.location,
        status=service.status,
        images=[ImageOut.model_validate(i) for i in service.images],
        is_featured=service.is_featured,
        moderation_note=service.moderation_note,
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


# -- public search ---------------------------------------------------------------------


async def public_products_query(
    session: AsyncSession,
    *,
    q: str | None = None,
    category_slug: str | None = None,
    store_slug: str | None = None,
    city: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    featured: bool | None = None,
    sort: str = "newest",
) -> Select[Product, Store]:
    stmt = (
        select(Product, Store)
        .join(Store, col(Store.id) == col(Product.store_id))
        .join(Merchant, col(Merchant.id) == col(Product.merchant_id))
        .where(Product.status == CatalogStatus.ACTIVE.value, *public_store_conditions())
    )
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(col(Product.title).ilike(pattern), col(Product.description).ilike(pattern)))
    if category_slug:
        category = await resolve_category_slug(session, category_slug)
        stmt = stmt.where(col(Product.category_id).in_(await category_with_descendants(session, category.id)))
    if store_slug:
        stmt = stmt.where(Store.slug == store_slug)
    if city:
        stmt = stmt.where(func.lower(Store.city) == city.strip().lower())
    effective = func.coalesce(Product.discounted_price, Product.price)
    if min_price is not None:
        stmt = stmt.where(effective >= min_price)
    if max_price is not None:
        stmt = stmt.where(effective <= max_price)
    if featured is not None:
        stmt = stmt.where(col(Product.is_featured).is_(featured))
    order_options: dict[str, ColumnElement[Any]] = {
        "newest": col(Product.created_at).desc(),
        "price_asc": effective.asc(),
        "price_desc": effective.desc(),
        "popular": col(Store.orders_count).desc(),
    }
    order = order_options.get(sort, col(Product.created_at).desc())
    return stmt.order_by(order, col(Product.id))


async def public_services_query(
    session: AsyncSession,
    *,
    q: str | None = None,
    category_slug: str | None = None,
    store_slug: str | None = None,
    city: str | None = None,
    featured: bool | None = None,
    sort: str = "newest",
) -> Select[Service, Store]:
    stmt = (
        select(Service, Store)
        .join(Store, col(Store.id) == col(Service.store_id))
        .join(Merchant, col(Merchant.id) == col(Service.merchant_id))
        .where(Service.status == CatalogStatus.ACTIVE.value, *public_store_conditions())
    )
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(col(Service.title).ilike(pattern), col(Service.description).ilike(pattern)))
    if category_slug:
        category = await resolve_category_slug(session, category_slug)
        stmt = stmt.where(col(Service.category_id).in_(await category_with_descendants(session, category.id)))
    if store_slug:
        stmt = stmt.where(Store.slug == store_slug)
    if city:
        stmt = stmt.where(func.lower(Store.city) == city.strip().lower())
    if featured is not None:
        stmt = stmt.where(col(Service.is_featured).is_(featured))
    effective = func.coalesce(Service.discounted_price, Service.price)
    order_options: dict[str, ColumnElement[Any]] = {
        "newest": col(Service.created_at).desc(),
        "price_asc": effective.asc(),
        "price_desc": effective.desc(),
        "popular": col(Store.orders_count).desc(),
    }
    order = order_options.get(sort, col(Service.created_at).desc())
    return stmt.order_by(order, col(Service.id))


async def get_public_product(session: AsyncSession, product_id: uuid.UUID) -> ProductOut:
    row = (
        await session.exec(
            select(Product, Store)
            .join(Store, col(Store.id) == col(Product.store_id))
            .join(Merchant, col(Merchant.id) == col(Product.merchant_id))
            .where(Product.id == product_id, Product.status == CatalogStatus.ACTIVE.value, *public_store_conditions())
        )
    ).first()
    if row is None:
        raise NotFound("Product not found.")
    return (await products_out(session, [(row[0], row[1])]))[0]


async def get_public_service(session: AsyncSession, service_id: uuid.UUID) -> ServiceOut:
    row = (
        await session.exec(
            select(Service, Store)
            .join(Store, col(Store.id) == col(Service.store_id))
            .join(Merchant, col(Merchant.id) == col(Service.merchant_id))
            .where(Service.id == service_id, Service.status == CatalogStatus.ACTIVE.value, *public_store_conditions())
        )
    ).first()
    if row is None:
        raise NotFound("Service not found.")
    return service_out(row[0], row[1])


# -- merchant product management ------------------------------------------------------


async def get_merchant_product(session: AsyncSession, merchant_id: uuid.UUID, product_id: uuid.UUID) -> Product:
    product = await session.get(Product, product_id)
    if product is None or product.merchant_id != merchant_id:
        raise NotFound("Product not found.")  # never reveal other merchants' products
    return product


def _set_images(target: Product | Service, images: list[ImageIn]) -> None:
    if isinstance(target, Product):
        target.images = [
            ProductImage(product_id=target.id, url=image.url, alt=image.alt, sort_order=index)
            for index, image in enumerate(images)
        ]
    else:
        target.images = [
            ServiceImage(service_id=target.id, url=image.url, alt=image.alt, sort_order=index)
            for index, image in enumerate(images)
        ]


async def _sync_variants(session: AsyncSession, product: Product, variants: list[VariantIn]) -> None:
    existing = {v.id: v for v in product.variants}
    seen: set[uuid.UUID] = set()
    for data in variants:
        variant = existing.get(data.id) if data.id else None
        if data.id and variant is None:
            raise ValidationFailed("Unknown variant id.", code="invalid_variant")
        if variant is None:
            variant = ProductVariant(product_id=product.id, sku=data.sku, name=data.name)
            product.variants.append(variant)
        variant.sku = data.sku
        variant.name = data.name
        variant.options = data.options
        variant.price = data.price
        variant.discounted_price = data.discounted_price
        variant.is_active = data.is_active
        await session.flush()
        seen.add(variant.id)
        inv = (await session.exec(select(Inventory).where(Inventory.variant_id == variant.id))).first()
        if inv is None:
            session.add(Inventory(product_id=product.id, variant_id=variant.id, quantity_on_hand=data.stock_quantity))
        elif data.stock_quantity < inv.quantity_reserved:
            raise ValidationFailed("Stock cannot be lower than the reserved quantity.", code="stock_below_reserved")
        else:
            inv.quantity_on_hand = data.stock_quantity
    # Variants removed from the list are deactivated, not deleted (orders may reference them).
    for variant_id, variant in existing.items():
        if variant_id not in seen:
            variant.is_active = False


async def create_product(session: AsyncSession, merchant: Merchant, store: Store, data: ProductIn) -> Product:
    await _validate_category(session, data.category_id, "PRODUCT")
    product = Product(
        merchant_id=merchant.id,
        store_id=store.id,
        category_id=data.category_id,
        title=data.title,
        slug=slugify(data.title),
        description=data.description,
        sku=data.sku,
        price=data.price,
        discounted_price=data.discounted_price,
        status=data.status,
        is_available=data.is_available,
        requires_shipping=data.requires_shipping,
        weight_grams=data.weight_grams,
        images=[],
        variants=[],
    )
    session.add(product)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("A product with this SKU already exists.", code="sku_taken") from exc
    _set_images(product, data.images)
    if data.variants:
        await _sync_variants(session, product, data.variants)
    else:
        session.add(Inventory(product_id=product.id, variant_id=None, quantity_on_hand=data.stock_quantity))
    await session.flush()
    return product


async def update_product(session: AsyncSession, product: Product, data: ProductUpdate) -> Product:
    if product.status == CatalogStatus.BLOCKED.value and data.status is not None:
        raise PermissionDenied("This product was blocked by moderation.", code="product_blocked")
    values = data.model_dump(exclude_unset=True, exclude={"images", "variants", "clear_discount"})
    if "category_id" in values:
        await _validate_category(session, values["category_id"], "PRODUCT")
    for key, value in values.items():
        if value is not None or key == "category_id":
            setattr(product, key, value)
    if data.clear_discount:
        product.discounted_price = None
    if product.discounted_price is not None and product.discounted_price >= product.price:
        raise ValidationFailed("discounted_price must be lower than price.", code="invalid_discount")
    if data.images is not None:
        _set_images(product, data.images)
    if data.variants is not None:
        await _sync_variants(session, product, data.variants)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("A product with this SKU already exists.", code="sku_taken") from exc
    return product


async def archive_product(session: AsyncSession, product: Product) -> None:
    """Products are archived (not deleted) because orders reference them."""
    product.status = CatalogStatus.ARCHIVED.value
    await session.flush()


async def list_inventory(session: AsyncSession, merchant_id: uuid.UUID) -> list[InventoryOut]:
    rows = (
        await session.exec(
            select(Inventory, Product, ProductVariant)
            .join(Product, col(Product.id) == col(Inventory.product_id))
            .outerjoin(ProductVariant, col(ProductVariant.id) == col(Inventory.variant_id))
            .where(Product.merchant_id == merchant_id, Product.status != CatalogStatus.ARCHIVED.value)
            .order_by(Product.title, ProductVariant.name)
        )
    ).all()
    return [
        InventoryOut(
            id=inv.id,
            product_id=product.id,
            product_title=product.title,
            variant_id=variant.id if variant else None,
            variant_name=variant.name if variant else None,
            sku=variant.sku if variant else product.sku,
            quantity_on_hand=inv.quantity_on_hand,
            quantity_reserved=inv.quantity_reserved,
            available=inv.available,
        )
        for inv, product, variant in rows
    ]


async def adjust_inventory(
    session: AsyncSession, merchant_id: uuid.UUID, inventory_id: uuid.UUID, data: InventoryAdjust
) -> Inventory:
    row = (
        await session.exec(
            select(Inventory, Product)
            .join(Product, col(Product.id) == col(Inventory.product_id))
            .where(Inventory.id == inventory_id)
            .with_for_update(of=Inventory)
        )
    ).first()
    if row is None or row[1].merchant_id != merchant_id:
        raise NotFound("Inventory record not found.")
    inv = row[0]
    target = data.quantity_on_hand if data.quantity_on_hand is not None else inv.quantity_on_hand + (data.delta or 0)
    if target < inv.quantity_reserved:
        raise ValidationFailed("Stock cannot be lower than the reserved quantity.", code="stock_below_reserved")
    inv.quantity_on_hand = target
    await session.flush()
    return inv


# -- merchant service management -------------------------------------------------------


async def get_merchant_service(session: AsyncSession, merchant_id: uuid.UUID, service_id: uuid.UUID) -> Service:
    service = await session.get(Service, service_id)
    if service is None or service.merchant_id != merchant_id:
        raise NotFound("Service not found.")
    return service


async def create_service(session: AsyncSession, merchant: Merchant, store: Store, data: ServiceIn) -> Service:
    await _validate_category(session, data.category_id, "SERVICE")
    service = Service(
        merchant_id=merchant.id,
        store_id=store.id,
        category_id=data.category_id,
        title=data.title,
        slug=slugify(data.title),
        description=data.description,
        price=data.price,
        discounted_price=data.discounted_price,
        duration_minutes=data.duration_minutes,
        availability=data.availability.value,
        location_type=data.location_type.value,
        location=data.location,
        status=data.status,
        images=[],
    )
    session.add(service)
    await session.flush()
    _set_images(service, data.images)
    await session.flush()
    return service


async def update_service(session: AsyncSession, service: Service, data: ServiceUpdate) -> Service:
    if service.status == CatalogStatus.BLOCKED.value and data.status is not None:
        raise PermissionDenied("This service was blocked by moderation.", code="service_blocked")
    values = data.model_dump(exclude_unset=True, exclude={"images", "clear_discount"})
    if "category_id" in values:
        await _validate_category(session, values["category_id"], "SERVICE")
    for key, value in values.items():
        if value is None and key != "category_id":
            continue
        setattr(service, key, value.value if hasattr(value, "value") else value)
    if data.clear_discount:
        service.discounted_price = None
    if service.discounted_price is not None and service.discounted_price >= service.price:
        raise ValidationFailed("discounted_price must be lower than price.", code="invalid_discount")
    if data.images is not None:
        _set_images(service, data.images)
    await session.flush()
    return service


# -- reviews -------------------------------------------------------------------------------


async def recalculate_store_rating(session: AsyncSession, store_id: uuid.UUID) -> None:
    avg, count = (
        await session.exec(
            select(func.avg(col(Review.rating)), func.count(col(Review.id))).where(
                Review.store_id == store_id, Review.status == ReviewStatus.PUBLISHED.value
            )
        )
    ).one()
    store = await session.get(Store, store_id)
    if store is not None:
        store.rating_avg = Decimal(avg or 0).quantize(Decimal("0.01"))
        store.rating_count = int(count)


def published_reviews_query(store_id: uuid.UUID) -> Select[Review, str]:
    from app.modules.auth.models import User

    return (
        select(Review, User.full_name)
        .join(User, col(User.id) == col(Review.customer_user_id))
        .where(and_(Review.store_id == store_id, Review.status == ReviewStatus.PUBLISHED.value))
        .order_by(col(Review.created_at).desc())
    )
