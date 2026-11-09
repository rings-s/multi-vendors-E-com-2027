"""Provider selection (dependency injection)."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.config import PaymentProviderName, get_settings
from app.database.session import get_sessionmaker
from app.integrations.payments.base import PaymentProvider
from app.integrations.payments.mock import MockPaymentProvider
from app.integrations.payments.moyasar import MoyasarProvider


@lru_cache
def get_payment_provider() -> PaymentProvider:
    settings = get_settings()
    if settings.payment_provider == PaymentProviderName.MOYASAR:
        return MoyasarProvider(settings)
    return MockPaymentProvider(settings, get_sessionmaker())


def get_provider_by_name(name: str) -> PaymentProvider:
    provider = get_payment_provider()
    if provider.name != name:
        from app.core.errors import NotFound

        raise NotFound(f"Payment provider {name!r} is not active.")
    return provider


ProviderDep = Annotated[PaymentProvider, Depends(get_payment_provider)]
