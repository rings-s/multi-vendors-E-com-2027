"""/api/v1/admin/* — platform administration (permission-gated, audited)."""

import contextlib
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import ColumnElement
from sqlmodel import col, func, or_, select

from app.api.deps import AuthContext, client_ip, require_permission
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import Page, PageDep, paginate
from app.database.session import DbSession
from app.infrastructure.redis import cache_delete
from app.integrations.payments.factory import ProviderDep
from app.modules.admin import settings_service
from app.modules.admin.audit import record_audit
from app.modules.admin.models import AuditLog, SupportTicket, TicketStatus
from app.modules.analytics import service as analytics
from app.modules.analytics.schemas import Analytics
from app.modules.auth.models import Role, RoleName, User, UserRole
from app.modules.auth.permissions import Perm
from app.modules.auth.router import user_public
from app.modules.auth.schemas import UserPublic
from app.modules.auth.service import revoke_all_sessions
from app.modules.catalog import service as catalog
from app.modules.catalog.models import CatalogStatus, Category, Product, Review, ReviewStatus, Service
from app.modules.catalog.schemas import (
    CategoryIn,
    CategoryOut,
    CategoryUpdate,
    ModerationAction,
    ProductOut,
    ServiceOut,
)
from app.modules.commissions import service as commissions
from app.modules.commissions.models import CommissionRateType, CommissionRule, CommissionScope
from app.modules.ledger import service as ledger
from app.modules.ledger.models import AccountType, FinancialReconciliation
from app.modules.merchants import finance
from app.modules.merchants import service as merchants
from app.modules.merchants.models import Merchant, MerchantPaymentAccount, MerchantStatus, MerchantVerification
from app.modules.merchants.schemas import MerchantOut, PaymentAccountOut, StatusTransition, VerificationEventOut
from app.modules.orders import service as orders
from app.modules.orders.models import CancellationStatus, MerchantOrder, Order, OrderStatusHistory
from app.modules.orders.schemas import CancellationDecision, MerchantOrderMerchantView, OrderOut, StatusHistoryOut
from app.modules.orders.views import merchant_views, order_out
from app.modules.payments import chargebacks, refunds, webhooks
from app.modules.payments.models import (
    CAPTURED_STATUSES,
    Chargeback,
    ChargebackStatus,
    Payment,
    PaymentStatus,
    PaymentWebhookEvent,
    Refund,
    RefundInitiator,
    RefundScope,
    RefundStatus,
)
from app.modules.payments.reconciliation import run_reconciliation
from app.modules.payments.schemas import (
    ChargebackCreate,
    ChargebackOut,
    ChargebackResolve,
    PaymentAdminOut,
    RefundCreate,
    RefundDecision,
    RefundOut,
    WebhookEventOut,
)
from app.modules.settlements.models import Settlement, SettlementStatus
from app.modules.settlements.service import record_reconciled_settlement
from app.modules.stores.models import Store

router = APIRouter(prefix="/admin", tags=["admin"])

AuditViewAuth = Annotated[AuthContext, Depends(require_permission(Perm.AUDIT_VIEW))]
CatalogModerateAuth = Annotated[AuthContext, Depends(require_permission(Perm.CATALOG_MODERATE))]
CategoriesManageAuth = Annotated[AuthContext, Depends(require_permission(Perm.CATEGORIES_MANAGE))]
CommissionsManageAuth = Annotated[AuthContext, Depends(require_permission(Perm.COMMISSIONS_MANAGE))]
CommissionsViewAuth = Annotated[AuthContext, Depends(require_permission(Perm.COMMISSIONS_VIEW))]
CustomersManageAuth = Annotated[AuthContext, Depends(require_permission(Perm.CUSTOMERS_MANAGE))]
CustomersViewAuth = Annotated[AuthContext, Depends(require_permission(Perm.CUSTOMERS_VIEW))]
DisputesManageAuth = Annotated[AuthContext, Depends(require_permission(Perm.DISPUTES_MANAGE))]
MerchantsManageAuth = Annotated[AuthContext, Depends(require_permission(Perm.MERCHANTS_MANAGE))]
MerchantsViewAuth = Annotated[AuthContext, Depends(require_permission(Perm.MERCHANTS_VIEW))]
OrdersManageAuth = Annotated[AuthContext, Depends(require_permission(Perm.ORDERS_MANAGE))]
OrdersViewAuth = Annotated[AuthContext, Depends(require_permission(Perm.ORDERS_VIEW))]
PaymentsViewAuth = Annotated[AuthContext, Depends(require_permission(Perm.PAYMENTS_VIEW))]
ReconciliationRunAuth = Annotated[AuthContext, Depends(require_permission(Perm.RECONCILIATION_RUN))]
RefundsManageAuth = Annotated[AuthContext, Depends(require_permission(Perm.REFUNDS_MANAGE))]
SettingsManageAuth = Annotated[AuthContext, Depends(require_permission(Perm.SETTINGS_MANAGE))]
SettingsViewAuth = Annotated[AuthContext, Depends(require_permission(Perm.SETTINGS_VIEW))]
SettlementsReconcileAuth = Annotated[AuthContext, Depends(require_permission(Perm.SETTLEMENTS_RECONCILE))]
SettlementsViewAuth = Annotated[AuthContext, Depends(require_permission(Perm.SETTLEMENTS_VIEW))]
SupportManageAuth = Annotated[AuthContext, Depends(require_permission(Perm.SUPPORT_MANAGE))]
UsersRolesManageAuth = Annotated[AuthContext, Depends(require_permission(Perm.USERS_ROLES_MANAGE))]


# -- overview ---------------------------------------------------------------------------


class AdminOverview(BaseModel):
    currency: str = "SAR"
    total_customers: int
    total_merchants: int
    active_merchants: int
    pending_merchant_applications: int
    total_orders: int
    gross_marketplace_sales: int
    platform_revenue: int
    payment_success_rate: float | None
    refund_volume: int
    settlement_volume: int
    pending_cancellations: int
    failed_webhooks: int
    sales_chart: list[finance.DailyPoint]


@router.get("/overview")
async def overview(ctx: PaymentsViewAuth, db: DbSession) -> AdminOverview:
    async def scalar(stmt: Any) -> int:
        return int((await db.exec(stmt)).first() or 0)

    customers = await scalar(
        select(func.count(col(User.id))).join(UserRole).join(Role).where(col(Role.name) == RoleName.CUSTOMER.value)
    )
    captured = [s.value for s in CAPTURED_STATUSES]
    attempted = await scalar(
        select(func.count(col(Payment.id))).where(col(Payment.status).in_([*captured, PaymentStatus.FAILED.value]))
    )
    succeeded = await scalar(select(func.count(col(Payment.id))).where(col(Payment.status).in_(captured)))
    return AdminOverview(
        total_customers=customers,
        total_merchants=await scalar(select(func.count(col(Merchant.id)))),
        active_merchants=await scalar(
            select(func.count(col(Merchant.id))).where(col(Merchant.status) == MerchantStatus.APPROVED.value)
        ),
        pending_merchant_applications=await scalar(
            select(func.count(col(Merchant.id))).where(
                col(Merchant.status).in_([MerchantStatus.SUBMITTED.value, MerchantStatus.UNDER_REVIEW.value])
            )
        ),
        total_orders=await scalar(
            select(func.count(col(MerchantOrder.id))).where(col(MerchantOrder.paid_at).is_not(None))
        ),
        gross_marketplace_sales=await scalar(
            select(func.coalesce(func.sum(col(Payment.amount)), 0)).where(col(Payment.status).in_(captured))
        ),
        platform_revenue=await ledger.balance(db, AccountType.PLATFORM_COMMISSION),
        payment_success_rate=round(succeeded / attempted, 4) if attempted else None,
        refund_volume=await scalar(
            select(func.coalesce(func.sum(Refund.amount), 0)).where(Refund.status == RefundStatus.SUCCEEDED.value)
        ),
        settlement_volume=await scalar(
            select(func.coalesce(func.sum(Settlement.amount), 0)).where(
                Settlement.status == SettlementStatus.COMPLETED.value
            )
        ),
        pending_cancellations=await scalar(
            select(func.count(col(MerchantOrder.id))).where(
                MerchantOrder.cancellation_status == CancellationStatus.REQUESTED.value
            )
        ),
        failed_webhooks=await scalar(
            select(func.count(col(PaymentWebhookEvent.id))).where(col(PaymentWebhookEvent.status) == "FAILED")
        ),
        sales_chart=await finance.daily_sales(db, None),
    )


AnalyticsDays = Annotated[int, Query(ge=7, le=365, description="Length of the period in days, ending today.")]


@router.get("/analytics")
async def marketplace_analytics(ctx: PaymentsViewAuth, db: DbSession, days: AnalyticsDays = 30) -> Analytics:
    """Charts for the overview: sales trend, period-over-period KPIs and breakdowns."""
    return await analytics.build(db, None, days)


# -- merchants --------------------------------------------------------------------------


class MerchantListItem(BaseModel):
    id: uuid.UUID
    business_name: str
    status: str
    store_slug: str | None
    city: str | None
    submitted_at: datetime | None
    created_at: datetime


@router.get("/merchants")
async def list_merchants(
    ctx: MerchantsViewAuth,
    db: DbSession,
    page: PageDep,
    status_filter: Annotated[MerchantStatus | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[MerchantListItem]:
    stmt = (
        select(Merchant, Store)
        .outerjoin(Store, col(Store.merchant_id) == col(Merchant.id))
        .order_by(col(Merchant.created_at).desc())
    )
    if status_filter:
        stmt = stmt.where(Merchant.status == status_filter.value)
    if q:
        stmt = stmt.where(or_(col(Merchant.business_name).ilike(f"%{q}%"), col(Store.name).ilike(f"%{q}%")))
    total = (await db.exec(select(func.count()).select_from(stmt.order_by(None).subquery()))).first()
    rows = (await db.exec(stmt.limit(page.page_size).offset(page.offset))).all()
    items = [
        MerchantListItem(
            id=m.id,
            business_name=m.business_name,
            status=m.status,
            store_slug=s.slug if s else None,
            city=s.city if s else None,
            submitted_at=m.submitted_at,
            created_at=m.created_at,
        )
        for m, s in rows
    ]
    return Page(items=items, total=int(total or 0), page=page.page, page_size=page.page_size)


async def _merchant(db: DbSession, merchant_id: uuid.UUID, *, lock: bool = False) -> Merchant:
    merchant = await db.get(Merchant, merchant_id, with_for_update=lock)
    if merchant is None:
        raise NotFound("Merchant not found.")
    return merchant


class MerchantDetail(BaseModel):
    merchant: MerchantOut
    verification_history: list[VerificationEventOut]
    payment_account: PaymentAccountOut
    financial_summary: finance.FinancialSummary


@router.get("/merchants/{merchant_id}")
async def get_merchant(
    merchant_id: uuid.UUID, ctx: MerchantsViewAuth, db: DbSession, provider: ProviderDep
) -> MerchantDetail:
    merchant = await _merchant(db, merchant_id)
    history = (
        await db.exec(
            select(MerchantVerification)
            .where(MerchantVerification.merchant_id == merchant.id)
            .order_by(col(MerchantVerification.created_at))
        )
    ).all()
    fee_bearer = (await settings_service.get_setting(db, "payments", settings_service.PaymentSettings)).fee_bearer
    return MerchantDetail(
        merchant=await merchants.merchant_out(db, merchant, provider.name),
        verification_history=[VerificationEventOut.model_validate(h) for h in history],
        payment_account=await merchants.payment_account_out(db, merchant, provider),
        financial_summary=await finance.summary(
            db,
            merchant.id,
            fee_bearer,
            await settings_service.get_setting(db, "delivery", settings_service.DeliveryFinanceSettings),
        ),
    )


MerchantAction = Literal["start_review", "approve", "reject", "request_info", "suspend", "reactivate"]
_ACTION_STATUS = {
    "start_review": MerchantStatus.UNDER_REVIEW,
    "approve": MerchantStatus.APPROVED,
    "reject": MerchantStatus.REJECTED,
    "request_info": MerchantStatus.ADDITIONAL_INFO_REQUIRED,
    "suspend": MerchantStatus.SUSPENDED,
    "reactivate": MerchantStatus.APPROVED,
}


@router.post("/merchants/{merchant_id}/{action}")
async def merchant_action(
    merchant_id: uuid.UUID,
    action: MerchantAction,
    body: StatusTransition,
    request: Request,
    ctx: MerchantsManageAuth,
    db: DbSession,
    provider: ProviderDep,
) -> MerchantOut:
    merchant = await _merchant(db, merchant_id, lock=True)
    if action == "reactivate" and merchant.status != MerchantStatus.SUSPENDED.value:
        raise Conflict("Only suspended merchants can be reactivated.", code="invalid_transition")
    await merchants.transition(
        db, merchant, _ACTION_STATUS[action], actor_user_id=ctx.user_id, reason=body.reason, ip=client_ip(request)
    )
    return await merchants.merchant_out(db, merchant, provider.name)


@router.post("/merchants/{merchant_id}/payment-account/sync")
async def sync_merchant_payment_account(
    merchant_id: uuid.UUID, ctx: MerchantsManageAuth, db: DbSession, provider: ProviderDep
) -> PaymentAccountOut:
    merchant = await _merchant(db, merchant_id)
    await merchants.sync_payment_onboarding(db, merchant, provider)
    return await merchants.payment_account_out(db, merchant, provider)


# -- customers --------------------------------------------------------------------------


@router.get("/customers")
async def list_customers(
    ctx: CustomersViewAuth,
    db: DbSession,
    page: PageDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[UserPublic]:
    stmt = (
        select(User)
        .join(UserRole)
        .join(Role)
        .where(col(Role.name) == RoleName.CUSTOMER.value)
        .order_by(col(User.created_at).desc())
    )
    if q:
        stmt = stmt.where(or_(col(User.email).ilike(f"%{q}%"), col(User.full_name).ilike(f"%{q}%")))
    rows, total = await paginate(db, stmt, page)
    return Page(items=[user_public(u) for u in rows], total=total, page=page.page, page_size=page.page_size)


class ActiveToggle(BaseModel):
    is_active: bool
    reason: str = Field(min_length=3, max_length=2000)


@router.post("/users/{user_id}/active")
async def set_user_active(
    user_id: uuid.UUID, body: ActiveToggle, request: Request, ctx: CustomersManageAuth, db: DbSession
) -> UserPublic:
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise NotFound("User not found.")
    if user.has_role(RoleName.SUPER_ADMIN) and not ctx.user.has_role(RoleName.SUPER_ADMIN):
        raise Conflict("Only super administrators can change super administrators.")
    before = {"is_active": user.is_active}
    user.is_active = body.is_active
    if not body.is_active:
        await revoke_all_sessions(db, user.id, reason="disabled_by_admin")
    await record_audit(
        db,
        actor_user_id=ctx.user_id,
        action="user.set_active",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after={"is_active": body.is_active, "reason": body.reason},
        ip_address=client_ip(request),
    )
    return user_public(user)


class RolesUpdate(BaseModel):
    roles: list[RoleName] = Field(min_length=1)


@router.put("/users/{user_id}/roles")
async def set_user_roles(
    user_id: uuid.UUID, body: RolesUpdate, request: Request, ctx: UsersRolesManageAuth, db: DbSession
) -> UserPublic:
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise NotFound("User not found.")
    roles = (await db.exec(select(Role).where(col(Role.name).in_([r.value for r in body.roles])))).all()
    before = {"roles": user.role_names}
    user.roles = list(roles)
    await revoke_all_sessions(db, user.id, reason="roles_changed")
    await record_audit(
        db,
        actor_user_id=ctx.user_id,
        action="user.roles",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after={"roles": sorted(r.value for r in body.roles)},
        ip_address=client_ip(request),
    )
    return user_public(user)


# -- catalog moderation & categories ---------------------------------------------------


@router.get("/products")
async def moderate_products_list(
    ctx: CatalogModerateAuth,
    db: DbSession,
    page: PageDep,
    status_filter: Annotated[CatalogStatus | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[ProductOut]:
    stmt = (
        select(Product, Store)
        .join(Store, col(Store.id) == col(Product.store_id))
        .order_by(col(Product.created_at).desc())
    )
    if status_filter:
        stmt = stmt.where(Product.status == status_filter.value)
    if q:
        stmt = stmt.where(col(Product.title).ilike(f"%{q}%"))
    total = (await db.exec(select(func.count()).select_from(stmt.order_by(None).subquery()))).first()
    rows = [(p, s) for p, s in (await db.exec(stmt.limit(page.page_size).offset(page.offset))).all()]
    return Page(
        items=await catalog.products_out(db, rows), total=int(total or 0), page=page.page, page_size=page.page_size
    )


def _moderate(item: Product | Service, body: ModerationAction) -> None:
    if body.action == "block":
        item.status = CatalogStatus.BLOCKED.value
        item.moderation_note = body.note
    elif body.action == "unblock":
        if item.status != CatalogStatus.BLOCKED.value:
            raise Conflict("Item is not blocked.")
        item.status = CatalogStatus.DRAFT.value
        item.moderation_note = body.note
    elif body.action == "feature":
        item.is_featured = True
    else:
        item.is_featured = False


@router.post("/products/{product_id}/moderation")
async def moderate_product(
    product_id: uuid.UUID, body: ModerationAction, request: Request, ctx: CatalogModerateAuth, db: DbSession
) -> ProductOut:
    product = await db.get(Product, product_id, with_for_update=True)
    if product is None:
        raise NotFound("Product not found.")
    before = {"status": product.status, "is_featured": product.is_featured}
    _moderate(product, body)
    await record_audit(
        db,
        actor_user_id=ctx.user_id,
        action=f"product.{body.action}",
        entity_type="product",
        entity_id=product.id,
        before=before,
        after={"status": product.status, "note": body.note},
        ip_address=client_ip(request),
    )
    store = await db.get(Store, product.store_id)
    assert store is not None
    return (await catalog.products_out(db, [(product, store)]))[0]


@router.post("/services/{service_id}/moderation")
async def moderate_service(
    service_id: uuid.UUID, body: ModerationAction, request: Request, ctx: CatalogModerateAuth, db: DbSession
) -> ServiceOut:
    service = await db.get(Service, service_id, with_for_update=True)
    if service is None:
        raise NotFound("Service not found.")
    before = {"status": service.status, "is_featured": service.is_featured}
    _moderate(service, body)
    await record_audit(
        db,
        actor_user_id=ctx.user_id,
        action=f"service.{body.action}",
        entity_type="service",
        entity_id=service.id,
        before=before,
        after={"status": service.status, "note": body.note},
        ip_address=client_ip(request),
    )
    store = await db.get(Store, service.store_id)
    assert store is not None
    return catalog.service_out(service, store)


class ReviewModeration(BaseModel):
    status: ReviewStatus


@router.post("/reviews/{review_id}/moderation", status_code=status.HTTP_204_NO_CONTENT)
async def moderate_review(
    review_id: uuid.UUID, body: ReviewModeration, ctx: CatalogModerateAuth, db: DbSession
) -> None:
    review = await db.get(Review, review_id, with_for_update=True)
    if review is None:
        raise NotFound("Review not found.")
    review.status = body.status.value
    await db.flush()
    await catalog.recalculate_store_rating(db, review.store_id)
    await record_audit(
        db,
        actor_user_id=ctx.user_id,
        action="review.moderate",
        entity_type="review",
        entity_id=review.id,
        after={"status": body.status.value},
    )


@router.get("/categories")
async def admin_categories(ctx: CategoriesManageAuth, db: DbSession) -> list[CategoryOut]:
    return await catalog.list_categories(db, include_inactive=True)


@router.post("/categories", status_code=status.HTTP_201_CREATED)
async def create_category(body: CategoryIn, ctx: CategoriesManageAuth, db: DbSession) -> CategoryOut:
    if (await db.exec(select(Category.id).where(Category.slug == body.slug))).first():
        raise Conflict("Category slug already exists.", code="slug_taken")
    if body.parent_id and await db.get(Category, body.parent_id) is None:
        raise NotFound("Parent category not found.")
    category = Category(**body.model_dump(mode="python"))
    category.kind = body.kind.value
    db.add(category)
    await db.flush()
    await cache_delete("categories:active")
    await record_audit(
        db,
        actor_user_id=ctx.user_id,
        action="category.create",
        entity_type="category",
        entity_id=category.id,
        after=body.model_dump(mode="json"),
    )
    return CategoryOut.model_validate(category)


@router.patch("/categories/{category_id}")
async def update_category(
    category_id: uuid.UUID, body: CategoryUpdate, ctx: CategoriesManageAuth, db: DbSession
) -> CategoryOut:
    category = await db.get(Category, category_id, with_for_update=True)
    if category is None:
        raise NotFound("Category not found.")
    values = body.model_dump(exclude_unset=True)
    if values.get("parent_id") == category_id:
        raise ValidationFailed("A category cannot be its own parent.")
    if values.get("parent_id") and category_id in await catalog.category_ancestors(db, values["parent_id"]):
        raise ValidationFailed("This would create a category cycle.")
    for key, value in values.items():
        setattr(category, key, value.value if hasattr(value, "value") else value)
    await db.flush()
    await cache_delete("categories:active")
    await record_audit(
        db,
        actor_user_id=ctx.user_id,
        action="category.update",
        entity_type="category",
        entity_id=category.id,
        after=body.model_dump(mode="json", exclude_unset=True),
    )
    return CategoryOut.model_validate(category)


# -- orders & cancellations ----------------------------------------------------------------


@router.get("/orders")
async def list_orders(
    ctx: OrdersViewAuth,
    db: DbSession,
    page: PageDep,
    merchant_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    status_filter: Annotated[str | None, Query(alias="status", max_length=30)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    number: Annotated[str | None, Query(max_length=40)] = None,
    cancellation_requested: bool | None = None,
) -> Page[MerchantOrderMerchantView]:
    stmt = select(MerchantOrder).order_by(col(MerchantOrder.created_at).desc())
    if merchant_id:
        stmt = stmt.where(MerchantOrder.merchant_id == merchant_id)
    if customer_id:
        stmt = stmt.where(MerchantOrder.customer_user_id == customer_id)
    if status_filter:
        stmt = stmt.where(MerchantOrder.status == status_filter)
    if date_from:
        stmt = stmt.where(MerchantOrder.created_at >= date_from)
    if date_to:
        stmt = stmt.where(MerchantOrder.created_at < date_to)
    if number:
        stmt = stmt.where(col(MerchantOrder.number).ilike(f"{number}%"))
    if cancellation_requested:
        stmt = stmt.where(MerchantOrder.cancellation_status == CancellationStatus.REQUESTED.value)
    rows, total = await paginate(db, stmt, page)
    return Page(items=await merchant_views(db, rows), total=total, page=page.page, page_size=page.page_size)


class AdminOrderDetail(BaseModel):
    order: OrderOut
    history: list[StatusHistoryOut]
    payments: list[PaymentAdminOut]


@router.get("/orders/{order_id}")
async def get_order(order_id: uuid.UUID, ctx: OrdersViewAuth, db: DbSession) -> AdminOrderDetail:
    order = await db.get(Order, order_id)
    if order is None:
        raise NotFound("Order not found.")
    history = (
        await db.exec(
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order.id)
            .order_by(col(OrderStatusHistory.created_at))
        )
    ).all()
    payments = (
        await db.exec(select(Payment).where(col(Payment.order_id) == order.id).order_by(col(Payment.created_at)))
    ).all()
    return AdminOrderDetail(
        order=await order_out(db, order),
        history=[StatusHistoryOut.model_validate(h) for h in history],
        payments=[PaymentAdminOut.model_validate(p) for p in payments],
    )


@router.post("/merchant-orders/{mo_id}/cancellation-decision")
async def decide_cancellation(
    mo_id: uuid.UUID, body: CancellationDecision, ctx: OrdersManageAuth, db: DbSession, provider: ProviderDep
) -> MerchantOrderMerchantView:
    mo = await db.get(MerchantOrder, mo_id, with_for_update=True)
    if mo is None:
        raise NotFound("Order not found.")
    await orders.decide_cancellation(
        db,
        mo,
        provider,
        approve=body.approve,
        actor_user_id=ctx.user_id,
        initiated_by=RefundInitiator.PLATFORM.value,
        note=body.note,
    )
    await record_audit(
        db,
        actor_user_id=ctx.user_id,
        action="order.cancellation_decision",
        entity_type="merchant_order",
        entity_id=mo.id,
        after={"approve": body.approve, "note": body.note},
    )
    return (await merchant_views(db, [mo]))[0]


# -- payments, refunds, chargebacks, webhooks -------------------------------------------


@router.get("/payments")
async def list_payments(
    ctx: PaymentsViewAuth,
    db: DbSession,
    page: PageDep,
    reference: Annotated[str | None, Query(max_length=100)] = None,
    status_filter: Annotated[PaymentStatus | None, Query(alias="status")] = None,
    merchant_id: uuid.UUID | None = None,
    is_test: bool | None = None,
) -> Page[PaymentAdminOut]:
    stmt = select(Payment).order_by(col(Payment.created_at).desc())
    if reference:
        conditions: list[ColumnElement[bool]] = [col(Payment.provider_payment_id) == reference]
        with contextlib.suppress(ValueError):
            conditions.append(col(Payment.id) == uuid.UUID(reference))
        mo_ids = select(col(MerchantOrder.id)).where(col(MerchantOrder.number).ilike(f"{reference}%"))
        conditions.append(col(Payment.merchant_order_id).in_(mo_ids))
        stmt = stmt.where(or_(*conditions))
    if status_filter:
        stmt = stmt.where(Payment.status == status_filter.value)
    if merchant_id:
        stmt = stmt.where(Payment.merchant_id == merchant_id)
    if is_test is not None:
        stmt = stmt.where(col(Payment.is_test).is_(is_test))
    rows, total = await paginate(db, stmt, page)
    return Page(
        items=[PaymentAdminOut.model_validate(p) for p in rows], total=total, page=page.page, page_size=page.page_size
    )


@router.get("/payments/{payment_id}")
async def get_payment(payment_id: uuid.UUID, ctx: PaymentsViewAuth, db: DbSession) -> PaymentAdminOut:
    payment = await db.get(Payment, payment_id)
    if payment is None:
        raise NotFound("Payment not found.")
    return PaymentAdminOut.model_validate(payment)


@router.post("/payments/{payment_id}/sync")
async def sync_payment(
    payment_id: uuid.UUID, ctx: ReconciliationRunAuth, db: DbSession, provider: ProviderDep
) -> PaymentAdminOut:
    from app.modules.payments.service import sync_payment as do_sync

    payment = await db.get(Payment, payment_id, with_for_update=True)
    if payment is None:
        raise NotFound("Payment not found.")
    await do_sync(db, payment, provider)
    return PaymentAdminOut.model_validate(payment)


@router.post("/payments/{payment_id}/refunds", status_code=status.HTTP_201_CREATED)
async def platform_refund(
    payment_id: uuid.UUID,
    body: RefundCreate,
    request: Request,
    ctx: RefundsManageAuth,
    db: DbSession,
    provider: ProviderDep,
) -> RefundOut:
    payment = await db.get(Payment, payment_id, with_for_update=True)
    if payment is None:
        raise NotFound("Payment not found.")
    refund = await refunds.create_and_process(
        db,
        payment,
        provider,
        amount=body.amount,
        initiated_by=RefundInitiator.PLATFORM,
        actor_user_id=ctx.user_id,
        reason=body.reason,
        restock=body.restock,
        scope=RefundScope(body.scope),
    )
    await record_audit(
        db,
        actor_user_id=ctx.user_id,
        action="refund.platform",
        entity_type="refund",
        entity_id=refund.id,
        after={"amount": refund.amount, "status": refund.status, "scope": refund.scope},
        ip_address=client_ip(request),
    )
    return RefundOut.model_validate(refund)


@router.get("/refunds")
async def list_refunds(
    ctx: PaymentsViewAuth,
    db: DbSession,
    page: PageDep,
    status_filter: Annotated[RefundStatus | None, Query(alias="status")] = None,
) -> Page[RefundOut]:
    stmt = select(Refund).order_by(col(Refund.created_at).desc())
    if status_filter:
        stmt = stmt.where(Refund.status == status_filter.value)
    rows, total = await paginate(db, stmt, page)
    return Page(
        items=[RefundOut.model_validate(r) for r in rows], total=total, page=page.page, page_size=page.page_size
    )


@router.post("/refunds/{refund_id}/decision")
async def decide_refund(
    refund_id: uuid.UUID, body: RefundDecision, ctx: RefundsManageAuth, db: DbSession, provider: ProviderDep
) -> RefundOut:
    refund = await db.get(Refund, refund_id, with_for_update=True)
    if refund is None:
        raise NotFound("Refund not found.")
    if body.approve:
        refund = await refunds.process_refund(db, refund, provider, reviewer_id=ctx.user_id)
    else:
        refund = await refunds.reject_refund(db, refund, reviewer_id=ctx.user_id, note=body.note)
    await record_audit(
        db,
        actor_user_id=ctx.user_id,
        action="refund.decision",
        entity_type="refund",
        entity_id=refund.id,
        after={"approve": body.approve, "status": refund.status},
    )
    return RefundOut.model_validate(refund)


@router.get("/chargebacks")
async def list_chargebacks(ctx: PaymentsViewAuth, db: DbSession, page: PageDep) -> Page[ChargebackOut]:
    rows, total = await paginate(db, select(Chargeback).order_by(col(Chargeback.created_at).desc()), page)
    return Page(
        items=[ChargebackOut.model_validate(c) for c in rows], total=total, page=page.page, page_size=page.page_size
    )


@router.post("/chargebacks", status_code=status.HTTP_201_CREATED)
async def record_chargeback(body: ChargebackCreate, ctx: DisputesManageAuth, db: DbSession) -> ChargebackOut:
    payment = await db.get(Payment, body.payment_id)
    if payment is None:
        raise NotFound("Payment not found.")
    chargeback = await chargebacks.open_chargeback(
        db,
        payment,
        amount=body.amount,
        provider_reference=body.provider_reference,
        reason=body.reason,
        actor_user_id=ctx.user_id,
    )
    return ChargebackOut.model_validate(chargeback)


@router.post("/chargebacks/{chargeback_id}/resolve")
async def resolve_chargeback(
    chargeback_id: uuid.UUID, body: ChargebackResolve, ctx: DisputesManageAuth, db: DbSession
) -> ChargebackOut:
    chargeback = await chargebacks.get_chargeback(db, chargeback_id)
    await chargebacks.resolve_chargeback(
        db, chargeback, outcome=ChargebackStatus(body.outcome), actor_user_id=ctx.user_id
    )
    return ChargebackOut.model_validate(chargeback)


@router.get("/webhook-events")
async def list_webhook_events(
    ctx: PaymentsViewAuth,
    db: DbSession,
    page: PageDep,
    status_filter: Annotated[str | None, Query(alias="status", max_length=20)] = None,
) -> Page[WebhookEventOut]:
    stmt = select(PaymentWebhookEvent).order_by(col(PaymentWebhookEvent.created_at).desc())
    if status_filter:
        stmt = stmt.where(PaymentWebhookEvent.status == status_filter)
    rows, total = await paginate(db, stmt, page)
    return Page(
        items=[WebhookEventOut.model_validate(e) for e in rows], total=total, page=page.page, page_size=page.page_size
    )


@router.post("/webhook-events/{event_id}/reprocess")
async def reprocess_webhook(
    event_id: uuid.UUID, ctx: ReconciliationRunAuth, db: DbSession, provider: ProviderDep
) -> dict[str, Any]:
    result = await webhooks.reprocess_event(db, provider, event_id)
    return {"outcome": result.outcome, "status_code": result.status_code}


# -- commissions --------------------------------------------------------------------------


class CommissionRuleIn(BaseModel):
    scope: CommissionScope
    merchant_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    rate_type: CommissionRateType = CommissionRateType.PERCENTAGE
    rate: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=3)
    fixed_amount: int | None = Field(default=None, ge=0)
    effective_from: datetime | None = None
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _validate(self) -> "CommissionRuleIn":
        if self.rate_type == CommissionRateType.PERCENTAGE and self.rate is None:
            raise ValueError("rate is required for percentage commissions.")
        if self.rate_type == CommissionRateType.FIXED and self.fixed_amount is None:
            raise ValueError("fixed_amount is required for fixed commissions.")
        if self.scope == CommissionScope.MERCHANT and not self.merchant_id:
            raise ValueError("merchant_id is required for merchant commissions.")
        if self.scope == CommissionScope.CATEGORY and not self.category_id:
            raise ValueError("category_id is required for category commissions.")
        if self.scope == CommissionScope.GLOBAL and (self.merchant_id or self.category_id):
            raise ValueError("Global commissions cannot target a merchant or category.")
        return self


class CommissionRuleAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope: str
    merchant_id: uuid.UUID | None
    category_id: uuid.UUID | None
    rate_type: str
    rate: Decimal | None
    fixed_amount: int | None
    effective_from: datetime
    effective_to: datetime | None
    created_by_user_id: uuid.UUID | None
    note: str | None
    created_at: datetime


@router.get("/commissions")
async def list_commission_rules(
    ctx: CommissionsViewAuth,
    db: DbSession,
    page: PageDep,
    scope: CommissionScope | None = None,
    merchant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
) -> Page[CommissionRuleAdminOut]:
    stmt = select(CommissionRule).order_by(
        col(CommissionRule.effective_from).desc(), col(CommissionRule.created_at).desc()
    )
    if scope:
        stmt = stmt.where(CommissionRule.scope == scope.value)
    if merchant_id:
        stmt = stmt.where(CommissionRule.merchant_id == merchant_id)
    if category_id:
        stmt = stmt.where(CommissionRule.category_id == category_id)
    rows, total = await paginate(db, stmt, page)
    return Page(
        items=[CommissionRuleAdminOut.model_validate(r) for r in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.post("/commissions", status_code=status.HTTP_201_CREATED)
async def set_commission(
    body: CommissionRuleIn, request: Request, ctx: CommissionsManageAuth, db: DbSession
) -> CommissionRuleAdminOut:
    if body.merchant_id and await db.get(Merchant, body.merchant_id) is None:
        raise NotFound("Merchant not found.")
    if body.category_id and await db.get(Category, body.category_id) is None:
        raise NotFound("Category not found.")
    rule = await commissions.set_rule(
        db,
        scope=body.scope,
        merchant_id=body.merchant_id,
        category_id=body.category_id,
        rate_type=body.rate_type,
        rate=body.rate,
        fixed_amount=body.fixed_amount,
        effective_from=body.effective_from,
        note=body.note,
        actor_user_id=ctx.user_id,
        ip=client_ip(request),
    )
    return CommissionRuleAdminOut.model_validate(rule)


@router.post("/commissions/{rule_id}/end")
async def end_commission(
    rule_id: uuid.UUID, request: Request, ctx: CommissionsManageAuth, db: DbSession
) -> CommissionRuleAdminOut:
    rule = await commissions.end_rule(db, rule_id, actor_user_id=ctx.user_id, ip=client_ip(request))
    return CommissionRuleAdminOut.model_validate(rule)


# -- settlements & reconciliation -------------------------------------------------------


class AdminSettlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_id: uuid.UUID
    provider: str
    provider_settlement_id: str
    amount: int
    status: str
    is_test: bool
    completed_at: datetime | None
    failure_reason: str | None
    confirmation_source: str | None
    confirmation_reference: str | None
    created_at: datetime


@router.get("/settlements")
async def list_settlements(
    ctx: SettlementsViewAuth,
    db: DbSession,
    page: PageDep,
    merchant_id: uuid.UUID | None = None,
    status_filter: Annotated[SettlementStatus | None, Query(alias="status")] = None,
) -> Page[AdminSettlementOut]:
    stmt = select(Settlement).order_by(col(Settlement.created_at).desc())
    if merchant_id:
        stmt = stmt.where(Settlement.merchant_id == merchant_id)
    if status_filter:
        stmt = stmt.where(Settlement.status == status_filter.value)
    rows, total = await paginate(db, stmt, page)
    return Page(
        items=[AdminSettlementOut.model_validate(s) for s in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


class ReconciledSettlementIn(BaseModel):
    merchant_id: uuid.UUID
    amount: int = Field(gt=0)
    provider_settlement_id: str = Field(min_length=3, max_length=100)
    completed_at: datetime
    evidence_reference: str = Field(min_length=3, max_length=200, description="Provider statement/transfer reference.")


@router.post("/settlements/reconciled", status_code=status.HTTP_201_CREATED)
async def record_settlement(
    body: ReconciledSettlementIn, request: Request, ctx: SettlementsReconcileAuth, db: DbSession, provider: ProviderDep
) -> AdminSettlementOut:
    settlement = await record_reconciled_settlement(
        db,
        provider,
        merchant_id=body.merchant_id,
        amount=body.amount,
        provider_settlement_id=body.provider_settlement_id,
        completed_at=body.completed_at,
        evidence_reference=body.evidence_reference,
        actor_user_id=ctx.user_id,
        ip=client_ip(request),
    )
    return AdminSettlementOut.model_validate(settlement)


class ReconciliationIn(BaseModel):
    period_start: datetime | None = None
    period_end: datetime | None = None
    apply: bool = False


class ReconciliationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    scope: str
    status: str
    period_start: datetime | None
    period_end: datetime | None
    checked_count: int
    mismatch_count: int
    applied_updates: int
    details: list[dict[str, Any]]
    created_at: datetime
    completed_at: datetime | None


@router.post("/reconciliation", status_code=status.HTTP_201_CREATED)
async def reconcile(
    body: ReconciliationIn, ctx: ReconciliationRunAuth, db: DbSession, provider: ProviderDep
) -> ReconciliationOut:
    run = await run_reconciliation(
        db,
        provider,
        period_start=body.period_start,
        period_end=body.period_end,
        apply=body.apply,
        actor_user_id=ctx.user_id,
    )
    return ReconciliationOut.model_validate(run)


@router.get("/reconciliation")
async def list_reconciliations(ctx: ReconciliationRunAuth, db: DbSession, page: PageDep) -> Page[ReconciliationOut]:
    rows, total = await paginate(
        db, select(FinancialReconciliation).order_by(col(FinancialReconciliation.created_at).desc()), page
    )
    return Page(
        items=[ReconciliationOut.model_validate(r) for r in rows], total=total, page=page.page, page_size=page.page_size
    )


# -- settings, provider status, audit logs, support ------------------------------------


@router.get("/settings")
async def get_settings_all(ctx: SettingsViewAuth, db: DbSession) -> dict[str, dict[str, Any]]:
    return await settings_service.get_all(db)


@router.put("/settings/{key}")
async def update_setting(
    key: str, body: dict[str, Any], request: Request, ctx: SettingsManageAuth, db: DbSession
) -> dict[str, Any]:
    return await settings_service.update_setting(db, key, body, actor_user_id=ctx.user_id, ip=client_ip(request))


class ProviderStatusOut(BaseModel):
    provider: str
    is_test: bool
    platform_recipient_configured: bool
    supports_splits: bool
    max_merchants_per_payment: int
    supports_settlement_lookup: bool
    supports_chargeback_events: bool
    notes: list[str]
    merchant_accounts_by_status: dict[str, int]


@router.get("/payment-provider")
async def payment_provider_status(ctx: SettingsViewAuth, db: DbSession, provider: ProviderDep) -> ProviderStatusOut:
    """Provider configuration is environment-managed (secrets never pass through the API)."""
    counts = dict(
        (
            await db.exec(
                select(MerchantPaymentAccount.onboarding_status, func.count())
                .where(MerchantPaymentAccount.provider == provider.name)
                .group_by(MerchantPaymentAccount.onboarding_status)
            )
        ).all()
    )
    caps = provider.capabilities
    return ProviderStatusOut(
        provider=provider.name,
        is_test=provider.is_test,
        platform_recipient_configured=bool(provider.platform_recipient_id),
        supports_splits=caps.supports_splits,
        max_merchants_per_payment=caps.max_merchants_per_payment,
        supports_settlement_lookup=caps.supports_settlement_lookup,
        supports_chargeback_events=caps.supports_chargeback_events,
        notes=list(caps.notes),
        merchant_accounts_by_status={str(k): int(v) for k, v in counts.items()},
    )


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime


@router.get("/audit-logs")
async def audit_logs(
    ctx: AuditViewAuth,
    db: DbSession,
    page: PageDep,
    action: Annotated[str | None, Query(max_length=100)] = None,
    entity_type: Annotated[str | None, Query(max_length=60)] = None,
    entity_id: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[AuditLogOut]:
    stmt = select(AuditLog).order_by(col(AuditLog.created_at).desc())
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    rows, total = await paginate(db, stmt, page)
    return Page(
        items=[AuditLogOut.model_validate(a) for a in rows], total=total, page=page.page, page_size=page.page_size
    )


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    merchant_order_id: uuid.UUID | None
    subject: str
    body: str
    status: str
    admin_response: str | None
    created_at: datetime
    updated_at: datetime


class TicketUpdate(BaseModel):
    status: TicketStatus
    admin_response: str | None = Field(default=None, max_length=5000)


@router.get("/support-tickets")
async def list_tickets(
    ctx: SupportManageAuth,
    db: DbSession,
    page: PageDep,
    status_filter: Annotated[TicketStatus | None, Query(alias="status")] = None,
) -> Page[TicketOut]:
    stmt = select(SupportTicket).order_by(col(SupportTicket.created_at).desc())
    if status_filter:
        stmt = stmt.where(SupportTicket.status == status_filter.value)
    rows, total = await paginate(db, stmt, page)
    return Page(
        items=[TicketOut.model_validate(t) for t in rows], total=total, page=page.page, page_size=page.page_size
    )


@router.patch("/support-tickets/{ticket_id}")
async def update_ticket(ticket_id: uuid.UUID, body: TicketUpdate, ctx: SupportManageAuth, db: DbSession) -> TicketOut:
    ticket = await db.get(SupportTicket, ticket_id, with_for_update=True)
    if ticket is None:
        raise NotFound("Ticket not found.")
    ticket.status = body.status.value
    if body.admin_response is not None:
        ticket.admin_response = body.admin_response
    await db.flush()
    return TicketOut.model_validate(ticket)
