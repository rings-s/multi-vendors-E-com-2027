"""Permission codes and their default role assignments (seeded by migration 0002)."""

from enum import StrEnum

from app.modules.auth.models import RoleName


class Perm(StrEnum):
    MERCHANTS_VIEW = "admin.merchants.view"
    MERCHANTS_MANAGE = "admin.merchants.manage"
    CUSTOMERS_VIEW = "admin.customers.view"
    CUSTOMERS_MANAGE = "admin.customers.manage"
    CATALOG_MODERATE = "admin.catalog.moderate"
    CATEGORIES_MANAGE = "admin.categories.manage"
    ORDERS_VIEW = "admin.orders.view"
    ORDERS_MANAGE = "admin.orders.manage"
    PAYMENTS_VIEW = "admin.payments.view"
    REFUNDS_MANAGE = "admin.refunds.manage"
    DISPUTES_MANAGE = "admin.disputes.manage"
    RECONCILIATION_RUN = "admin.reconciliation.run"
    SETTLEMENTS_VIEW = "admin.settlements.view"
    SETTLEMENTS_RECONCILE = "admin.settlements.reconcile"
    COMMISSIONS_VIEW = "admin.commissions.view"
    COMMISSIONS_MANAGE = "admin.commissions.manage"
    SETTINGS_VIEW = "admin.settings.view"
    SETTINGS_MANAGE = "admin.settings.manage"
    AUDIT_VIEW = "admin.audit.view"
    SUPPORT_MANAGE = "admin.support.manage"
    USERS_ROLES_MANAGE = "admin.users.roles.manage"
    # Generic data admin (every table): browse, and create / change / delete raw records.
    DATA_VIEW = "admin.data.view"
    DATA_MANAGE = "admin.data.manage"
    # Change or delete rows of append-only tables (ledger, audit log, verification and
    # delivery timelines). Always needs a reason and is audited.
    DATA_OVERRIDE_IMMUTABLE = "admin.data.override_immutable"


# Permissions reserved for SUPER_ADMIN (financial configuration and role management).
SUPER_ADMIN_ONLY = frozenset(
    {
        Perm.COMMISSIONS_MANAGE,
        Perm.SETTINGS_MANAGE,
        Perm.SETTLEMENTS_RECONCILE,
        Perm.USERS_ROLES_MANAGE,
        Perm.DATA_MANAGE,
        Perm.DATA_OVERRIDE_IMMUTABLE,
    }
)

ROLE_PERMISSIONS: dict[RoleName, frozenset[Perm]] = {
    RoleName.CUSTOMER: frozenset(),
    RoleName.MERCHANT: frozenset(),
    RoleName.ADMIN: frozenset(p for p in Perm if p not in SUPER_ADMIN_ONLY),
    RoleName.SUPER_ADMIN: frozenset(Perm),
}
