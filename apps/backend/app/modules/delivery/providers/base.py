"""Provider-independent delivery interface.

A *delivery provider* is whoever performs the delivery: the merchant itself (MVP),
the platform's own drivers, or a third-party courier. Orders and checkout only talk
to this interface; provider-specific request/response formats stay inside each
adapter, exactly like payment providers.

Adding a provider (e.g. platform drivers or a courier API) means implementing
``DeliveryProvider`` and registering it in ``registry.py``; the order domain, the
financial split (driven by ``terms``) and the delivery records do not change.
"""

import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.modules.delivery.models import DeliveryMethod, DeliveryStatus
from app.modules.delivery.pricing import DeliveryTerms

if TYPE_CHECKING:
    from app.modules.delivery.models import Delivery, DeliveryZone, StoreDeliverySettings
    from app.modules.merchants.models import MerchantAddress
    from app.modules.stores.models import Store


@dataclass(frozen=True)
class ProviderCapabilities:
    """What a provider really supports. Nothing is simulated: a capability that is
    False is simply not offered in the API or the dashboards."""

    manual_status_updates: bool  # the merchant moves the delivery through its statuses
    driver_assignment: bool = False
    live_tracking: bool = False
    proof_of_delivery: bool = False
    status_webhooks: bool = False


@dataclass(frozen=True)
class AddressSnapshot:
    recipient_name: str
    phone: str
    region: str
    city: str
    district: str
    street: str
    building_number: str
    postal_code: str
    additional_info: str
    latitude: float | None = None
    longitude: float | None = None

    def as_dict(self) -> dict[str, str]:
        return {
            "recipient_name": self.recipient_name,
            "phone": self.phone,
            "region": self.region,
            "city": self.city,
            "district": self.district,
            "street": self.street,
            "building_number": self.building_number,
            "postal_code": self.postal_code,
            "additional_info": self.additional_info,
        }


@dataclass(frozen=True)
class QuoteRequest:
    """Everything a provider needs to price one merchant order's delivery."""

    method: DeliveryMethod
    store: "Store"
    settings: "StoreDeliverySettings"
    zones: Sequence["DeliveryZone"]
    pickup_locations: Sequence["MerchantAddress"]
    items_net: int  # item value after discounts (for free-delivery thresholds)
    address: AddressSnapshot | None
    pickup_location_id: uuid.UUID | None


@dataclass(frozen=True)
class PickupPoint:
    id: uuid.UUID
    label: str
    region: str
    city: str
    district: str
    street: str
    building_number: str
    postal_code: str
    latitude: float | None
    longitude: float | None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "label": self.label,
            "region": self.region,
            "city": self.city,
            "district": self.district,
            "street": self.street,
            "building_number": self.building_number,
            "postal_code": self.postal_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


@dataclass(frozen=True)
class DeliveryQuote:
    method: DeliveryMethod
    provider: str
    available: bool
    terms: DeliveryTerms
    issue: str | None = None  # machine-readable reason when unavailable
    base_fee: int = 0
    fee: int = 0
    eta_min_minutes: int = 0
    eta_max_minutes: int = 0
    zone_id: uuid.UUID | None = None
    zone_name: str | None = None
    free_delivery_threshold: int | None = None
    pickup_location: PickupPoint | None = None
    pickup_points: tuple[PickupPoint, ...] = field(default_factory=tuple)

    @property
    def fee_waived(self) -> int:
        return self.base_fee - self.fee


class DeliveryProvider(ABC):
    key: str
    methods: frozenset[DeliveryMethod]
    capabilities: ProviderCapabilities

    @abstractmethod
    def terms(self, method: DeliveryMethod) -> DeliveryTerms:
        """Who receives the fee and who bears the cost for ``method``."""

    @abstractmethod
    async def quote(self, request: QuoteRequest) -> DeliveryQuote:
        """Price a delivery. Must not have side effects."""

    def manual_transitions(self, method: DeliveryMethod) -> Mapping[DeliveryStatus, frozenset[DeliveryStatus]]:
        """Status changes the merchant may make by hand (empty when the provider drives them)."""
        return {}

    async def on_confirmed(self, delivery: "Delivery") -> None:  # noqa: B027 - optional hook
        """Called once the merchant confirms the order (e.g. book a courier)."""

    async def on_cancelled(self, delivery: "Delivery") -> None:  # noqa: B027 - optional hook
        """Called when the delivery is cancelled (e.g. cancel a courier booking)."""
