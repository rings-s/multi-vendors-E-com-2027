"""Notification service: in-app notifications plus transactional email (outbox).

Notifications are written in the same database transaction as the business change.
Emails are dispatched afterwards by the maintenance loop (``dispatch_pending_emails``),
so an email is never sent for a change that was rolled back.
"""

import uuid
from datetime import timedelta
from typing import Any

from sqlmodel import col, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.i18n import render
from app.core.security import utcnow
from app.infrastructure.email import send_email
from app.modules.auth.models import User
from app.modules.notifications.models import Notification, NotificationType


async def notify(
    session: AsyncSession, user_id: uuid.UUID, notification_type: NotificationType, data: dict[str, Any]
) -> Notification:
    notification = Notification(user_id=user_id, type=notification_type.value, data=data)
    session.add(notification)
    return notification


async def dispatch_pending_emails(session: AsyncSession, limit: int = 50) -> int:
    if not get_settings().smtp_host:
        return 0
    cutoff = utcnow() - timedelta(days=1)
    rows = (
        await session.exec(
            select(Notification, User)
            .join(User, col(User.id) == col(Notification.user_id))
            .where(col(Notification.email_sent_at).is_(None), col(Notification.created_at) >= cutoff)
            .order_by(col(Notification.created_at))
            .limit(limit)
            .with_for_update(of=Notification, skip_locked=True)
        )
    ).all()
    sent = 0
    for notification, user in rows:
        title, body = render(notification.type, user.preferred_language, notification.data)
        if await send_email(user.email, title, body):
            sent += 1
        await session.exec(
            update(Notification).where(col(Notification.id) == notification.id).values(email_sent_at=utcnow())
        )
    return sent
