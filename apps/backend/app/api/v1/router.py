"""Versioned API router: /api/v1"""

from fastapi import APIRouter

from app.core.config import get_settings
from app.modules.admin.data.router import router as admin_data_router
from app.modules.admin.router import router as admin_router
from app.modules.auth.router import router as auth_router
from app.modules.cart.router import router as cart_router
from app.modules.customers.router import router as customers_router
from app.modules.delivery.router import router as delivery_router
from app.modules.merchants.portal_router import router as merchant_portal_router
from app.modules.merchants.router import router as merchants_router
from app.modules.notifications.router import router as notifications_router
from app.modules.notifications.router import support_router, uploads_router
from app.modules.orders.router import checkout_router
from app.modules.orders.router import router as orders_router
from app.modules.payments.router import router as payments_router
from app.modules.payments.router import webhook_router
from app.modules.stores.router import (
    categories_router,
    homepage_router,
    products_router,
    services_router,
    stores_router,
)
from app.modules.users.router import router as users_router


def build_api_router() -> APIRouter:
    api = APIRouter(prefix="/api/v1")
    for router in (
        auth_router,
        users_router,
        customers_router,
        merchants_router,
        stores_router,
        categories_router,
        products_router,
        services_router,
        homepage_router,
        cart_router,
        checkout_router,
        orders_router,
        payments_router,
        webhook_router,
        merchant_portal_router,
        delivery_router,
        admin_router,
        admin_data_router,
        notifications_router,
        uploads_router,
        support_router,
    ):
        api.include_router(router)
    settings = get_settings()
    if settings.mock_payments_enabled and not settings.is_production:
        from app.integrations.payments.mock_router import router as mock_router

        api.include_router(mock_router)
    return api
