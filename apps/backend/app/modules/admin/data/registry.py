"""Model registry for the generic data admin.

Every table model is discovered from the SQLModel registry; its columns are introspected
into ``FieldSpec``s. ``CONFIG`` holds Django-``ModelAdmin``-style overrides per table.
Anything not configured gets a sensible default (display field, list columns, search,
filters and ordering are derived from the column types).
"""

from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache
from typing import Any, Literal

from pydantic_core import PydanticUndefined
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    Numeric,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.types import TypeDecorator, TypeEngine
from sqlmodel import SQLModel
from sqlmodel.main import default_registry

import app.database.models  # noqa: F401  (registers every table model)
from app.integrations.payments.mock_models import MockRecordKind
from app.modules.admin.models import TicketStatus
from app.modules.auth.models import Language, TokenPurpose
from app.modules.catalog.models import (
    CatalogStatus,
    CategoryKind,
    ReviewStatus,
    ServiceAvailability,
    ServiceLocationType,
)
from app.modules.commissions.models import CommissionRateType, CommissionScope
from app.modules.delivery.models import CostBearer, DeliveryMethod, DeliveryStatus, EventSource, FeeRecipient
from app.modules.ledger.models import (
    AccountType,
    Direction,
    LedgerComponent,
    LedgerTransactionType,
    ReconciliationStatus,
)
from app.modules.merchants.models import BusinessType, DocumentStatus, MerchantStatus, OnboardingStatus, PayoutStatus
from app.modules.notifications.models import NotificationType
from app.modules.orders.models import (
    CancellationStatus,
    FulfillmentType,
    InventoryState,
    ItemType,
    MerchantOrderStatus,
    OrderStatus,
    ShipmentStatus,
)
from app.modules.payments.models import (
    ChargebackStatus,
    FeeBearer,
    PaymentStatus,
    RecipientType,
    RefundInitiator,
    RefundScope,
    RefundStatus,
    WebhookEventStatus,
)
from app.modules.settlements.models import ConfirmationSource, SettlementStatus
from app.modules.stores.models import StoreStatus

FieldKind = Literal["uuid", "string", "text", "integer", "money", "decimal", "float", "boolean", "datetime", "json"]

# The group (Django "app") of a model is the module it lives in; the mock provider's
# records belong with payments.
_GROUP_OVERRIDES = {"integrations": "payments"}

# Columns that are always managed by the system.
_SYSTEM_COLUMNS = frozenset({"created_at", "updated_at"})

# Candidate columns for a row's display label, in order of preference.
_DISPLAY_CANDIDATES = (
    "email",
    "business_name",
    "name",
    "title",
    "number",
    "code",
    "key",
    "slug",
    "reference",
    "subject",
    "label",
    "owner_full_name",
    "beneficiary_name",
    "event_type",
    "provider_settlement_id",
    "external_id",
)

APPEND_ONLY = "append_only"
FINANCIAL = "financial"
SYSTEM_GENERATED = "system_generated"


@dataclass(frozen=True)
class ModelConfig:
    """Per-table overrides (the equivalent of a Django ``ModelAdmin``)."""

    display: tuple[str, ...] = ()
    list_display: tuple[str, ...] = ()
    search_fields: tuple[str, ...] | None = None
    list_filter: tuple[str, ...] | None = None
    ordering: tuple[str, ...] = ()
    readonly: tuple[str, ...] = ()
    # Never returned and never written through the admin (secrets, token hashes).
    hidden: tuple[str, ...] = ()
    choices: dict[str, type[StrEnum]] = field(default_factory=dict)
    can_add: bool = True
    can_change: bool = True
    can_delete: bool = True
    # A column that stores a password hash: the admin exposes a write-only ``password``.
    password_column: str | None = None
    # Redis cache keys to invalidate after any write.
    cache_keys: tuple[str, ...] = ()
    # Why the table is restricted, or a caution for editors (translated by the client).
    notes: tuple[str, ...] = ()
    # Append-only tables: the trigger that rejects UPDATE / DELETE. Changing or deleting a
    # row needs ``admin.data.override_immutable`` and a reason; the trigger is disabled
    # for that single statement only, inside the request's transaction.
    immutable_trigger: str | None = None
    # Child tables edited on this model's page (Django inlines): (child table, FK column).
    inlines: tuple[tuple[str, str], ...] = ()
    # Rows must keep the double-entry ledger balanced per value of this column.
    balanced_by: str | None = None
    # New rows are added through this parent's inline instead of on their own.
    add_via: str | None = None
    # Hidden columns filled automatically on create (e.g. an unusable random token hash).
    generated: tuple[str, ...] = ()


def append_only(table: str, **options: Any) -> ModelConfig:
    """An append-only table: ``{table}_immutable`` (migrations 0002 / 0004) rejects UPDATE and DELETE."""
    notes = (APPEND_ONLY, *options.pop("notes", ()))
    return ModelConfig(immutable_trigger=f"{table}_immutable", notes=notes, **options)


CONFIG: dict[str, ModelConfig] = {
    # -- auth ---------------------------------------------------------------------------
    "users": ModelConfig(
        display=("email",),
        list_display=("email", "full_name", "phone", "is_active", "preferred_language", "last_login_at", "created_at"),
        search_fields=("email", "full_name", "phone"),
        list_filter=("is_active", "preferred_language", "email_verified_at"),
        hidden=("password_hash",),
        password_column="password_hash",  # noqa: S106 (a column name)
        choices={"preferred_language": Language},
    ),
    "roles": ModelConfig(display=("name",), ordering=("name",)),
    "permissions": ModelConfig(display=("code",), list_display=("code", "description"), ordering=("code",)),
    "user_roles": ModelConfig(display=("user_id", "role_id"), list_filter=("role_id",)),
    "role_permissions": ModelConfig(display=("role_id", "permission_id"), list_filter=("role_id",)),
    "user_sessions": ModelConfig(
        display=("user_id", "ip_address"),
        list_display=("user_id", "ip_address", "user_agent", "last_seen_at", "revoked_at", "created_at"),
        search_fields=("ip_address", "user_agent", "revoked_reason"),
        list_filter=("revoked_at",),
        notes=(SYSTEM_GENERATED,),
    ),
    "refresh_tokens": ModelConfig(
        display=("session_id",),
        list_display=("session_id", "expires_at", "used_at", "revoked_at", "created_at"),
        list_filter=("used_at", "revoked_at"),
        hidden=("token_hash",),
        generated=("token_hash",),
        notes=(SYSTEM_GENERATED,),
    ),
    "user_action_tokens": ModelConfig(
        display=("user_id", "purpose"),
        list_display=("user_id", "purpose", "expires_at", "used_at", "created_at"),
        list_filter=("purpose", "used_at"),
        hidden=("token_hash",),
        generated=("token_hash",),
        choices={"purpose": TokenPurpose},
        notes=(SYSTEM_GENERATED,),
    ),
    # -- admin --------------------------------------------------------------------------
    "audit_logs": append_only(
        "audit_logs",
        display=("action", "entity_type"),
        list_display=("action", "entity_type", "entity_id", "actor_user_id", "ip_address", "created_at"),
        search_fields=("action", "entity_type", "entity_id", "ip_address"),
        list_filter=("actor_user_id",),
    ),
    "platform_settings": ModelConfig(display=("key",), list_display=("key", "updated_by_user_id", "updated_at")),
    "support_tickets": ModelConfig(
        display=("subject",),
        list_display=("subject", "user_id", "merchant_order_id", "status", "created_at", "updated_at"),
        search_fields=("subject", "body", "admin_response"),
        choices={"status": TicketStatus},
    ),
    # -- catalog ------------------------------------------------------------------------
    "categories": ModelConfig(
        display=("name_en",),
        list_display=("name_en", "name_ar", "slug", "kind", "parent_id", "is_active", "sort_order"),
        search_fields=("name_en", "name_ar", "slug"),
        ordering=("sort_order", "name_en"),
        choices={"kind": CategoryKind},
        cache_keys=("categories:active",),
    ),
    "products": ModelConfig(
        display=("title",),
        list_display=("title", "sku", "store_id", "price", "status", "is_available", "is_featured", "created_at"),
        search_fields=("title", "slug", "sku"),
        list_filter=("status", "is_available", "is_featured", "requires_shipping", "category_id"),
        choices={"status": CatalogStatus},
    ),
    "product_images": ModelConfig(
        display=("product_id", "sort_order"), list_display=("product_id", "url", "alt", "sort_order")
    ),
    "product_variants": ModelConfig(
        display=("name", "sku"),
        list_display=("name", "sku", "product_id", "price", "discounted_price", "is_active"),
    ),
    "inventory": ModelConfig(
        display=("product_id", "variant_id"),
        list_display=("product_id", "variant_id", "quantity_on_hand", "quantity_reserved", "updated_at"),
    ),
    "services": ModelConfig(
        display=("title",),
        list_display=("title", "store_id", "price", "duration_minutes", "status", "availability", "is_featured"),
        search_fields=("title", "slug", "location"),
        list_filter=("status", "availability", "location_type", "is_featured", "category_id"),
        choices={"status": CatalogStatus, "availability": ServiceAvailability, "location_type": ServiceLocationType},
    ),
    "service_images": ModelConfig(
        display=("service_id", "sort_order"), list_display=("service_id", "url", "alt", "sort_order")
    ),
    "reviews": ModelConfig(
        display=("store_id", "rating"),
        list_display=("store_id", "customer_user_id", "rating", "status", "created_at"),
        search_fields=("comment",),
        choices={"status": ReviewStatus},
    ),
    # -- cart ---------------------------------------------------------------------------
    "carts": ModelConfig(display=("user_id",), list_display=("user_id", "currency", "created_at", "updated_at")),
    "cart_items": ModelConfig(
        display=("cart_id", "product_id"),
        list_display=("cart_id", "product_id", "variant_id", "service_id", "quantity", "created_at"),
    ),
    # -- commissions --------------------------------------------------------------------
    "commission_rules": ModelConfig(
        display=("scope", "rate_type"),
        list_display=(
            "scope",
            "merchant_id",
            "category_id",
            "rate_type",
            "rate",
            "fixed_amount",
            "effective_from",
            "effective_to",
        ),
        search_fields=("note",),
        ordering=("-effective_from",),
        choices={"scope": CommissionScope, "rate_type": CommissionRateType},
        notes=(FINANCIAL,),
    ),
    "commission_transactions": ModelConfig(
        display=("merchant_order_id",),
        list_display=(
            "merchant_order_id",
            "merchant_id",
            "gross_amount",
            "commission_rate",
            "commission_amount",
            "seller_net_amount",
            "created_at",
        ),
        list_filter=("fee_bearer",),
        choices={"fee_bearer": FeeBearer},
        notes=(FINANCIAL,),
    ),
    # -- customers ----------------------------------------------------------------------
    "customer_profiles": ModelConfig(display=("display_name", "user_id"), list_display=("user_id", "display_name")),
    "customer_addresses": ModelConfig(
        display=("label", "city"),
        list_display=("user_id", "label", "recipient_name", "region", "city", "is_default", "is_deleted"),
        search_fields=("label", "recipient_name", "phone", "city", "district", "street", "postal_code"),
    ),
    "customer_preferences": ModelConfig(display=("user_id",), list_display=("user_id", "marketing_emails")),
    # -- delivery -----------------------------------------------------------------------
    "store_delivery_settings": ModelConfig(
        display=("store_id",),
        list_display=("store_id", "merchant_id", "delivery_enabled", "pickup_enabled", "pickup_preparation_minutes"),
    ),
    "delivery_zones": ModelConfig(
        display=("name",),
        list_display=("name", "store_id", "region", "fee", "free_delivery_threshold", "is_active"),
        search_fields=("name", "region"),
    ),
    "deliveries": ModelConfig(
        display=("merchant_order_id", "status"),
        list_display=("merchant_order_id", "store_id", "method", "status", "zone_name", "attempts", "created_at"),
        search_fields=("provider", "provider_reference", "zone_name"),
        list_filter=("method", "status", "provider"),
        choices={"method": DeliveryMethod, "status": DeliveryStatus},
    ),
    "delivery_events": append_only(
        "delivery_events",
        display=("delivery_id", "to_status"),
        list_display=("delivery_id", "from_status", "to_status", "source", "actor_user_id", "created_at"),
        choices={"from_status": DeliveryStatus, "to_status": DeliveryStatus, "source": EventSource},
    ),
    # -- ledger -------------------------------------------------------------------------
    "ledger_accounts": ModelConfig(
        display=("account_type", "merchant_id"),
        list_display=("account_type", "merchant_id", "currency", "created_at"),
        choices={"account_type": AccountType},
        notes=(FINANCIAL,),
    ),
    "ledger_entries": append_only(
        "ledger_entries",
        display=("transaction_id", "direction"),
        list_display=("transaction_id", "account_id", "direction", "amount", "component", "created_at"),
        search_fields=("description",),
        choices={"direction": Direction, "component": LedgerComponent},
        balanced_by="transaction_id",
        add_via="ledger_transactions",
        notes=(FINANCIAL,),
    ),
    "ledger_transactions": append_only(
        "ledger_transactions",
        display=("reference",),
        list_display=("reference", "transaction_type", "source_type", "merchant_id", "status", "is_test", "created_at"),
        search_fields=("reference", "source_type", "description"),
        list_filter=("transaction_type", "is_test", "merchant_id"),
        choices={"transaction_type": LedgerTransactionType},
        inlines=(("ledger_entries", "transaction_id"),),
        notes=(FINANCIAL,),
    ),
    "financial_reconciliations": ModelConfig(
        display=("scope", "status"),
        list_display=(
            "provider",
            "scope",
            "status",
            "checked_count",
            "mismatch_count",
            "applied_updates",
            "created_at",
        ),
        choices={"status": ReconciliationStatus},
        notes=(FINANCIAL,),
    ),
    # -- merchants ----------------------------------------------------------------------
    "merchants": ModelConfig(
        display=("business_name",),
        list_display=("business_name", "owner_user_id", "business_type", "status", "submitted_at", "approved_at"),
        search_fields=("business_name", "commercial_registration_number", "vat_number"),
        list_filter=("status", "business_type", "category_id"),
        choices={"status": MerchantStatus, "business_type": BusinessType},
    ),
    "merchant_profiles": ModelConfig(
        display=("owner_full_name",),
        list_display=("merchant_id", "owner_full_name", "contact_email", "contact_phone"),
    ),
    "merchant_addresses": ModelConfig(
        display=("label", "city"),
        list_display=("merchant_id", "label", "region", "city", "is_primary", "is_pickup_location"),
    ),
    "merchant_verifications": append_only(
        "merchant_verifications",
        display=("merchant_id", "to_status"),
        list_display=("merchant_id", "from_status", "to_status", "actor_user_id", "created_at"),
        choices={"from_status": MerchantStatus, "to_status": MerchantStatus},
    ),
    "merchant_payment_accounts": ModelConfig(
        display=("merchant_id", "provider"),
        list_display=("merchant_id", "provider", "onboarding_status", "payout_status", "is_test", "last_synced_at"),
        list_filter=("provider", "onboarding_status", "payout_status", "is_test"),
        choices={"onboarding_status": OnboardingStatus, "payout_status": PayoutStatus},
        notes=(FINANCIAL,),
    ),
    "merchant_bank_account_references": ModelConfig(
        display=("beneficiary_name", "iban_masked"),
        list_display=("merchant_id", "beneficiary_name", "bank_name", "iban_masked", "is_active"),
    ),
    "merchant_document_references": ModelConfig(
        display=("document_type",),
        list_display=("merchant_id", "provider", "document_type", "status", "updated_at"),
        choices={"status": DocumentStatus},
    ),
    # -- notifications ------------------------------------------------------------------
    "notifications": ModelConfig(
        display=("type", "user_id"),
        list_display=("user_id", "type", "read_at", "email_sent_at", "created_at"),
        list_filter=("type", "read_at", "email_sent_at"),
        choices={"type": NotificationType},
    ),
    # -- orders -------------------------------------------------------------------------
    "orders": ModelConfig(
        display=("number",),
        list_display=("number", "customer_user_id", "status", "total", "contact_name", "created_at"),
        search_fields=("number", "contact_name", "contact_email", "contact_phone", "idempotency_key"),
        choices={"status": OrderStatus},
        notes=(FINANCIAL,),
    ),
    "merchant_orders": ModelConfig(
        display=("number",),
        list_display=("number", "merchant_id", "store_id", "status", "total", "cancellation_status", "created_at"),
        search_fields=("number", "merchant_note", "cancellation_reason"),
        list_filter=(
            "status",
            "fulfillment_type",
            "delivery_method",
            "cancellation_status",
            "inventory_state",
            "merchant_id",
        ),
        choices={
            "status": MerchantOrderStatus,
            "fulfillment_type": FulfillmentType,
            "delivery_method": DeliveryMethod,
            "delivery_fee_recipient": FeeRecipient,
            "delivery_cost_bearer": CostBearer,
            "inventory_state": InventoryState,
            "cancellation_status": CancellationStatus,
        },
        notes=(FINANCIAL,),
    ),
    "order_items": ModelConfig(
        display=("title",),
        list_display=("title", "merchant_order_id", "item_type", "sku", "unit_price", "quantity", "line_total"),
        search_fields=("title", "sku"),
        choices={"item_type": ItemType, "commission_rate_type": CommissionRateType},
        notes=(FINANCIAL,),
    ),
    "order_status_history": ModelConfig(
        display=("order_id", "to_status"),
        list_display=("order_id", "merchant_order_id", "from_status", "to_status", "actor_user_id", "created_at"),
    ),
    "shipments": ModelConfig(
        display=("carrier", "tracking_number"),
        list_display=("merchant_order_id", "carrier", "tracking_number", "status", "shipped_at", "delivered_at"),
        choices={"status": ShipmentStatus},
    ),
    # -- payments -----------------------------------------------------------------------
    "payments": ModelConfig(
        display=("provider", "provider_payment_id"),
        list_display=(
            "merchant_order_id",
            "provider",
            "provider_payment_id",
            "status",
            "amount",
            "refunded_amount",
            "is_test",
            "created_at",
        ),
        search_fields=("provider_payment_id", "payment_method", "failure_reason"),
        list_filter=("status", "provider", "is_test", "merchant_id"),
        choices={"status": PaymentStatus, "fee_bearer": FeeBearer},
        notes=(FINANCIAL,),
    ),
    "payment_allocations": ModelConfig(
        display=("recipient_type", "recipient_id"),
        list_display=("payment_id", "recipient_type", "merchant_id", "amount", "delivery_amount", "refundable"),
        choices={"recipient_type": RecipientType},
        notes=(FINANCIAL,),
    ),
    "payment_provider_accounts": ModelConfig(
        display=("provider",), list_display=("provider", "is_live", "status", "platform_recipient_id", "updated_at")
    ),
    "payment_webhook_events": ModelConfig(
        display=("event_type", "event_id"),
        list_display=("provider", "event_type", "event_id", "status", "attempts", "is_live", "created_at"),
        search_fields=("event_id", "event_type", "last_error"),
        list_filter=("status", "provider", "is_live", "event_type"),
        choices={"status": WebhookEventStatus},
    ),
    "refunds": ModelConfig(
        display=("merchant_order_id", "amount"),
        list_display=("merchant_order_id", "amount", "scope", "status", "initiated_by", "created_at"),
        search_fields=("reason", "provider_reference", "failure_reason"),
        list_filter=("status", "scope", "initiated_by", "restock", "merchant_id"),
        choices={"status": RefundStatus, "initiated_by": RefundInitiator, "scope": RefundScope},
        notes=(FINANCIAL,),
    ),
    "chargebacks": ModelConfig(
        display=("payment_id", "amount"),
        list_display=("payment_id", "merchant_id", "amount", "status", "opened_at", "resolved_at"),
        search_fields=("reason", "provider_reference"),
        choices={"status": ChargebackStatus, "previous_payment_status": PaymentStatus},
        notes=(FINANCIAL,),
    ),
    "mock_provider_records": ModelConfig(
        display=("kind", "external_id"),
        list_display=("kind", "external_id", "created_at", "updated_at"),
        choices={"kind": MockRecordKind},
    ),
    # -- settlements --------------------------------------------------------------------
    "settlements": ModelConfig(
        display=("provider_settlement_id",),
        list_display=("provider_settlement_id", "merchant_id", "provider", "amount", "status", "is_test", "created_at"),
        search_fields=("provider_settlement_id", "confirmation_reference", "failure_reason"),
        list_filter=("status", "provider", "is_test", "confirmation_source", "merchant_id"),
        choices={"status": SettlementStatus, "confirmation_source": ConfirmationSource},
        notes=(FINANCIAL,),
    ),
    # -- stores -------------------------------------------------------------------------
    "stores": ModelConfig(
        display=("name",),
        list_display=("name", "slug", "merchant_id", "city", "status", "is_open", "rating_avg", "created_at"),
        search_fields=("name", "slug", "city", "region", "contact_email", "contact_phone"),
        choices={"status": StoreStatus},
    ),
    "store_categories": ModelConfig(display=("store_id", "category_id"), list_filter=("category_id",)),
}


@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: FieldKind
    nullable: bool
    primary_key: bool
    # Required when creating: not nullable, and neither a Python nor a server default.
    required: bool
    readonly: bool
    max_length: int | None
    choices: tuple[str, ...] | None
    # Referenced admin model (table name) for foreign keys.
    fk: str | None
    on_delete: str | None
    column: Column[Any] = field(repr=False, compare=False)


@dataclass(frozen=True)
class ReverseRelation:
    """A foreign key in another table that points at this model."""

    model: str
    field: str
    on_delete: str  # CASCADE | SET NULL | RESTRICT


@dataclass(frozen=True)
class AdminModel:
    key: str
    group: str
    model: type[SQLModel]
    table: Table
    config: ModelConfig
    fields: tuple[FieldSpec, ...]
    pk: tuple[str, ...]
    display: tuple[str, ...]
    list_display: tuple[str, ...]
    search_fields: tuple[str, ...]
    list_filter: tuple[str, ...]
    ordering: tuple[str, ...]

    @property
    def can_add(self) -> bool:
        return self.config.can_add

    @property
    def can_change(self) -> bool:
        # Link tables (every column is part of a composite key) change their key columns.
        editable = any(not f.readonly and (not f.primary_key or not self.auto_pk) for f in self.fields)
        return self.config.can_change and editable

    @property
    def can_delete(self) -> bool:
        return self.config.can_delete

    @property
    def immutable(self) -> bool:
        return self.config.immutable_trigger is not None

    @property
    def by_name(self) -> dict[str, FieldSpec]:
        return {f.name: f for f in self.fields}

    @property
    def auto_pk(self) -> bool:
        """A single UUID key generated by the model (not entered by the admin)."""
        return len(self.pk) == 1 and self.by_name[self.pk[0]].readonly

    def reverse_relations(self) -> list[ReverseRelation]:
        return _reverse_relations()[self.key]


def _base_type(t: TypeEngine[Any]) -> TypeEngine[Any]:
    while isinstance(t, TypeDecorator):
        t = t.impl_instance
    return t


def _kind(column: Column[Any]) -> FieldKind:
    t = _base_type(column.type)
    if isinstance(t, Uuid):
        return "uuid"
    if isinstance(t, Boolean):
        return "boolean"
    if isinstance(t, BigInteger):
        # Every BIGINT column in this schema is an amount in halalas.
        return "money"
    if isinstance(t, Integer):
        return "integer"
    if isinstance(t, Float):
        return "float"
    if isinstance(t, Numeric):
        return "decimal"
    if isinstance(t, DateTime):
        return "datetime"
    if isinstance(t, JSON):
        return "json"
    if isinstance(t, Text):
        return "text"
    return "string"


def _has_default(model: type[SQLModel], column: Column[Any]) -> bool:
    if column.server_default is not None or column.default is not None:
        return True
    info = model.model_fields.get(column.key)
    if info is None:
        return False
    return info.default is not PydanticUndefined or info.default_factory is not None


def _field_specs(model: type[SQLModel], table: Table, config: ModelConfig) -> tuple[FieldSpec, ...]:
    pk_cols = [c for c in table.columns if c.primary_key]
    specs: list[FieldSpec] = []
    for column in table.columns:
        if column.name in config.hidden:
            continue
        kind = _kind(column)
        fk = next(iter(column.foreign_keys), None)
        enum = config.choices.get(column.name)
        auto_key = column.primary_key and len(pk_cols) == 1 and kind == "uuid" and fk is None
        max_length = getattr(_base_type(column.type), "length", None)
        specs.append(
            FieldSpec(
                name=column.name,
                kind=kind,
                nullable=bool(column.nullable),
                primary_key=column.primary_key,
                required=not column.nullable and not _has_default(model, column) and not auto_key,
                readonly=auto_key or column.name in _SYSTEM_COLUMNS or column.name in config.readonly,
                max_length=max_length if isinstance(max_length, int) else None,
                choices=tuple(e.value for e in enum) if enum else None,
                fk=fk.column.table.name if fk else None,
                on_delete=(fk.ondelete or "NO ACTION").upper() if fk else None,
                column=column,
            )
        )
    return tuple(specs)


def _group(model: type[SQLModel]) -> str:
    parts = model.__module__.split(".")
    name = parts[2] if len(parts) > 2 and parts[1] == "modules" else parts[1]
    return _GROUP_OVERRIDES.get(name, name)


def _build(model: type[SQLModel], table: Table) -> AdminModel:
    config = CONFIG.get(table.name, ModelConfig())
    fields = _field_specs(model, table, config)
    names = {f.name: f for f in fields}
    pk = tuple(c.name for c in table.columns if c.primary_key)

    display = config.display or next(((c,) for c in _DISPLAY_CANDIDATES if c in names), pk)
    list_display = config.list_display or tuple(
        dict.fromkeys([*display, *(f.name for f in fields if f.kind not in ("json", "text") and not f.primary_key)][:7])
    )
    if not config.list_display and len(pk) > 1:
        list_display = pk
    search = (
        config.search_fields
        if config.search_fields is not None
        else tuple(f.name for f in fields if f.kind == "string" and f.choices is None)
    )
    filters = (
        config.list_filter
        if config.list_filter is not None
        else tuple(f.name for f in fields if f.kind == "boolean" or f.choices is not None)
    )
    ordering = config.ordering or (("-created_at",) if "created_at" in names else display)
    for name in (*display, *list_display, *search, *filters, *(o.lstrip("-") for o in ordering)):
        if name not in names:
            raise RuntimeError(f"Admin config for {table.name!r} references unknown column {name!r}")
    return AdminModel(
        key=table.name,
        group=_group(model),
        model=model,
        table=table,
        config=config,
        fields=fields,
        pk=pk,
        display=display,
        list_display=list_display,
        search_fields=search,
        list_filter=filters,
        ordering=ordering,
    )


@cache
def registry() -> dict[str, AdminModel]:
    """Every table model, keyed by table name, sorted by group and name."""
    models: list[AdminModel] = []
    for mapper in default_registry.mappers:
        cls = mapper.class_
        table = mapper.local_table
        if isinstance(table, Table) and issubclass(cls, SQLModel):
            models.append(_build(cls, table))
    unknown = set(CONFIG) - {m.key for m in models}
    if unknown:
        raise RuntimeError(f"Admin config for unknown tables: {sorted(unknown)}")
    by_key = {m.key: m for m in models}
    for m in models:
        for child, fk in m.config.inlines:
            if child not in by_key or fk not in by_key[child].by_name or by_key[child].by_name[fk].fk != m.key:
                raise RuntimeError(f"Invalid inline {child}.{fk} on {m.key!r}")
        if m.config.add_via and m.config.add_via not in by_key:
            raise RuntimeError(f"Invalid add_via on {m.key!r}")
    return {m.key: m for m in sorted(models, key=lambda m: (m.group, m.key))}


@cache
def _reverse_relations() -> dict[str, list[ReverseRelation]]:
    out: dict[str, list[ReverseRelation]] = {key: [] for key in registry()}
    for admin in registry().values():
        for column in admin.table.columns:
            for fk in column.foreign_keys:
                target = fk.column.table.name
                if target in out:
                    out[target].append(
                        ReverseRelation(
                            model=admin.key, field=column.name, on_delete=(fk.ondelete or "NO ACTION").upper()
                        )
                    )
    return out


def get_model(key: str) -> AdminModel | None:
    return registry().get(key)
