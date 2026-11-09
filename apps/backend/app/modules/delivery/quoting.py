"""Delivery quotes for checkout groups.

Loads each store's delivery configuration in bulk, asks the delivery provider for
every method the store offers, picks the customer's selection (or a sensible
default) and turns the chosen quote into an explicit ``DeliveryCharge``.

This module never imports the order service, so cart pricing can depend on it.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.admin.settings_service import DeliveryFinanceSettings, TaxSettings
from app.modules.delivery.models import (
    DeliveryMethod,
    DeliveryZone,
    FeeRecipient,
    StoreDeliverySettings,
)
from app.modules.delivery.pricing import NO_DELIVERY, DeliveryCharge, delivery_charge
from app.modules.delivery.providers.base import AddressSnapshot, DeliveryQuote, QuoteRequest
from app.modules.delivery.providers.registry import provider_for
from app.modules.merchants.models import Merchant, MerchantAddress
from app.modules.stores.models import Store

METHOD_PREFERENCE = (DeliveryMethod.DELIVERY, DeliveryMethod.PICKUP)
# Quote issues that only mean "not priced yet" while browsing the cart.
PENDING_ISSUES = frozenset({"address_required", "pickup_location_required"})


@dataclass(frozen=True)
class DeliverySelection:
    method: DeliveryMethod
    pickup_location_id: uuid.UUID | None = None


@dataclass(frozen=True)
class DeliveryContext:
    """The customer's delivery choices.

    ``strict`` is True at checkout: every group must have a fully priced, available
    delivery. While browsing the cart, missing choices only leave the fee pending.
    """

    address: AddressSnapshot | None = None
    selections: dict[uuid.UUID, DeliverySelection] = field(default_factory=dict)  # by store id
    strict: bool = False


@dataclass
class StoreDeliveryData:
    settings: StoreDeliverySettings
    zones: list[DeliveryZone]
    pickup_locations: list[MerchantAddress]


@dataclass
class GroupDelivery:
    """The delivery outcome of one checkout group."""

    method: DeliveryMethod
    charge: DeliveryCharge = NO_DELIVERY
    quote: DeliveryQuote | None = None
    options: list[DeliveryQuote] = field(default_factory=list)
    pending: bool = False  # fee not known yet (address / pickup point not chosen)
    issue: str | None = None  # blocking problem with the chosen method


def default_settings(store: Store) -> StoreDeliverySettings:
    return StoreDeliverySettings(store_id=store.id, merchant_id=store.merchant_id)


async def load_store_delivery(session: AsyncSession, stores: list[Store]) -> dict[uuid.UUID, StoreDeliveryData]:
    if not stores:
        return {}
    store_ids = [s.id for s in stores]
    merchant_ids = [s.merchant_id for s in stores]
    settings = {
        s.store_id: s
        for s in (
            await session.exec(select(StoreDeliverySettings).where(col(StoreDeliverySettings.store_id).in_(store_ids)))
        ).all()
    }
    zones: dict[uuid.UUID, list[DeliveryZone]] = {sid: [] for sid in store_ids}
    for zone in (
        await session.exec(
            select(DeliveryZone)
            .where(col(DeliveryZone.store_id).in_(store_ids), col(DeliveryZone.is_active).is_(True))
            .order_by(col(DeliveryZone.created_at))
        )
    ).all():
        zones[zone.store_id].append(zone)
    pickups: dict[uuid.UUID, list[MerchantAddress]] = {mid: [] for mid in merchant_ids}
    for loc in (
        await session.exec(
            select(MerchantAddress)
            .where(col(MerchantAddress.merchant_id).in_(merchant_ids), col(MerchantAddress.is_pickup_location))
            .order_by(col(MerchantAddress.is_primary).desc(), col(MerchantAddress.created_at))
        )
    ).all():
        pickups[loc.merchant_id].append(loc)
    return {
        s.id: StoreDeliveryData(
            settings=settings.get(s.id) or default_settings(s),
            zones=zones[s.id],
            pickup_locations=pickups[s.merchant_id],
        )
        for s in stores
    }


def offered_methods(data: StoreDeliveryData) -> list[DeliveryMethod]:
    methods = []
    if data.settings.delivery_enabled and data.zones:
        methods.append(DeliveryMethod.DELIVERY)
    if data.settings.pickup_enabled and data.pickup_locations:
        methods.append(DeliveryMethod.PICKUP)
    return methods


def _vat_rate(recipient: FeeRecipient, merchant: Merchant, tax: TaxSettings) -> Decimal:
    if not tax.vat_applies_to_shipping:
        return Decimal("0")
    if recipient == FeeRecipient.MERCHANT and not merchant.is_vat_registered:
        return Decimal("0")
    # The platform is VAT-registered; when it receives delivery fees it charges VAT on them.
    return tax.vat_rate


async def quote_group(
    *,
    store: Store,
    merchant: Merchant,
    data: StoreDeliveryData,
    items_net: int,
    context: DeliveryContext,
    tax: TaxSettings,
    finance: DeliveryFinanceSettings,
) -> GroupDelivery:
    selection = context.selections.get(store.id)
    options: list[DeliveryQuote] = []
    for method in METHOD_PREFERENCE:
        provider = provider_for(method)
        options.append(
            await provider.quote(
                QuoteRequest(
                    method=method,
                    store=store,
                    settings=data.settings,
                    zones=data.zones,
                    pickup_locations=data.pickup_locations,
                    items_net=items_net,
                    address=context.address,
                    pickup_location_id=selection.pickup_location_id
                    if selection and selection.method == method
                    else None,
                )
            )
        )
    by_method = {q.method: q for q in options}
    offered = offered_methods(data)

    if selection is not None:
        chosen = by_method[selection.method]
    else:
        usable = [q for q in options if q.method in offered and (q.available or (q.issue in PENDING_ISSUES))]
        chosen = usable[0] if usable else by_method[offered[0] if offered else DeliveryMethod.DELIVERY]

    result = GroupDelivery(method=chosen.method, quote=chosen, options=options)
    if not chosen.available:
        if not context.strict and chosen.issue in PENDING_ISSUES:
            result.pending = True
        else:
            result.issue = chosen.issue or "delivery_unavailable"
        return result
    result.charge = delivery_charge(
        method=chosen.method,
        fee=chosen.fee,
        fee_waived=chosen.fee_waived,
        terms=chosen.terms,
        vat_rate=_vat_rate(chosen.terms.fee_recipient, merchant, tax),
        commission_on_delivery=finance.commission_applies_to == "ITEMS_AND_DELIVERY",
        commission_rate=finance.delivery_commission_rate,
    )
    return result
