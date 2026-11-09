"""Audit logging helper (append-only)."""

import uuid
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.admin.models import AuditLog


async def record_audit(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | str | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            before=_jsonable(before),
            after=_jsonable(after),
            ip_address=ip_address,
        )
    )


def _jsonable(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        k: (v if isinstance(v, (str, int, float, bool, type(None), list, dict)) else str(v)) for k, v in value.items()
    }
