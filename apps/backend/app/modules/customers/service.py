import uuid

from sqlmodel import col, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import NotFound
from app.modules.customers.models import CustomerAddress, CustomerPreference, CustomerProfile
from app.modules.customers.schemas import AddressCreate, AddressUpdate


async def get_profile(session: AsyncSession, user_id: uuid.UUID) -> tuple[CustomerProfile, CustomerPreference]:
    profile = (await session.exec(select(CustomerProfile).where(CustomerProfile.user_id == user_id))).first()
    if profile is None:
        profile = CustomerProfile(user_id=user_id)
        session.add(profile)
    prefs = (await session.exec(select(CustomerPreference).where(CustomerPreference.user_id == user_id))).first()
    if prefs is None:
        prefs = CustomerPreference(user_id=user_id, marketing_emails=False, notification_settings={})
        session.add(prefs)
    await session.flush()
    return profile, prefs


async def list_addresses(session: AsyncSession, user_id: uuid.UUID) -> list[CustomerAddress]:
    rows = await session.exec(
        select(CustomerAddress)
        .where(CustomerAddress.user_id == user_id, col(CustomerAddress.is_deleted).is_(False))
        .order_by(col(CustomerAddress.is_default).desc(), col(CustomerAddress.created_at))
    )
    return list(rows.all())


async def get_address(session: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID) -> CustomerAddress:
    address = await session.get(CustomerAddress, address_id)
    if address is None or address.user_id != user_id or address.is_deleted:
        raise NotFound("Address not found.")
    return address


async def _clear_default(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.exec(
        update(CustomerAddress)
        .where(col(CustomerAddress.user_id) == user_id, col(CustomerAddress.is_default).is_(True))
        .values(is_default=False)
    )


async def create_address(session: AsyncSession, user_id: uuid.UUID, data: AddressCreate) -> CustomerAddress:
    existing = await list_addresses(session, user_id)
    make_default = data.is_default or not existing
    if make_default:
        await _clear_default(session, user_id)
    address = CustomerAddress(user_id=user_id, **data.model_dump(exclude={"is_default"}), is_default=make_default)
    session.add(address)
    await session.flush()
    return address


async def update_address(
    session: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID, data: AddressUpdate
) -> CustomerAddress:
    address = await get_address(session, user_id, address_id)
    values = data.model_dump(exclude_unset=True, exclude_none=True)
    if values.pop("clear_location", False):
        address.latitude = None
        address.longitude = None
    if values.pop("is_default", False):
        await _clear_default(session, user_id)
        address.is_default = True
    for key, value in values.items():
        setattr(address, key, value)
    await session.flush()
    return address


async def delete_address(session: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID) -> None:
    address = await get_address(session, user_id, address_id)
    address.is_deleted = True
    address.is_default = False
    await session.flush()
