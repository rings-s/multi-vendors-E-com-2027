"""/api/v1/payments (customer) and /api/v1/webhooks/{provider}."""

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlmodel import col, select

from app.api.deps import CustomerAuth
from app.core.errors import NotFound
from app.core.pagination import Page, PageDep, paginate
from app.database.session import DbSession
from app.integrations.payments.base import WebhookRequest
from app.integrations.payments.factory import ProviderDep, get_provider_by_name
from app.modules.orders import service as orders
from app.modules.payments import service, webhooks
from app.modules.payments.models import Payment
from app.modules.payments.schemas import PaymentOut, PayRequest

router = APIRouter(prefix="/payments", tags=["payments"])
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("")
async def list_payments(ctx: CustomerAuth, db: DbSession, page: PageDep) -> Page[PaymentOut]:
    stmt = select(Payment).where(col(Payment.customer_user_id) == ctx.user_id).order_by(col(Payment.created_at).desc())
    rows, total = await paginate(db, stmt, page)
    return Page(
        items=[PaymentOut.model_validate(p) for p in rows], total=total, page=page.page, page_size=page.page_size
    )


@router.get("/{payment_id}")
async def get_payment(payment_id: uuid.UUID, ctx: CustomerAuth, db: DbSession) -> PaymentOut:
    return PaymentOut.model_validate(await service.get_payment_for_customer(db, ctx.user_id, payment_id))


@router.post("/{payment_id}/pay")
async def pay(
    payment_id: uuid.UUID, body: PayRequest, ctx: CustomerAuth, db: DbSession, provider: ProviderDep
) -> PaymentOut:
    payment = await service.get_payment_for_customer(db, ctx.user_id, payment_id, lock=True)
    await service.start_payment(db, payment, provider, source=body.source.model_dump())
    return PaymentOut.model_validate(payment)


@router.post("/{payment_id}/sync")
async def sync(payment_id: uuid.UUID, ctx: CustomerAuth, db: DbSession, provider: ProviderDep) -> PaymentOut:
    """Called after the payer returns from the provider. The redirect itself proves
    nothing; the backend asks the provider for the payment's verified state."""
    payment = await service.get_payment_for_customer(db, ctx.user_id, payment_id, lock=True)
    await service.sync_payment(db, payment, provider)
    return PaymentOut.model_validate(payment)


@router.post("/merchant-orders/{mo_id}/retry")
async def retry(mo_id: uuid.UUID, ctx: CustomerAuth, db: DbSession, provider: ProviderDep) -> PaymentOut:
    mo = await orders.get_customer_merchant_order(db, ctx.user_id, mo_id)
    return PaymentOut.model_validate(await service.retry_payment(db, mo, provider))


@webhook_router.post("/{provider_name}", include_in_schema=True)
async def receive_webhook(provider_name: str, request: Request, db: DbSession) -> JSONResponse:
    if provider_name not in {"moyasar", "mock"}:
        raise NotFound("Unknown webhook provider.")
    provider = get_provider_by_name(provider_name)
    body = await request.body()
    result = await webhooks.handle_webhook(
        db, provider, WebhookRequest(headers={k.lower(): v for k, v in request.headers.items()}, body=body)
    )
    return JSONResponse(
        status_code=result.status_code, content={"outcome": result.outcome, "event_id": result.event_id}
    )
