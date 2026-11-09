"""Authentication: registration, login, refresh-token rotation, sessions,
email verification and password reset."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

import structlog
from sqlmodel import col, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.errors import Conflict, NotAuthenticated, ValidationFailed
from app.core.i18n import render
from app.core.security import (
    create_access_token,
    generate_token,
    hash_password,
    hash_password_async,
    hash_token,
    password_needs_rehash,
    utcnow,
    verify_password_async,
)
from app.infrastructure.email import send_email
from app.modules.auth.models import (
    RefreshToken,
    Role,
    RoleName,
    TokenPurpose,
    User,
    UserActionToken,
    UserSession,
)
from app.modules.customers.models import CustomerPreference, CustomerProfile

log = structlog.get_logger(__name__)

# Pre-computed hash so failed logins for unknown emails take the same time.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


@dataclass
class IssuedTokens:
    access_token: str
    refresh_token: str
    session_id: uuid.UUID
    expires_in: int


async def get_role(session: AsyncSession, name: RoleName) -> Role:
    role = (await session.exec(select(Role).where(Role.name == name.value))).first()
    if role is None:
        raise RuntimeError(f"Role {name} is not seeded; run migrations.")
    return role


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str,
    phone: str | None,
    roles: list[RoleName],
    preferred_language: str = "ar",
) -> User:
    email = email.strip().lower()
    if (await session.exec(select(User.id).where(User.email == email))).first():
        raise Conflict("An account with this email already exists.", code="email_taken")
    user = User(
        email=email,
        password_hash=await hash_password_async(password),
        full_name=full_name.strip(),
        phone=phone,
        preferred_language=preferred_language,
        roles=[await get_role(session, r) for r in roles],
    )
    session.add(user)
    await session.flush()
    if RoleName.CUSTOMER in roles:
        session.add(CustomerProfile(user_id=user.id, display_name=user.full_name))
        session.add(CustomerPreference(user_id=user.id, notification_settings={}))
    await issue_email_verification(session, user)
    return user


async def _issue_action_token(session: AsyncSession, user: User, purpose: TokenPurpose, ttl: int) -> str:
    await session.exec(
        update(UserActionToken)
        .where(
            col(UserActionToken.user_id) == user.id,
            col(UserActionToken.purpose) == purpose.value,
            col(UserActionToken.used_at).is_(None),
        )
        .values(used_at=utcnow())
    )
    token = generate_token()
    session.add(
        UserActionToken(
            user_id=user.id,
            purpose=purpose.value,
            token_hash=hash_token(token),
            expires_at=utcnow() + timedelta(seconds=ttl),
        )
    )
    return token


async def _send_link(user: User, message_type: str, path: str, token: str) -> None:
    settings = get_settings()
    link = f"{settings.frontend_url}{path}?token={token}"
    if not settings.is_production:
        log.info("auth_link_generated", type=message_type, email=user.email, link=link)
    title, body = render(message_type, user.preferred_language, {"link": link})
    await send_email(user.email, title, body)


async def issue_email_verification(session: AsyncSession, user: User) -> str:
    token = await _issue_action_token(
        session, user, TokenPurpose.EMAIL_VERIFICATION, get_settings().email_token_ttl_seconds
    )
    await _send_link(user, "email_verification", "/verify-email", token)
    return token


async def _consume_action_token(session: AsyncSession, token: str, purpose: TokenPurpose) -> User:
    record = (
        await session.exec(
            select(UserActionToken)
            .where(UserActionToken.token_hash == hash_token(token), UserActionToken.purpose == purpose.value)
            .with_for_update()
        )
    ).first()
    if record is None or record.used_at is not None or record.expires_at < utcnow():
        raise ValidationFailed("The link is invalid or has expired.", code="invalid_token")
    record.used_at = utcnow()
    user = await session.get(User, record.user_id)
    if user is None or not user.is_active:
        raise ValidationFailed("The link is invalid or has expired.", code="invalid_token")
    return user


async def verify_email(session: AsyncSession, token: str) -> User:
    user = await _consume_action_token(session, token, TokenPurpose.EMAIL_VERIFICATION)
    user.email_verified_at = user.email_verified_at or utcnow()
    return user


async def request_password_reset(session: AsyncSession, email: str) -> str | None:
    user = (await session.exec(select(User).where(User.email == email.strip().lower()))).first()
    if user is None or not user.is_active:
        return None  # never reveal whether an account exists
    token = await _issue_action_token(
        session, user, TokenPurpose.PASSWORD_RESET, get_settings().password_reset_ttl_seconds
    )
    await _send_link(user, "password_reset", "/reset-password", token)
    return token


async def confirm_password_reset(session: AsyncSession, token: str, new_password: str) -> None:
    user = await _consume_action_token(session, token, TokenPurpose.PASSWORD_RESET)
    user.password_hash = await hash_password_async(new_password)
    await revoke_all_sessions(session, user.id, reason="password_reset")


async def change_password(session: AsyncSession, user: User, current: str, new: str, keep_session: uuid.UUID) -> None:
    if not await verify_password_async(user.password_hash, current):
        raise ValidationFailed("Current password is incorrect.", code="invalid_password")
    user.password_hash = await hash_password_async(new)
    await revoke_all_sessions(session, user.id, reason="password_changed", except_session=keep_session)


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = (await session.exec(select(User).where(User.email == email.strip().lower()))).first()
    if user is None:
        await verify_password_async(_DUMMY_HASH, password)
        raise NotAuthenticated("Invalid email or password.", code="invalid_credentials")
    if not await verify_password_async(user.password_hash, password):
        raise NotAuthenticated("Invalid email or password.", code="invalid_credentials")
    if not user.is_active:
        raise NotAuthenticated("This account is disabled.", code="account_disabled")
    if password_needs_rehash(user.password_hash):
        user.password_hash = await hash_password_async(password)
    return user


async def _new_refresh_token(session: AsyncSession, session_id: uuid.UUID) -> str:
    token = generate_token(48)
    session.add(
        RefreshToken(
            session_id=session_id,
            token_hash=hash_token(token),
            expires_at=utcnow() + timedelta(seconds=get_settings().refresh_token_ttl_seconds),
        )
    )
    return token


async def start_session(session: AsyncSession, user: User, *, ip: str | None, user_agent: str | None) -> IssuedTokens:
    user_session = UserSession(
        user_id=user.id, ip_address=ip, user_agent=(user_agent or "")[:512], last_seen_at=utcnow()
    )
    session.add(user_session)
    await session.flush()
    user.last_login_at = utcnow()
    refresh = await _new_refresh_token(session, user_session.id)
    return IssuedTokens(
        access_token=create_access_token(user_id=user.id, session_id=user_session.id, roles=user.role_names),
        refresh_token=refresh,
        session_id=user_session.id,
        expires_in=get_settings().access_token_ttl_seconds,
    )


async def rotate_refresh_token(session: AsyncSession, token: str) -> IssuedTokens:
    """Rotate a refresh token. Reuse of an already-rotated token revokes the session."""
    record = (
        await session.exec(select(RefreshToken).where(RefreshToken.token_hash == hash_token(token)).with_for_update())
    ).first()
    if record is None:
        raise NotAuthenticated("Invalid refresh token.", code="invalid_refresh_token")
    user_session = await session.get(UserSession, record.session_id, with_for_update=True)
    if user_session is None or user_session.revoked_at is not None:
        raise NotAuthenticated("Session has ended.", code="session_revoked")
    if record.used_at is not None or record.revoked_at is not None:
        # Token reuse: a stolen token may be in use. Kill the whole session.
        user_session.revoked_at = utcnow()
        user_session.revoked_reason = "refresh_token_reuse"
        log.warning("refresh_token_reuse_detected", session_id=str(user_session.id))
        # Persist the revocation even though the request fails.
        await session.commit()
        raise NotAuthenticated("Refresh token reuse detected; session revoked.", code="refresh_token_reuse")
    if record.expires_at < utcnow():
        raise NotAuthenticated("Refresh token expired.", code="refresh_token_expired")
    user = await session.get(User, user_session.user_id)
    if user is None or not user.is_active:
        raise NotAuthenticated("This account is disabled.", code="account_disabled")
    record.used_at = utcnow()
    user_session.last_seen_at = utcnow()
    refresh = await _new_refresh_token(session, user_session.id)
    return IssuedTokens(
        access_token=create_access_token(user_id=user.id, session_id=user_session.id, roles=user.role_names),
        refresh_token=refresh,
        session_id=user_session.id,
        expires_in=get_settings().access_token_ttl_seconds,
    )


async def revoke_session(session: AsyncSession, session_id: uuid.UUID, reason: str = "logout") -> None:
    now = utcnow()
    await session.exec(
        update(UserSession)
        .where(col(UserSession.id) == session_id, col(UserSession.revoked_at).is_(None))
        .values(revoked_at=now, revoked_reason=reason)
    )
    await session.exec(
        update(RefreshToken)
        .where(col(RefreshToken.session_id) == session_id, col(RefreshToken.revoked_at).is_(None))
        .values(revoked_at=now)
    )


async def revoke_all_sessions(
    session: AsyncSession, user_id: uuid.UUID, *, reason: str, except_session: uuid.UUID | None = None
) -> None:
    stmt = select(UserSession.id).where(UserSession.user_id == user_id, col(UserSession.revoked_at).is_(None))
    if except_session is not None:
        stmt = stmt.where(UserSession.id != except_session)
    for session_id in (await session.exec(stmt)).all():
        await revoke_session(session, session_id, reason)
