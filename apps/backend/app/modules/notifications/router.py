"""/api/v1/notifications, /api/v1/uploads, /api/v1/support"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from asyncer import asyncify
from fastapi import APIRouter, File, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import col, func, select, update

from app.api.deps import CurrentAuth
from app.core.config import get_settings
from app.core.errors import NotFound, PermissionDenied
from app.core.i18n import render, resolve_language
from app.core.pagination import Page, PageDep, paginate
from app.core.security import utcnow
from app.database.session import DbSession
from app.infrastructure.storage import store_image
from app.modules.admin.models import SupportTicket
from app.modules.auth.models import RoleName
from app.modules.notifications.models import Notification
from app.modules.orders.models import MerchantOrder

router = APIRouter(prefix="/notifications", tags=["notifications"])
uploads_router = APIRouter(prefix="/uploads", tags=["uploads"])
support_router = APIRouter(prefix="/support", tags=["support"])


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    data: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


class NotificationPage(Page[NotificationOut]):
    unread: int


@router.get("")
async def list_notifications(
    request: Request, ctx: CurrentAuth, db: DbSession, page: PageDep, unread_only: bool = False
) -> NotificationPage:
    language = ctx.user.preferred_language or resolve_language(request.headers.get("accept-language"))
    stmt = (
        select(Notification)
        .where(col(Notification.user_id) == ctx.user_id)
        .order_by(col(Notification.created_at).desc())
    )
    if unread_only:
        stmt = stmt.where(col(Notification.read_at).is_(None))
    rows, total = await paginate(db, stmt, page)
    unread = (
        await db.exec(
            select(func.count(col(Notification.id))).where(
                col(Notification.user_id) == ctx.user_id, col(Notification.read_at).is_(None)
            )
        )
    ).first()
    items = []
    for n in rows:
        title, body = render(n.type, language, n.data)
        items.append(
            NotificationOut(
                id=n.id, type=n.type, title=title, body=body, data=n.data, read_at=n.read_at, created_at=n.created_at
            )
        )
    return NotificationPage(items=items, total=total, page=page.page, page_size=page.page_size, unread=int(unread or 0))


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(notification_id: uuid.UUID, ctx: CurrentAuth, db: DbSession) -> None:
    notification = await db.get(Notification, notification_id)
    if notification is None or notification.user_id != ctx.user_id:
        raise NotFound("Notification not found.")
    notification.read_at = notification.read_at or utcnow()


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(ctx: CurrentAuth, db: DbSession) -> None:
    await db.exec(
        update(Notification)
        .where(col(Notification.user_id) == ctx.user_id, col(Notification.read_at).is_(None))
        .values(read_at=utcnow())
    )


class UploadOut(BaseModel):
    url: str


@uploads_router.post("/images", status_code=status.HTTP_201_CREATED)
async def upload_image(
    ctx: CurrentAuth,
    file: Annotated[UploadFile, File()],
    purpose: Literal["product", "service", "store", "category", "homepage"] = "product",
) -> UploadOut:
    if not ctx.user.has_role(RoleName.MERCHANT, RoleName.ADMIN, RoleName.SUPER_ADMIN):
        raise PermissionDenied("Only merchants and administrators can upload images.")
    # Read one byte past the limit so oversized files are rejected rather than truncated.
    content = await file.read(get_settings().upload_max_bytes + 1)
    return UploadOut(url=await asyncify(store_image)(content, folder=purpose))


class TicketIn(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=10, max_length=5000)
    merchant_order_id: uuid.UUID | None = None


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject: str
    body: str
    status: str
    admin_response: str | None
    merchant_order_id: uuid.UUID | None
    created_at: datetime


@support_router.post("/tickets", status_code=status.HTTP_201_CREATED)
async def create_ticket(body: TicketIn, ctx: CurrentAuth, db: DbSession) -> TicketOut:
    if body.merchant_order_id:
        mo = await db.get(MerchantOrder, body.merchant_order_id)
        if mo is None or mo.customer_user_id != ctx.user_id:
            raise NotFound("Order not found.")
    ticket = SupportTicket(
        user_id=ctx.user_id, subject=body.subject, body=body.body, merchant_order_id=body.merchant_order_id
    )
    db.add(ticket)
    await db.flush()
    return TicketOut.model_validate(ticket)


@support_router.get("/tickets")
async def list_tickets(ctx: CurrentAuth, db: DbSession, page: PageDep) -> Page[TicketOut]:
    stmt = (
        select(SupportTicket)
        .where(col(SupportTicket.user_id) == ctx.user_id)
        .order_by(col(SupportTicket.created_at).desc())
    )
    rows, total = await paginate(db, stmt, page)
    return Page(
        items=[TicketOut.model_validate(t) for t in rows], total=total, page=page.page, page_size=page.page_size
    )
