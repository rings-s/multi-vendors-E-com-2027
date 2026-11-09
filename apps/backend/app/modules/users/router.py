"""/api/v1/users — the authenticated user's own account."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentAuth
from app.core.validators import SaudiMobile
from app.database.session import DbSession
from app.modules.auth import service as auth_service
from app.modules.auth.router import user_public
from app.modules.auth.schemas import MessageResponse, Password, UserPublic

router = APIRouter(prefix="/users", tags=["users"])


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: SaudiMobile | None = None
    preferred_language: Literal["ar", "en"] | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: Password


@router.get("/me")
async def get_me(ctx: CurrentAuth) -> UserPublic:
    return user_public(ctx.user)


@router.patch("/me")
async def update_me(body: UserUpdate, ctx: CurrentAuth, db: DbSession) -> UserPublic:
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(ctx.user, field, value)
    await db.flush()
    return user_public(ctx.user)


@router.post("/me/password")
async def change_password(body: PasswordChange, ctx: CurrentAuth, db: DbSession) -> MessageResponse:
    await auth_service.change_password(db, ctx.user, body.current_password, body.new_password, ctx.session_id)
    return MessageResponse(message="Password changed. Other sessions were signed out.")
