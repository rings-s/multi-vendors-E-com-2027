"""/api/v1/merchant/* — the merchant dashboard API.

Every query is scoped to the authenticated merchant (``CurrentMerchant``); ids in
paths are always checked against that merchant, so one merchant can never read or
change another merchant's data.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, ConfigDict
from sqlmodel import col, delete, distinct, func, select
from sqlmodel.sql.expression import Select

from app.api.deps import CurrentMerchant
from app.core.errors import Conflict, NotFound
from app.core.pagination import Page, PageDep, paginate
from app.core.security import utcnow
from app.database.session import DbSession
from app.integrations.payments.factory import ProviderDep
from app.modules.admin.settings_service import DeliveryFinanceSettings, PaymentSettings, get_setting
from app.modules.analytics import service as analytics
from app.modules.analytics.schemas import Analytics
from app.modules.auth.models import User
from app.modules.catalog import service as catalog
from app.modules.catalog.models import CatalogStatus, Category, Product, Service
from app.modules.catalog.schemas import (
    InventoryAdjust,
    InventoryOut,
    ProductIn,
    ProductOut,
    ProductUpdate,
    ServiceIn,
    ServiceOut,
    ServiceUpdate,
)
from app.modules.commissions.models import CommissionRule, CommissionTransaction
from app.modules.commissions.service import resolve_rule
from app.modules.ledger.models import LedgerAccount, LedgerEntry, LedgerTransaction
from app.modules.merchants import finance
from app.modules.merchants.models import MerchantAddress
from app.modules.merchants.service import get_store
from app.modules.orders import service as orders
from app.modules.orders.models import MerchantOrder, MerchantOrderStatus
from app.modules.orders.schemas import (
    CancellationDecision,
    FulfillmentUpdate,
    MerchantOrderMerchantView,
    RejectOrder,
)
from app.modules.orders.views import merchant_views
from app.modules.payments import refunds
from app.modules.payments.models import Refund, RefundInitiator, RefundScope, RefundStatus
from app.modules.payments.schemas import RefundCreate, RefundDecision, RefundOut
from app.modules.settlements.models import Settlement
from app.modules.stores.models import Store, StoreCategory
from app.modules.stores.router import store_out
from app.modules.stores.schemas import LocationIn, LocationOut, StoreOut, StoreUpdate

router = APIRouter(prefix="/merchant", tags=["merchant"])


async def _store(db: DbSession, ctx: CurrentMerchant) -> Store:
    store = await get_store(db, ctx.merchant_id)
    if store is None:
        raise NotFound("Store not found.")
    return store


# -- dashboard ----------------------------------------------------------------------


class RecentTransaction(BaseModel):
    id: uuid.UUID
    transaction_type: str
    direction: str
    amount: int
    description: str
    is_test: bool
    created_at: datetime


class DashboardOut(BaseModel):
    summary: finance.FinancialSummary
    orders_today: int
    total_orders: int
    open_orders: int
    recent_transactions: list[RecentTransaction]
    sales_chart: list[finance.DailyPoint]


async def _transactions_query(merchant_id: uuid.UUID) -> Select[LedgerEntry, LedgerTransaction]:
    return (
        select(LedgerEntry, LedgerTransaction)
        .join(LedgerTransaction, col(LedgerTransaction.id) == col(LedgerEntry.transaction_id))
        .join(LedgerAccount, col(LedgerAccount.id) == col(LedgerEntry.account_id))
        .where(LedgerAccount.merchant_id == merchant_id)
        .order_by(col(LedgerEntry.created_at).desc(), col(LedgerEntry.id))
    )


def _tx_out(entry: LedgerEntry, tx: LedgerTransaction) -> RecentTransaction:
    return RecentTransaction(
        id=entry.id,
        transaction_type=tx.transaction_type,
        direction=entry.direction,
        amount=entry.amount,
        description=tx.description,
        is_test=tx.is_test,
        created_at=entry.created_at,
    )


@router.get("/dashboard")
async def dashboard(ctx: CurrentMerchant, db: DbSession) -> DashboardOut:
    fee_bearer = (await get_setting(db, "payments", PaymentSettings)).fee_bearer
    total_orders = (
        await db.exec(
            select(func.count(col(MerchantOrder.id))).where(
                col(MerchantOrder.merchant_id) == ctx.merchant_id, col(MerchantOrder.paid_at).is_not(None)
            )
        )
    ).first()
    open_orders = (
        await db.exec(
            select(func.count(col(MerchantOrder.id))).where(
                MerchantOrder.merchant_id == ctx.merchant_id,
                col(MerchantOrder.status).in_(
                    [
                        s.value
                        for s in (
                            MerchantOrderStatus.PAID,
                            MerchantOrderStatus.ACCEPTED,
                            MerchantOrderStatus.PROCESSING,
                        )
                    ]
                ),
            )
        )
    ).first()
    recent = (await db.exec((await _transactions_query(ctx.merchant_id)).limit(10))).all()
    return DashboardOut(
        summary=await finance.summary(
            db, ctx.merchant_id, fee_bearer, await get_setting(db, "delivery", DeliveryFinanceSettings)
        ),
        orders_today=await orders.count_orders_today(db, ctx.merchant_id),
        total_orders=int(total_orders or 0),
        open_orders=int(open_orders or 0),
        recent_transactions=[_tx_out(e, t) for e, t in recent],
        sales_chart=await finance.daily_sales(db, ctx.merchant_id),
    )


@router.get("/analytics")
async def analytics_for_merchant(
    ctx: CurrentMerchant,
    db: DbSession,
    days: Annotated[int, Query(ge=7, le=365, description="Length of the period in days, ending today.")] = 30,
) -> Analytics:
    """Charts for the dashboard, scoped to the signed-in merchant."""
    return await analytics.build(db, ctx.merchant_id, days)


# -- store ----------------------------------------------------------------------------


@router.get("/store")
async def get_my_store(ctx: CurrentMerchant, db: DbSession) -> StoreOut:
    return await store_out(db, await _store(db, ctx))


@router.patch("/store")
async def update_my_store(body: StoreUpdate, ctx: CurrentMerchant, db: DbSession) -> StoreOut:
    store = await _store(db, ctx)
    values = body.model_dump(exclude_unset=True, exclude={"category_ids"})
    for key, value in values.items():
        if value is not None:
            setattr(store, key, value)
    if body.category_ids is not None:
        valid = set(
            (
                await db.exec(
                    select(col(Category.id)).where(
                        col(Category.id).in_(body.category_ids), col(Category.is_active).is_(True)
                    )
                )
            ).all()
        )
        if valid != set(body.category_ids):
            raise NotFound("Unknown category.")
        await db.exec(delete(StoreCategory).where(col(StoreCategory.store_id) == store.id))
        db.add_all([StoreCategory(store_id=store.id, category_id=category_id) for category_id in valid])
    await db.flush()
    return await store_out(db, store)


@router.get("/store/locations")
async def list_locations(ctx: CurrentMerchant, db: DbSession) -> list[LocationOut]:
    rows = await db.exec(
        select(MerchantAddress)
        .where(MerchantAddress.merchant_id == ctx.merchant_id)
        .order_by(col(MerchantAddress.created_at))
    )
    return [LocationOut.model_validate(r) for r in rows.all()]


@router.post("/store/locations", status_code=status.HTTP_201_CREATED)
async def add_location(body: LocationIn, ctx: CurrentMerchant, db: DbSession) -> LocationOut:
    location = MerchantAddress(merchant_id=ctx.merchant_id, is_primary=False, **body.model_dump())
    db.add(location)
    await db.flush()
    return LocationOut.model_validate(location)


async def _location(db: DbSession, ctx: CurrentMerchant, location_id: uuid.UUID) -> MerchantAddress:
    location = await db.get(MerchantAddress, location_id)
    if location is None or location.merchant_id != ctx.merchant_id:
        raise NotFound("Location not found.")
    return location


@router.put("/store/locations/{location_id}")
async def update_location(location_id: uuid.UUID, body: LocationIn, ctx: CurrentMerchant, db: DbSession) -> LocationOut:
    location = await _location(db, ctx, location_id)
    for key, value in body.model_dump().items():
        setattr(location, key, value)
    await db.flush()
    return LocationOut.model_validate(location)


@router.delete("/store/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(location_id: uuid.UUID, ctx: CurrentMerchant, db: DbSession) -> None:
    location = await _location(db, ctx, location_id)
    if location.is_primary:
        raise Conflict("The primary business address cannot be removed.", code="primary_location")
    await db.delete(location)


# -- products & inventory ---------------------------------------------------------------


@router.get("/products")
async def list_products(
    ctx: CurrentMerchant,
    db: DbSession,
    page: PageDep,
    status_filter: Annotated[Literal["DRAFT", "ACTIVE", "ARCHIVED", "BLOCKED"] | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[ProductOut]:
    store = await _store(db, ctx)
    stmt = select(Product).where(col(Product.merchant_id) == ctx.merchant_id).order_by(col(Product.created_at).desc())
    if status_filter:
        stmt = stmt.where(Product.status == status_filter)
    if q:
        stmt = stmt.where(col(Product.title).ilike(f"%{q}%") | col(Product.sku).ilike(f"%{q}%"))
    rows, total = await paginate(db, stmt, page)
    return Page(
        items=await catalog.products_out(db, [(p, store) for p in rows]),
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.post("/products", status_code=status.HTTP_201_CREATED)
async def create_product(body: ProductIn, ctx: CurrentMerchant, db: DbSession) -> ProductOut:
    store = await _store(db, ctx)
    product = await catalog.create_product(db, ctx.merchant, store, body)
    await db.refresh(product, ["images", "variants"])
    return (await catalog.products_out(db, [(product, store)]))[0]


@router.get("/products/{product_id}")
async def get_product(product_id: uuid.UUID, ctx: CurrentMerchant, db: DbSession) -> ProductOut:
    store = await _store(db, ctx)
    product = await catalog.get_merchant_product(db, ctx.merchant_id, product_id)
    return (await catalog.products_out(db, [(product, store)]))[0]


@router.patch("/products/{product_id}")
async def update_product(product_id: uuid.UUID, body: ProductUpdate, ctx: CurrentMerchant, db: DbSession) -> ProductOut:
    store = await _store(db, ctx)
    product = await catalog.get_merchant_product(db, ctx.merchant_id, product_id)
    await catalog.update_product(db, product, body)
    await db.refresh(product, ["images", "variants"])
    return (await catalog.products_out(db, [(product, store)]))[0]


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_product(product_id: uuid.UUID, ctx: CurrentMerchant, db: DbSession) -> None:
    await catalog.archive_product(db, await catalog.get_merchant_product(db, ctx.merchant_id, product_id))


@router.get("/inventory")
async def list_inventory(ctx: CurrentMerchant, db: DbSession) -> list[InventoryOut]:
    return await catalog.list_inventory(db, ctx.merchant_id)


@router.patch("/inventory/{inventory_id}")
async def adjust_inventory(
    inventory_id: uuid.UUID, body: InventoryAdjust, ctx: CurrentMerchant, db: DbSession
) -> list[InventoryOut]:
    await catalog.adjust_inventory(db, ctx.merchant_id, inventory_id, body)
    return await catalog.list_inventory(db, ctx.merchant_id)


# -- services ---------------------------------------------------------------------------


@router.get("/services")
async def list_services(ctx: CurrentMerchant, db: DbSession, page: PageDep) -> Page[ServiceOut]:
    store = await _store(db, ctx)
    stmt = select(Service).where(col(Service.merchant_id) == ctx.merchant_id).order_by(col(Service.created_at).desc())
    rows, total = await paginate(db, stmt, page)
    return Page(
        items=[catalog.service_out(s, store) for s in rows], total=total, page=page.page, page_size=page.page_size
    )


@router.post("/services", status_code=status.HTTP_201_CREATED)
async def create_service(body: ServiceIn, ctx: CurrentMerchant, db: DbSession) -> ServiceOut:
    store = await _store(db, ctx)
    service = await catalog.create_service(db, ctx.merchant, store, body)
    await db.refresh(service, ["images"])
    return catalog.service_out(service, store)


@router.get("/services/{service_id}")
async def get_service(service_id: uuid.UUID, ctx: CurrentMerchant, db: DbSession) -> ServiceOut:
    store = await _store(db, ctx)
    return catalog.service_out(await catalog.get_merchant_service(db, ctx.merchant_id, service_id), store)


@router.patch("/services/{service_id}")
async def update_service(service_id: uuid.UUID, body: ServiceUpdate, ctx: CurrentMerchant, db: DbSession) -> ServiceOut:
    store = await _store(db, ctx)
    service = await catalog.get_merchant_service(db, ctx.merchant_id, service_id)
    await catalog.update_service(db, service, body)
    await db.refresh(service, ["images"])
    return catalog.service_out(service, store)


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_service(service_id: uuid.UUID, ctx: CurrentMerchant, db: DbSession) -> None:
    service = await catalog.get_merchant_service(db, ctx.merchant_id, service_id)
    service.status = CatalogStatus.ARCHIVED.value


# -- orders -----------------------------------------------------------------------------


@router.get("/orders")
async def list_orders(
    ctx: CurrentMerchant,
    db: DbSession,
    page: PageDep,
    status_filter: Annotated[MerchantOrderStatus | None, Query(alias="status")] = None,
    include_unpaid: bool = False,
) -> Page[MerchantOrderMerchantView]:
    stmt = (
        select(MerchantOrder)
        .where(MerchantOrder.merchant_id == ctx.merchant_id)
        .order_by(col(MerchantOrder.created_at).desc())
    )
    if status_filter:
        stmt = stmt.where(MerchantOrder.status == status_filter.value)
    elif not include_unpaid:
        stmt = stmt.where(col(MerchantOrder.paid_at).is_not(None))
    rows, total = await paginate(db, stmt, page)
    return Page(items=await merchant_views(db, rows), total=total, page=page.page, page_size=page.page_size)


@router.get("/orders/{mo_id}")
async def get_order(mo_id: uuid.UUID, ctx: CurrentMerchant, db: DbSession) -> MerchantOrderMerchantView:
    mo = await orders.get_merchant_order_for_merchant(db, ctx.merchant_id, mo_id)
    return (await merchant_views(db, [mo]))[0]


@router.post("/orders/{mo_id}/fulfillment")
async def update_fulfillment(
    mo_id: uuid.UUID, body: FulfillmentUpdate, ctx: CurrentMerchant, db: DbSession
) -> MerchantOrderMerchantView:
    mo = await orders.get_merchant_order_for_merchant(db, ctx.merchant_id, mo_id, lock=True)
    await orders.update_fulfillment(db, mo, body, actor_user_id=ctx.auth.user_id)
    return (await merchant_views(db, [mo]))[0]


@router.post("/orders/{mo_id}/reject")
async def reject_order(
    mo_id: uuid.UUID, body: RejectOrder, ctx: CurrentMerchant, db: DbSession, provider: ProviderDep
) -> MerchantOrderMerchantView:
    mo = await orders.get_merchant_order_for_merchant(db, ctx.merchant_id, mo_id, lock=True)
    if mo.status != MerchantOrderStatus.PAID.value:
        raise Conflict("Only new paid orders can be rejected.", code="invalid_transition")
    await orders.cancel_paid_order(
        db,
        mo,
        provider,
        actor_user_id=ctx.auth.user_id,
        initiated_by=RefundInitiator.MERCHANT.value,
        reason=body.reason,
        final_status=MerchantOrderStatus.REJECTED,
    )
    return (await merchant_views(db, [mo]))[0]


@router.post("/orders/{mo_id}/cancel")
async def cancel_order(
    mo_id: uuid.UUID, body: RejectOrder, ctx: CurrentMerchant, db: DbSession, provider: ProviderDep
) -> MerchantOrderMerchantView:
    mo = await orders.get_merchant_order_for_merchant(db, ctx.merchant_id, mo_id, lock=True)
    await orders.cancel_paid_order(
        db,
        mo,
        provider,
        actor_user_id=ctx.auth.user_id,
        initiated_by=RefundInitiator.MERCHANT.value,
        reason=body.reason,
    )
    return (await merchant_views(db, [mo]))[0]


@router.post("/orders/{mo_id}/cancellation-decision")
async def decide_cancellation(
    mo_id: uuid.UUID, body: CancellationDecision, ctx: CurrentMerchant, db: DbSession, provider: ProviderDep
) -> MerchantOrderMerchantView:
    mo = await orders.get_merchant_order_for_merchant(db, ctx.merchant_id, mo_id, lock=True)
    await orders.decide_cancellation(
        db,
        mo,
        provider,
        approve=body.approve,
        actor_user_id=ctx.auth.user_id,
        initiated_by=RefundInitiator.MERCHANT.value,
        note=body.note,
    )
    return (await merchant_views(db, [mo]))[0]


@router.post("/orders/{mo_id}/refunds", status_code=status.HTTP_201_CREATED)
async def refund_order(
    mo_id: uuid.UUID, body: RefundCreate, ctx: CurrentMerchant, db: DbSession, provider: ProviderDep
) -> RefundOut:
    mo = await orders.get_merchant_order_for_merchant(db, ctx.merchant_id, mo_id, lock=True)
    payment = await orders.captured_payment(db, mo.id, lock=True)
    if payment is None:
        raise Conflict("This order has no captured payment.", code="no_payment")
    refund = await refunds.create_and_process(
        db,
        payment,
        provider,
        amount=body.amount,
        initiated_by=RefundInitiator.MERCHANT,
        actor_user_id=ctx.auth.user_id,
        reason=body.reason,
        restock=body.restock,
        scope=RefundScope(body.scope),
    )
    return RefundOut.model_validate(refund)


# -- customers ----------------------------------------------------------------------------


class MerchantCustomerOut(BaseModel):
    customer_id: uuid.UUID
    name: str
    orders: int
    total_spent: int
    last_order_at: datetime


@router.get("/customers")
async def list_customers(ctx: CurrentMerchant, db: DbSession, page: PageDep) -> Page[MerchantCustomerOut]:
    last_paid = func.max(col(MerchantOrder.paid_at))
    stmt = (
        select(
            col(MerchantOrder.customer_user_id),
            func.count(col(MerchantOrder.id)),
            func.coalesce(func.sum(col(MerchantOrder.total)), 0),
            last_paid,
        )
        .where(MerchantOrder.merchant_id == ctx.merchant_id, col(MerchantOrder.paid_at).is_not(None))
        .group_by(col(MerchantOrder.customer_user_id))
        .order_by(last_paid.desc(), col(MerchantOrder.customer_user_id))
    )
    total = (
        await db.exec(
            select(func.count(distinct(MerchantOrder.customer_user_id))).where(
                col(MerchantOrder.merchant_id) == ctx.merchant_id, col(MerchantOrder.paid_at).is_not(None)
            )
        )
    ).first()
    rows = (await db.exec(stmt.limit(page.page_size).offset(page.offset))).all()
    customer_ids = [r[0] for r in rows]
    names = (
        {u.id: u.full_name for u in (await db.exec(select(User).where(col(User.id).in_(customer_ids)))).all()}
        if customer_ids
        else {}
    )
    items = [
        MerchantCustomerOut(
            customer_id=r[0], name=names.get(r[0], ""), orders=int(r[1]), total_spent=int(r[2]), last_order_at=r[3]
        )
        for r in rows
    ]
    return Page(items=items, total=int(total or 0), page=page.page, page_size=page.page_size)


# -- finance ------------------------------------------------------------------------------


@router.get("/transactions")
async def transactions(ctx: CurrentMerchant, db: DbSession, page: PageDep) -> Page[RecentTransaction]:
    stmt = await _transactions_query(ctx.merchant_id)
    total = (
        await db.exec(
            select(func.count(col(LedgerEntry.id)))
            .join(LedgerAccount, col(LedgerAccount.id) == col(LedgerEntry.account_id))
            .where(LedgerAccount.merchant_id == ctx.merchant_id)
        )
    ).first()
    rows = (await db.exec(stmt.limit(page.page_size).offset(page.offset))).all()
    return Page(items=[_tx_out(e, t) for e, t in rows], total=int(total or 0), page=page.page, page_size=page.page_size)


class EarningsOut(BaseModel):
    summary: finance.FinancialSummary
    daily: list[finance.DailyPoint]


@router.get("/earnings")
async def earnings(ctx: CurrentMerchant, db: DbSession, days: Annotated[int, Query(ge=7, le=365)] = 30) -> EarningsOut:
    fee_bearer = (await get_setting(db, "payments", PaymentSettings)).fee_bearer
    return EarningsOut(
        summary=await finance.summary(
            db, ctx.merchant_id, fee_bearer, await get_setting(db, "delivery", DeliveryFinanceSettings)
        ),
        daily=await finance.daily_sales(db, ctx.merchant_id, days),
    )


class CommissionTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_order_id: uuid.UUID
    gross_amount: int
    commission_base: int
    commission_rate: Decimal
    commission_amount: int
    processing_fee: int | None
    fee_bearer: str
    seller_net_amount: int
    created_at: datetime


class CommissionRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope: str
    rate_type: str
    rate: Decimal | None
    fixed_amount: int | None
    effective_from: datetime
    effective_to: datetime | None


class CommissionsOut(BaseModel):
    current_rule: CommissionRuleOut
    merchant_rules: list[CommissionRuleOut]
    transactions: Page[CommissionTransactionOut]


@router.get("/commissions")
async def commissions(ctx: CurrentMerchant, db: DbSession, page: PageDep) -> CommissionsOut:
    current = await resolve_rule(db, merchant_id=ctx.merchant_id, category_id=None, at=utcnow())
    rules = (
        await db.exec(
            select(CommissionRule)
            .where(CommissionRule.merchant_id == ctx.merchant_id)
            .order_by(col(CommissionRule.effective_from).desc())
        )
    ).all()
    stmt = (
        select(CommissionTransaction)
        .where(CommissionTransaction.merchant_id == ctx.merchant_id)
        .order_by(col(CommissionTransaction.created_at).desc())
    )
    rows, total = await paginate(db, stmt, page)
    return CommissionsOut(
        current_rule=CommissionRuleOut.model_validate(current),
        merchant_rules=[CommissionRuleOut.model_validate(r) for r in rules],
        transactions=Page(
            items=[CommissionTransactionOut.model_validate(r) for r in rows],
            total=total,
            page=page.page,
            page_size=page.page_size,
        ),
    )


class SettlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    provider_settlement_id: str
    amount: int
    currency: str
    status: str
    is_test: bool
    initiated_at: datetime | None
    completed_at: datetime | None
    failure_reason: str | None
    confirmation_source: str | None


@router.get("/settlements")
async def settlements(ctx: CurrentMerchant, db: DbSession, page: PageDep) -> Page[SettlementOut]:
    stmt = (
        select(Settlement)
        .where(col(Settlement.merchant_id) == ctx.merchant_id)
        .order_by(col(Settlement.created_at).desc())
    )
    rows, total = await paginate(db, stmt, page)
    return Page(
        items=[SettlementOut.model_validate(s) for s in rows], total=total, page=page.page, page_size=page.page_size
    )


@router.get("/refunds")
async def list_refunds(
    ctx: CurrentMerchant,
    db: DbSession,
    page: PageDep,
    status_filter: Annotated[RefundStatus | None, Query(alias="status")] = None,
) -> Page[RefundOut]:
    stmt = select(Refund).where(col(Refund.merchant_id) == ctx.merchant_id).order_by(col(Refund.created_at).desc())
    if status_filter:
        stmt = stmt.where(Refund.status == status_filter.value)
    rows, total = await paginate(db, stmt, page)
    return Page(
        items=[RefundOut.model_validate(r) for r in rows], total=total, page=page.page, page_size=page.page_size
    )


@router.post("/refunds/{refund_id}/decision")
async def decide_refund(
    refund_id: uuid.UUID, body: RefundDecision, ctx: CurrentMerchant, db: DbSession, provider: ProviderDep
) -> RefundOut:
    refund = await db.get(Refund, refund_id, with_for_update=True)
    if refund is None or refund.merchant_id != ctx.merchant_id:
        raise NotFound("Refund not found.")
    if body.approve:
        refund = await refunds.process_refund(db, refund, provider, reviewer_id=ctx.auth.user_id)
    else:
        refund = await refunds.reject_refund(db, refund, reviewer_id=ctx.auth.user_id, note=body.note)
    return RefundOut.model_validate(refund)
