"""Shared API dependencies: authentication, RBAC, merchant tenant scope, rate limits.

Authorization is always enforced here, in the backend. Merchant-scoped endpoints
derive the merchant from the authenticated user, never from request input.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import select

from app.core.config import get_settings
from app.core.errors import NotAuthenticated, PermissionDenied, RateLimited
from app.core.security import decode_access_token
from app.database.session import DbSession
from app.infrastructure.redis import hit_rate_limit
from app.modules.auth.models import RoleName, User, UserSession
from app.modules.auth.permissions import Perm
from app.modules.merchants.models import Merchant

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "x-csrf-token"


@dataclass
class AuthContext:
    user: User
    session_id: uuid.UUID

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id


def _extract_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return request.cookies.get(ACCESS_COOKIE)


async def _optional_auth(request: Request, db: DbSession) -> AuthContext | None:
    token = _extract_token(request)
    if not token:
        return None
    payload = decode_access_token(token)
    if payload is None:
        raise NotAuthenticated("Invalid or expired access token.", code="invalid_token")
    try:
        user_id = uuid.UUID(payload["sub"])
        session_id = uuid.UUID(payload["sid"])
    except (KeyError, ValueError) as exc:
        raise NotAuthenticated("Invalid access token.", code="invalid_token") from exc
    user_session = await db.get(UserSession, session_id)
    if user_session is None or user_session.revoked_at is not None or user_session.user_id != user_id:
        raise NotAuthenticated("Session has ended.", code="session_revoked")
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise NotAuthenticated("This account is disabled.", code="account_disabled")
    return AuthContext(user=user, session_id=session_id)


async def _require_auth(ctx: Annotated[AuthContext | None, Depends(_optional_auth)]) -> AuthContext:
    if ctx is None:
        raise NotAuthenticated("Authentication required.")
    return ctx


OptionalAuth = Annotated[AuthContext | None, Depends(_optional_auth)]
CurrentAuth = Annotated[AuthContext, Depends(_require_auth)]


def require_roles(*roles: RoleName) -> Callable[[AuthContext], Awaitable[AuthContext]]:
    async def dependency(ctx: CurrentAuth) -> AuthContext:
        if not ctx.user.has_role(*roles):
            raise PermissionDenied("You do not have access to this resource.")
        return ctx

    return dependency


def require_permission(*perms: Perm) -> Callable[[AuthContext], Awaitable[AuthContext]]:
    async def dependency(ctx: CurrentAuth) -> AuthContext:
        if not ctx.user.has_role(RoleName.ADMIN, RoleName.SUPER_ADMIN):
            raise PermissionDenied("Administrator access required.")
        missing = {p.value for p in perms} - ctx.user.permission_codes
        if missing:
            raise PermissionDenied("You do not have permission to perform this action.", details=sorted(missing))
        return ctx

    return dependency


CustomerAuth = Annotated[AuthContext, Depends(require_roles(RoleName.CUSTOMER))]
AdminAuth = Annotated[AuthContext, Depends(require_roles(RoleName.ADMIN, RoleName.SUPER_ADMIN))]


@dataclass
class MerchantContext:
    auth: AuthContext
    merchant: Merchant

    @property
    def merchant_id(self) -> uuid.UUID:
        return self.merchant.id


async def _current_merchant(
    ctx: Annotated[AuthContext, Depends(require_roles(RoleName.MERCHANT))], db: DbSession
) -> MerchantContext:
    merchant = (await db.exec(select(Merchant).where(Merchant.owner_user_id == ctx.user.id))).first()
    if merchant is None:
        raise PermissionDenied("No merchant account is linked to this user.")
    return MerchantContext(auth=ctx, merchant=merchant)


CurrentMerchant = Annotated[MerchantContext, Depends(_current_merchant)]


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, per_minute: int | None = None) -> Callable[[Request], Awaitable[None]]:
    async def dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        limit = per_minute or settings.auth_rate_limit_per_minute
        if await hit_rate_limit(f"{scope}:{client_ip(request)}", limit, 60):
            raise RateLimited("Too many requests. Please try again later.")

    return dependency
