"""/api/v1/customers and /api/v1/customers/addresses"""

import uuid

from fastapi import APIRouter, status

from app.api.deps import CustomerAuth
from app.database.session import DbSession
from app.modules.customers import service
from app.modules.customers.schemas import (
    AddressCreate,
    AddressOut,
    AddressUpdate,
    CustomerMe,
    PreferencesOut,
    PreferencesUpdate,
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/me")
async def get_me(ctx: CustomerAuth, db: DbSession) -> CustomerMe:
    profile, prefs = await service.get_profile(db, ctx.user_id)
    return CustomerMe(
        id=ctx.user.id,
        email=ctx.user.email,
        full_name=ctx.user.full_name,
        phone=ctx.user.phone,
        preferred_language=ctx.user.preferred_language,
        display_name=profile.display_name,
        preferences=PreferencesOut.model_validate(prefs),
    )


@router.patch("/me/preferences")
async def update_preferences(body: PreferencesUpdate, ctx: CustomerAuth, db: DbSession) -> PreferencesOut:
    _, prefs = await service.get_profile(db, ctx.user_id)
    if body.marketing_emails is not None:
        prefs.marketing_emails = body.marketing_emails
    if body.notification_settings is not None:
        prefs.notification_settings = body.notification_settings
    await db.flush()
    return PreferencesOut.model_validate(prefs)


@router.get("/addresses")
async def list_addresses(ctx: CustomerAuth, db: DbSession) -> list[AddressOut]:
    return [AddressOut.model_validate(a) for a in await service.list_addresses(db, ctx.user_id)]


@router.post("/addresses", status_code=status.HTTP_201_CREATED)
async def create_address(body: AddressCreate, ctx: CustomerAuth, db: DbSession) -> AddressOut:
    return AddressOut.model_validate(await service.create_address(db, ctx.user_id, body))


@router.get("/addresses/{address_id}")
async def get_address(address_id: uuid.UUID, ctx: CustomerAuth, db: DbSession) -> AddressOut:
    return AddressOut.model_validate(await service.get_address(db, ctx.user_id, address_id))


@router.patch("/addresses/{address_id}")
async def update_address(address_id: uuid.UUID, body: AddressUpdate, ctx: CustomerAuth, db: DbSession) -> AddressOut:
    return AddressOut.model_validate(await service.update_address(db, ctx.user_id, address_id, body))


@router.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(address_id: uuid.UUID, ctx: CustomerAuth, db: DbSession) -> None:
    await service.delete_address(db, ctx.user_id, address_id)
