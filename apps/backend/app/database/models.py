"""Import every table model so ``SQLModel.metadata`` (and Alembic) see the full schema."""

from app.integrations.payments.mock_models import MockProviderRecord
from app.modules.admin.models import AuditLog, PlatformSetting, SupportTicket
from app.modules.auth.models import (
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
    UserActionToken,
    UserRole,
    UserSession,
)
from app.modules.cart.models import Cart, CartItem
from app.modules.catalog.models import (
    Category,
    Inventory,
    Product,
    ProductImage,
    ProductVariant,
    Review,
    Service,
    ServiceImage,
)
from app.modules.commissions.models import CommissionRule, CommissionTransaction
from app.modules.customers.models import CustomerAddress, CustomerPreference, CustomerProfile
from app.modules.delivery.models import Delivery, DeliveryEvent, DeliveryZone, StoreDeliverySettings
from app.modules.ledger.models import FinancialReconciliation, LedgerAccount, LedgerEntry, LedgerTransaction
from app.modules.merchants.models import (
    Merchant,
    MerchantAddress,
    MerchantBankAccountReference,
    MerchantDocumentReference,
    MerchantPaymentAccount,
    MerchantProfile,
    MerchantVerification,
)
from app.modules.notifications.models import Notification
from app.modules.orders.models import MerchantOrder, Order, OrderItem, OrderStatusHistory, Shipment
from app.modules.payments.models import (
    Chargeback,
    Payment,
    PaymentAllocation,
    PaymentProviderAccount,
    PaymentWebhookEvent,
    Refund,
)
from app.modules.settlements.models import Settlement
from app.modules.stores.models import Store, StoreCategory

__all__ = [
    "AuditLog",
    "Cart",
    "CartItem",
    "Category",
    "Chargeback",
    "CommissionRule",
    "CommissionTransaction",
    "CustomerAddress",
    "CustomerPreference",
    "CustomerProfile",
    "Delivery",
    "DeliveryEvent",
    "DeliveryZone",
    "FinancialReconciliation",
    "Inventory",
    "LedgerAccount",
    "LedgerEntry",
    "LedgerTransaction",
    "Merchant",
    "MerchantAddress",
    "MerchantBankAccountReference",
    "MerchantDocumentReference",
    "MerchantOrder",
    "MerchantPaymentAccount",
    "MerchantProfile",
    "MerchantVerification",
    "MockProviderRecord",
    "Notification",
    "Order",
    "OrderItem",
    "OrderStatusHistory",
    "Payment",
    "PaymentAllocation",
    "PaymentProviderAccount",
    "PaymentWebhookEvent",
    "Permission",
    "PlatformSetting",
    "Product",
    "ProductImage",
    "ProductVariant",
    "RefreshToken",
    "Refund",
    "Review",
    "Role",
    "RolePermission",
    "Service",
    "ServiceImage",
    "Settlement",
    "Shipment",
    "Store",
    "StoreCategory",
    "StoreDeliverySettings",
    "SupportTicket",
    "User",
    "UserActionToken",
    "UserRole",
    "UserSession",
]
