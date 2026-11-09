"""Delivery provider registry.

MVP: every method is fulfilled by the merchant. Platform-managed drivers or courier
integrations are added here as new ``DeliveryProvider`` implementations; checkout
asks the registry which provider serves a store and a method, so nothing else in
the order flow needs to change.
"""

from app.core.errors import NotFound
from app.modules.delivery.models import DeliveryMethod
from app.modules.delivery.providers.base import DeliveryProvider
from app.modules.delivery.providers.merchant import MerchantFulfillmentProvider

_PROVIDERS: dict[str, DeliveryProvider] = {p.key: p for p in (MerchantFulfillmentProvider(),)}


def get_provider(key: str) -> DeliveryProvider:
    provider = _PROVIDERS.get(key)
    if provider is None:
        raise NotFound(f"Unknown delivery provider {key!r}.")
    return provider


def provider_for(method: DeliveryMethod) -> DeliveryProvider:
    """The provider that fulfils ``method`` for a store (merchant-managed in the MVP)."""
    for provider in _PROVIDERS.values():
        if method in provider.methods:
            return provider
    raise NotFound(f"No delivery provider supports {method.value}.")
