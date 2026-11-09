"""Merchant-managed fulfillment (MVP): the merchant delivers within its own zones,
or hands the order over at one of its pickup locations.

The merchant receives the delivery fee and bears the delivery cost (including fees
waived by a free-delivery threshold). For pickup there is no fee; the customer
travels to the pickup point. Status changes are made by the merchant from the
dashboard; there is no live tracking or driver functionality.
"""

from collections.abc import Mapping

from app.modules.delivery.models import CostBearer, DeliveryMethod, DeliveryStatus, FeeRecipient
from app.modules.delivery.pricing import DeliveryTerms, Place, match_zone, zone_fee
from app.modules.delivery.providers.base import (
    DeliveryProvider,
    DeliveryQuote,
    PickupPoint,
    ProviderCapabilities,
    QuoteRequest,
)

S = DeliveryStatus

DELIVERY_FLOW: Mapping[DeliveryStatus, frozenset[DeliveryStatus]] = {
    S.CONFIRMED: frozenset({S.PREPARING, S.OUT_FOR_DELIVERY}),
    S.PREPARING: frozenset({S.OUT_FOR_DELIVERY}),
    S.OUT_FOR_DELIVERY: frozenset({S.DELIVERED, S.FAILED}),
    S.FAILED: frozenset({S.OUT_FOR_DELIVERY}),  # another attempt
}
PICKUP_FLOW: Mapping[DeliveryStatus, frozenset[DeliveryStatus]] = {
    S.CONFIRMED: frozenset({S.PREPARING, S.READY_FOR_PICKUP}),
    S.PREPARING: frozenset({S.READY_FOR_PICKUP}),
    S.READY_FOR_PICKUP: frozenset({S.DELIVERED, S.FAILED}),
    S.FAILED: frozenset({S.READY_FOR_PICKUP}),  # rescheduled collection
}


class MerchantFulfillmentProvider(DeliveryProvider):
    key = "merchant"
    methods = frozenset({DeliveryMethod.DELIVERY, DeliveryMethod.PICKUP})
    capabilities = ProviderCapabilities(manual_status_updates=True)

    def terms(self, method: DeliveryMethod) -> DeliveryTerms:
        if method == DeliveryMethod.PICKUP:
            return DeliveryTerms(fee_recipient=FeeRecipient.MERCHANT, cost_bearer=CostBearer.CUSTOMER)
        return DeliveryTerms(fee_recipient=FeeRecipient.MERCHANT, cost_bearer=CostBearer.MERCHANT)

    def manual_transitions(self, method: DeliveryMethod) -> Mapping[DeliveryStatus, frozenset[DeliveryStatus]]:
        return PICKUP_FLOW if method == DeliveryMethod.PICKUP else DELIVERY_FLOW

    async def quote(self, request: QuoteRequest) -> DeliveryQuote:
        if request.method == DeliveryMethod.PICKUP:
            return self._pickup(request)
        return self._delivery(request)

    def _unavailable(self, request: QuoteRequest, issue: str, **extra: object) -> DeliveryQuote:
        return DeliveryQuote(
            method=request.method,
            provider=self.key,
            available=False,
            terms=self.terms(request.method),
            issue=issue,
            **extra,  # type: ignore[arg-type]
        )

    def _delivery(self, request: QuoteRequest) -> DeliveryQuote:
        if not request.settings.delivery_enabled or not any(z.is_active for z in request.zones):
            return self._unavailable(request, "delivery_not_offered")
        if request.address is None:
            return self._unavailable(request, "address_required")
        zone = match_zone(
            request.zones,
            Place(region=request.address.region, city=request.address.city, district=request.address.district),
        )
        if zone is None:
            return self._unavailable(request, "address_outside_delivery_zones")
        fee = zone_fee(zone, request.items_net)
        return DeliveryQuote(
            method=DeliveryMethod.DELIVERY,
            provider=self.key,
            available=True,
            terms=self.terms(DeliveryMethod.DELIVERY),
            base_fee=fee.base_fee,
            fee=fee.fee,
            eta_min_minutes=zone.eta_min_minutes,
            eta_max_minutes=zone.eta_max_minutes,
            zone_id=zone.id,
            zone_name=zone.name,
            free_delivery_threshold=zone.free_delivery_threshold,
        )

    def _pickup(self, request: QuoteRequest) -> DeliveryQuote:
        points = tuple(
            PickupPoint(
                id=loc.id,
                label=loc.label,
                region=loc.region,
                city=loc.city,
                district=loc.district,
                street=loc.street,
                building_number=loc.building_number,
                postal_code=loc.postal_code,
                latitude=loc.latitude,
                longitude=loc.longitude,
            )
            for loc in request.pickup_locations
        )
        if not request.settings.pickup_enabled or not points:
            return self._unavailable(request, "pickup_not_offered")
        minutes = request.settings.pickup_preparation_minutes
        chosen = None
        if request.pickup_location_id is not None:
            chosen = next((p for p in points if p.id == request.pickup_location_id), None)
            if chosen is None:
                return self._unavailable(request, "invalid_pickup_location", pickup_points=points)
        elif len(points) == 1:
            chosen = points[0]
        if chosen is None:
            return self._unavailable(request, "pickup_location_required", pickup_points=points)
        return DeliveryQuote(
            method=DeliveryMethod.PICKUP,
            provider=self.key,
            available=True,
            terms=self.terms(DeliveryMethod.PICKUP),
            eta_min_minutes=minutes,
            eta_max_minutes=minutes,
            pickup_location=chosen,
            pickup_points=points,
        )
