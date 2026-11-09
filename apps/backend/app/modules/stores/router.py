"""Public discovery: /api/v1/stores, /categories, /products, /services, /homepage."""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import ColumnElement
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import Select

from app.core.errors import NotFound
from app.core.pagination import Page, PageDep, PageParams, paginate
from app.database.session import DbSession
from app.infrastructure.redis import cache_get, cache_set
from app.modules.admin.settings_service import HomepageSettings, get_setting
from app.modules.catalog import service as catalog
from app.modules.catalog.models import Product, Service
from app.modules.catalog.schemas import CategoryOut, ProductOut, ReviewOut, ServiceOut
from app.modules.delivery.models import DeliveryMethod
from app.modules.merchants.models import Merchant, MerchantAddress
from app.modules.stores.models import Store, StoreCategory
from app.modules.stores.schemas import PublicLocationOut, StoreOut

stores_router = APIRouter(prefix="/stores", tags=["stores"])
categories_router = APIRouter(prefix="/categories", tags=["categories"])
products_router = APIRouter(prefix="/products", tags=["products"])
services_router = APIRouter(prefix="/services", tags=["services"])
homepage_router = APIRouter(prefix="/homepage", tags=["homepage"])

StoreSort = Literal["popular", "newest", "rating"]
ItemSort = Literal["newest", "price_asc", "price_desc", "popular"]


async def store_out(session: AsyncSession, store: Store) -> StoreOut:
    category_ids = (
        await session.exec(select(StoreCategory.category_id).where(StoreCategory.store_id == store.id))
    ).all()
    out = StoreOut.model_validate(store)
    out.category_ids = list(category_ids)
    return out


async def _public_store(session: AsyncSession, slug: str) -> Store:
    store = (
        await session.exec(
            select(Store)
            .join(Merchant, col(Merchant.id) == col(Store.merchant_id))
            .where(Store.slug == slug, *catalog.public_store_conditions())
        )
    ).first()
    if store is None:
        raise NotFound("Store not found.")
    return store


@stores_router.get("")
async def list_stores(
    db: DbSession,
    page: PageDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    city: Annotated[str | None, Query(max_length=100)] = None,
    min_rating: Annotated[float | None, Query(ge=0, le=5)] = None,
    sort: StoreSort = "popular",
) -> Page[StoreOut]:
    stmt = (
        select(Store)
        .join(Merchant, col(Merchant.id) == col(Store.merchant_id))
        .where(*catalog.public_store_conditions())
    )
    if q:
        stmt = stmt.where(col(Store.name).ilike(f"%{q.strip()}%"))
    if category:
        cat = await catalog.resolve_category_slug(db, category)
        ids = await catalog.category_with_descendants(db, cat.id)
        stmt = stmt.where(
            col(Store.id).in_(select(StoreCategory.store_id).where(col(StoreCategory.category_id).in_(ids)))
        )
    if city:
        stmt = stmt.where(func.lower(Store.city) == city.strip().lower())
    if min_rating is not None:
        stmt = stmt.where(Store.rating_avg >= min_rating)
    order_options: dict[str, ColumnElement[Any]] = {
        "popular": col(Store.orders_count).desc(),
        "newest": col(Store.created_at).desc(),
        "rating": col(Store.rating_avg).desc(),
    }
    order = order_options[sort]
    rows, total = await paginate(db, stmt.order_by(order, col(Store.id)), page)
    return Page(items=[await store_out(db, s) for s in rows], total=total, page=page.page, page_size=page.page_size)


@stores_router.get("/{slug}")
async def get_store(slug: str, db: DbSession) -> StoreOut:
    return await store_out(db, await _public_store(db, slug))


@stores_router.get("/{slug}/locations")
async def store_locations(slug: str, db: DbSession) -> list[PublicLocationOut]:
    """Pickup points only: other merchant addresses (e.g. the registered business address) stay private."""
    store = await _public_store(db, slug)
    rows = (
        await db.exec(
            select(MerchantAddress)
            .where(MerchantAddress.merchant_id == store.merchant_id, col(MerchantAddress.is_pickup_location))
            .order_by(col(MerchantAddress.is_primary).desc(), col(MerchantAddress.created_at))
        )
    ).all()
    return [PublicLocationOut.model_validate(r) for r in rows]


class PublicZoneOut(BaseModel):
    name: str
    region: str | None
    cities: list[str]
    districts: list[str]
    fee: int
    free_delivery_threshold: int | None
    eta_min_minutes: int
    eta_max_minutes: int


class PublicDeliveryOut(BaseModel):
    delivery_offered: bool
    pickup_offered: bool
    pickup_preparation_minutes: int
    delivery_policy: str
    zones: list[PublicZoneOut]


@stores_router.get("/{slug}/delivery")
async def store_delivery(slug: str, db: DbSession) -> PublicDeliveryOut:
    """Where and how a store delivers (fees exclude VAT)."""
    from app.modules.delivery.quoting import load_store_delivery, offered_methods

    store = await _public_store(db, slug)
    data = (await load_store_delivery(db, [store]))[store.id]
    offered = offered_methods(data)
    return PublicDeliveryOut(
        delivery_offered=DeliveryMethod.DELIVERY in offered,
        pickup_offered=DeliveryMethod.PICKUP in offered,
        pickup_preparation_minutes=data.settings.pickup_preparation_minutes,
        delivery_policy=data.settings.delivery_policy,
        zones=[
            PublicZoneOut(
                name=z.name,
                region=z.region,
                cities=z.cities,
                districts=z.districts,
                fee=z.fee,
                free_delivery_threshold=z.free_delivery_threshold,
                eta_min_minutes=z.eta_min_minutes,
                eta_max_minutes=z.eta_max_minutes,
            )
            for z in data.zones
        ]
        if DeliveryMethod.DELIVERY in offered
        else [],
    )


@stores_router.get("/{slug}/products")
async def store_products(slug: str, db: DbSession, page: PageDep, sort: ItemSort = "newest") -> Page[ProductOut]:
    await _public_store(db, slug)
    stmt = await catalog.public_products_query(db, store_slug=slug, sort=sort)
    rows, total = await _paginate_rows(db, stmt, page)
    return Page(items=await catalog.products_out(db, rows), total=total, page=page.page, page_size=page.page_size)


@stores_router.get("/{slug}/services")
async def store_services(slug: str, db: DbSession, page: PageDep, sort: ItemSort = "newest") -> Page[ServiceOut]:
    await _public_store(db, slug)
    stmt = await catalog.public_services_query(db, store_slug=slug, sort=sort)
    rows, total = await _paginate_rows(db, stmt, page)
    return Page(
        items=[catalog.service_out(s, st) for s, st in rows], total=total, page=page.page, page_size=page.page_size
    )


@stores_router.get("/{slug}/reviews")
async def store_reviews(slug: str, db: DbSession, page: PageDep) -> Page[ReviewOut]:
    store = await _public_store(db, slug)
    stmt = catalog.published_reviews_query(store.id)
    rows, total = await _paginate_rows(db, stmt, page)
    items = [
        ReviewOut(
            id=r.id,
            store_id=r.store_id,
            rating=r.rating,
            comment=r.comment,
            customer_name=name.split(" ")[0] if name else "",
            status=r.status,
            created_at=r.created_at,
        )
        for r, name in rows
    ]
    return Page(items=items, total=total, page=page.page, page_size=page.page_size)


async def _paginate_rows(
    db: AsyncSession, stmt: Select[Any, Any], page: PageParams
) -> tuple[list[tuple[Any, Any]], int]:
    total = (await db.exec(select(func.count()).select_from(stmt.order_by(None).subquery()))).first()
    rows = (await db.exec(stmt.limit(page.page_size).offset(page.offset))).all()
    return [(r[0], r[1]) for r in rows], int(total or 0)


@categories_router.get("")
async def list_categories(db: DbSession) -> list[CategoryOut]:
    cached = await cache_get("categories:active")
    if cached is not None:
        return [CategoryOut.model_validate(c) for c in cached]
    categories = await catalog.list_categories(db)
    await cache_set("categories:active", [c.model_dump(mode="json") for c in categories], 300)
    return categories


@categories_router.get("/{slug}")
async def get_category(slug: str, db: DbSession) -> CategoryOut:
    return CategoryOut.model_validate(await catalog.resolve_category_slug(db, slug))


@products_router.get("")
async def search_products(
    db: DbSession,
    page: PageDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    store: Annotated[str | None, Query(max_length=80)] = None,
    city: Annotated[str | None, Query(max_length=100)] = None,
    min_price: Annotated[int | None, Query(ge=0)] = None,
    max_price: Annotated[int | None, Query(ge=0)] = None,
    featured: bool | None = None,
    sort: ItemSort = "newest",
) -> Page[ProductOut]:
    stmt = await catalog.public_products_query(
        db,
        q=q,
        category_slug=category,
        store_slug=store,
        city=city,
        min_price=min_price,
        max_price=max_price,
        featured=featured,
        sort=sort,
    )
    rows, total = await _paginate_rows(db, stmt, page)
    return Page(items=await catalog.products_out(db, rows), total=total, page=page.page, page_size=page.page_size)


@products_router.get("/{product_id}")
async def get_product(product_id: uuid.UUID, db: DbSession) -> ProductOut:
    return await catalog.get_public_product(db, product_id)


@services_router.get("")
async def search_services(
    db: DbSession,
    page: PageDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    store: Annotated[str | None, Query(max_length=80)] = None,
    city: Annotated[str | None, Query(max_length=100)] = None,
    featured: bool | None = None,
    sort: ItemSort = "newest",
) -> Page[ServiceOut]:
    stmt = await catalog.public_services_query(
        db, q=q, category_slug=category, store_slug=store, city=city, featured=featured, sort=sort
    )
    rows, total = await _paginate_rows(db, stmt, page)
    return Page(
        items=[catalog.service_out(s, st) for s, st in rows], total=total, page=page.page, page_size=page.page_size
    )


@services_router.get("/{service_id}")
async def get_service(service_id: uuid.UUID, db: DbSession) -> ServiceOut:
    return await catalog.get_public_service(db, service_id)


class HomepageOut(BaseModel):
    settings: HomepageSettings
    featured_stores: list[StoreOut]
    featured_products: list[ProductOut]
    popular_services: list[ServiceOut]
    recent_stores: list[StoreOut]
    categories: list[CategoryOut]


@homepage_router.get("")
async def homepage(db: DbSession) -> HomepageOut:
    config = await get_setting(db, "homepage", HomepageSettings)
    public = (
        select(Store)
        .join(Merchant, col(Merchant.id) == col(Store.merchant_id))
        .where(*catalog.public_store_conditions())
    )
    featured_stores: list[Store] = []
    if config.featured_store_ids:
        featured_stores = list((await db.exec(public.where(col(Store.id).in_(config.featured_store_ids)))).all())
    if not featured_stores:
        featured_stores = list(
            (await db.exec(public.order_by(col(Store.orders_count).desc(), col(Store.id)).limit(8))).all()
        )
    recent = list((await db.exec(public.order_by(col(Store.created_at).desc()).limit(8))).all())

    products_stmt = await catalog.public_products_query(db, sort="popular")
    if config.featured_product_ids:
        products_stmt = products_stmt.where(col(Product.id).in_(config.featured_product_ids))
    else:
        products_stmt = products_stmt.where(col(Product.is_featured).is_(True))
    product_rows = [tuple(r) for r in (await db.exec(products_stmt.limit(12))).all()]
    if not product_rows:
        product_rows = [tuple(r) for r in (await db.exec((await catalog.public_products_query(db)).limit(12))).all()]

    services_stmt = await catalog.public_services_query(db, sort="popular")
    if config.featured_service_ids:
        services_stmt = services_stmt.where(col(Service.id).in_(config.featured_service_ids))
    service_rows = (await db.exec(services_stmt.limit(8))).all()

    return HomepageOut(
        settings=config,
        featured_stores=[await store_out(db, s) for s in featured_stores],
        featured_products=await catalog.products_out(db, product_rows),  # type: ignore[arg-type]
        popular_services=[catalog.service_out(s, st) for s, st in service_rows],
        recent_stores=[await store_out(db, s) for s in recent],
        categories=await catalog.list_categories(db),
    )
