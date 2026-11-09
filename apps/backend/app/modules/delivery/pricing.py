"""Delivery fee calculation (pure functions, no database access).

Delivery fees are calculated independently from product prices and commissions:
the only input from the cart is the item value after discounts, used to apply a
zone's free-delivery threshold.

Zone matching
-------------
A zone covers all of Saudi Arabia (no region), a region, specific cities of a region,
or specific districts of those cities. The most specific active zone that matches the
address applies (district > city > region > nationwide). Ties are broken by the lowest
fee, then the fastest promise, then name and id, so the result is deterministic.

Place names are compared after normalization (Unicode NFKC, case folding, Arabic
letter variants unified, punctuation and repeated spaces removed), so ``"Al-Olaya"``
matches ``"al olaya"`` and ``"الرياض"`` matches ``"الریاض"``. Merchants list every
spelling they accept (e.g. ``["Riyadh", "الرياض"]``).
"""

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.core.money import percentage_of
from app.modules.delivery.models import CostBearer, DeliveryMethod, FeeRecipient

_ARABIC_VARIANTS = str.maketrans(
    {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ی": "ي", "ة": "ه", "ک": "ك", "ـ": ""}
)
_PUNCTUATION = re.compile(r"[\-_'’.,()/]+")
_SPACES = re.compile(r"\s+")


def normalize_place(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value).casefold().translate(_ARABIC_VARIANTS)
    text = _PUNCTUATION.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def normalize_places(values: Iterable[str]) -> list[str]:
    """Normalized, de-duplicated, order-preserving list (empty names dropped)."""
    seen: dict[str, None] = {}
    for value in values:
        key = normalize_place(value)
        if key:
            seen.setdefault(key, None)
    return list(seen)


class ZoneLike(Protocol):
    @property
    def id(self) -> object: ...
    @property
    def name(self) -> str: ...
    @property
    def region(self) -> str | None: ...
    @property
    def cities(self) -> list[str]: ...
    @property
    def districts(self) -> list[str]: ...
    @property
    def fee(self) -> int: ...
    @property
    def free_delivery_threshold(self) -> int | None: ...
    @property
    def eta_min_minutes(self) -> int: ...
    @property
    def eta_max_minutes(self) -> int: ...
    @property
    def is_active(self) -> bool: ...


@dataclass(frozen=True)
class Place:
    region: str
    city: str
    district: str = ""


def zone_specificity(zone: ZoneLike, place: Place) -> int | None:
    """3 = district, 2 = city, 1 = region, 0 = nationwide; ``None`` if it does not match."""
    if zone.region is None:
        return 0
    if zone.region != place.region:
        return None
    if not zone.cities:
        return 1
    if normalize_place(place.city) not in normalize_places(zone.cities):
        return None
    if not zone.districts:
        return 2
    if normalize_place(place.district) not in normalize_places(zone.districts):
        return None
    return 3


def match_zone[Z: ZoneLike](zones: Sequence[Z], place: Place) -> Z | None:
    candidates: list[tuple[int, Z]] = []
    for zone in zones:
        if not zone.is_active:
            continue
        specificity = zone_specificity(zone, place)
        if specificity is not None:
            candidates.append((specificity, zone))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (-c[0], c[1].fee, c[1].eta_max_minutes, c[1].name, str(c[1].id)))
    return candidates[0][1]


@dataclass(frozen=True)
class ZoneFee:
    base_fee: int  # the zone's configured fee
    fee: int  # what the customer pays (0 when the free-delivery threshold is reached)

    @property
    def waived(self) -> int:
        return self.base_fee - self.fee


def zone_fee(zone: ZoneLike, items_net: int) -> ZoneFee:
    threshold = zone.free_delivery_threshold
    if threshold is not None and items_net >= threshold:
        return ZoneFee(base_fee=zone.fee, fee=0)
    return ZoneFee(base_fee=zone.fee, fee=zone.fee)


# -- financial split of a delivery charge ------------------------------------------------


@dataclass(frozen=True)
class DeliveryTerms:
    """Who receives the fee and who bears the cost; defined by the delivery provider."""

    fee_recipient: FeeRecipient
    cost_bearer: CostBearer


@dataclass(frozen=True)
class DeliveryCharge:
    """The delivery part of a merchant order, in integer halalas.

    ``gross = fee + vat`` is what the customer pays for delivery. It is split into the
    platform's share (delivery commission, or the whole charge when the platform
    receives delivery fees) and the merchant's share.
    """

    method: DeliveryMethod
    fee: int
    vat: int
    fee_waived: int
    commission: int
    commission_rate: Decimal | None
    fee_recipient: FeeRecipient | None
    cost_bearer: CostBearer | None

    @property
    def gross(self) -> int:
        return self.fee + self.vat

    @property
    def platform_share(self) -> int:
        if self.fee_recipient == FeeRecipient.PLATFORM:
            return self.gross
        return self.commission

    @property
    def merchant_share(self) -> int:
        return self.gross - self.platform_share


NO_DELIVERY = DeliveryCharge(
    method=DeliveryMethod.NONE,
    fee=0,
    vat=0,
    fee_waived=0,
    commission=0,
    commission_rate=None,
    fee_recipient=None,
    cost_bearer=None,
)


def delivery_charge(
    *,
    method: DeliveryMethod,
    fee: int,
    fee_waived: int,
    terms: DeliveryTerms,
    vat_rate: Decimal,
    commission_on_delivery: bool,
    commission_rate: Decimal,
) -> DeliveryCharge:
    """Split a delivery fee explicitly.

    * VAT is ``vat_rate`` % of the fee (``vat_rate`` is 0 when VAT does not apply).
    * Delivery commission is charged only when the platform is configured to take
      commission on delivery fees AND the merchant receives the fee; it is a
      percentage of the fee excluding VAT, exactly like item commission.
    """
    if method == DeliveryMethod.NONE:
        return NO_DELIVERY
    if fee < 0 or fee_waived < 0:
        raise ValueError("Delivery amounts cannot be negative.")
    vat = percentage_of(fee, vat_rate) if fee else 0
    takes_commission = commission_on_delivery and terms.fee_recipient == FeeRecipient.MERCHANT
    commission = percentage_of(fee, commission_rate) if takes_commission and fee else 0
    return DeliveryCharge(
        method=method,
        fee=fee,
        vat=vat,
        fee_waived=fee_waived,
        commission=min(commission, fee),
        commission_rate=commission_rate if takes_commission else None,
        fee_recipient=terms.fee_recipient,
        cost_bearer=terms.cost_bearer,
    )
