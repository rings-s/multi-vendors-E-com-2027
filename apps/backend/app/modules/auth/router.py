"""/api/v1/auth"""

import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from sqlmodel import col, select

from app.api.deps import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE, CurrentAuth, client_ip, rate_limit
from app.core.config import get_settings
from app.core.errors import NotAuthenticated, NotFound
from app.core.security import generate_token
from app.database.session import DbSession
from app.modules.auth import service
from app.modules.auth.models import RoleName, User, UserSession
from app.modules.auth.schemas import (
    CsrfResponse,
    EmailRequest,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirm,
    RefreshRequest,
    RegisterRequest,
    SessionOut,
    TokenRequest,
    TokenResponse,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])

AuthRateLimit = Depends(rate_limit("auth"))


def user_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        roles=user.role_names,
        preferred_language=user.preferred_language,
        email_verified=user.email_verified_at is not None,
        created_at=user.created_at,
    )


def set_auth_cookies(response: Response, tokens: service.IssuedTokens) -> None:
    settings = get_settings()
    secure, domain = settings.cookie_secure, settings.cookie_domain
    response.set_cookie(
        ACCESS_COOKIE,
        tokens.access_token,
        max_age=tokens.expires_in,
        httponly=True,
        path="/",
        secure=secure,
        samesite="lax",
        domain=domain,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        httponly=True,
        path="/api/v1/auth",
        secure=secure,
        samesite="lax",
        domain=domain,
    )
    response.set_cookie(
        CSRF_COOKIE, generate_token(24), httponly=False, path="/", secure=secure, samesite="lax", domain=domain
    )


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=settings.cookie_domain)
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth", domain=settings.cookie_domain)
    response.delete_cookie(CSRF_COOKIE, path="/", domain=settings.cookie_domain)


def _body_refresh_token(request: Request, tokens: service.IssuedTokens) -> str | None:
    """Browsers get the refresh token only as an HTTP-only cookie. Non-browser
    clients opt in to receiving it in the body with ``X-Client-Type: native``."""
    return tokens.refresh_token if request.headers.get("x-client-type") == "native" else None


async def _login_response(db: DbSession, user: User, request: Request, response: Response) -> TokenResponse:
    tokens = await service.start_session(db, user, ip=client_ip(request), user_agent=request.headers.get("user-agent"))
    set_auth_cookies(response, tokens)
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        refresh_token=_body_refresh_token(request, tokens),
        user=user_public(user),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, dependencies=[AuthRateLimit])
async def register_customer(
    body: RegisterRequest, request: Request, response: Response, db: DbSession
) -> TokenResponse:
    user = await service.create_user(
        db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        phone=body.phone,
        roles=[RoleName.CUSTOMER],
        preferred_language=body.preferred_language,
    )
    return await _login_response(db, user, request, response)


@router.post("/login", dependencies=[AuthRateLimit])
async def login(body: LoginRequest, request: Request, response: Response, db: DbSession) -> TokenResponse:
    user = await service.authenticate(db, body.email, body.password)
    return await _login_response(db, user, request, response)


@router.post("/refresh", dependencies=[AuthRateLimit])
async def refresh(
    request: Request, response: Response, db: DbSession, body: RefreshRequest | None = None
) -> TokenResponse:
    token = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise NotAuthenticated("Refresh token required.", code="invalid_refresh_token")
    tokens = await service.rotate_refresh_token(db, token)
    set_auth_cookies(response, tokens)
    user_session = await db.get(UserSession, tokens.session_id)
    assert user_session is not None
    user = await db.get(User, user_session.user_id)
    assert user is not None
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        refresh_token=_body_refresh_token(request, tokens),
        user=user_public(user),
    )


@router.post("/logout")
async def logout(ctx: CurrentAuth, response: Response, db: DbSession) -> MessageResponse:
    await service.revoke_session(db, ctx.session_id)
    clear_auth_cookies(response)
    return MessageResponse(message="Logged out.")


@router.post("/logout-all")
async def logout_all(ctx: CurrentAuth, response: Response, db: DbSession) -> MessageResponse:
    await service.revoke_all_sessions(db, ctx.user_id, reason="logout_all")
    clear_auth_cookies(response)
    return MessageResponse(message="All sessions ended.")


@router.get("/csrf")
async def csrf(response: Response) -> CsrfResponse:
    settings = get_settings()
    token = generate_token(24)
    response.set_cookie(
        CSRF_COOKIE,
        token,
        httponly=False,
        path="/",
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
    )
    return CsrfResponse(csrf_token=token)


@router.get("/me")
async def me(ctx: CurrentAuth) -> UserPublic:
    return user_public(ctx.user)


@router.post("/verify-email", dependencies=[AuthRateLimit])
async def verify_email(body: TokenRequest, db: DbSession) -> MessageResponse:
    await service.verify_email(db, body.token)
    return MessageResponse(message="Email verified.")


@router.post("/verify-email/resend", dependencies=[AuthRateLimit])
async def resend_verification(ctx: CurrentAuth, db: DbSession) -> MessageResponse:
    if ctx.user.email_verified_at is None:
        await service.issue_email_verification(db, ctx.user)
    return MessageResponse(message="If your email is not verified, a new link has been sent.")


@router.post("/password-reset/request", dependencies=[AuthRateLimit])
async def password_reset_request(body: EmailRequest, db: DbSession) -> MessageResponse:
    await service.request_password_reset(db, body.email)
    return MessageResponse(message="If an account exists for this email, a reset link has been sent.")


@router.post("/password-reset/confirm", dependencies=[AuthRateLimit])
async def password_reset_confirm(body: PasswordResetConfirm, db: DbSession) -> MessageResponse:
    await service.confirm_password_reset(db, body.token, body.new_password)
    return MessageResponse(message="Password updated. Please sign in again.")


@router.get("/sessions")
async def list_sessions(ctx: CurrentAuth, db: DbSession) -> list[SessionOut]:
    rows = await db.exec(
        select(UserSession)
        .where(UserSession.user_id == ctx.user_id, col(UserSession.revoked_at).is_(None))
        .order_by(col(UserSession.created_at).desc())
    )
    return [SessionOut.model_validate(s).model_copy(update={"current": s.id == ctx.session_id}) for s in rows.all()]


@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: uuid.UUID, ctx: CurrentAuth, db: DbSession) -> MessageResponse:
    user_session = await db.get(UserSession, session_id)
    if user_session is None or user_session.user_id != ctx.user_id:
        raise NotFound("Session not found.")
    await service.revoke_session(db, session_id, reason="revoked_by_user")
    return MessageResponse(message="Session revoked.")
