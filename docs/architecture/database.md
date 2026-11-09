# Database Design

Use PostgreSQL with SQLModel (on SQLAlchemy 2.x).

Design normalized relational models with appropriate indexes and constraints.

Suggested domain entities:

## Identity

- User
- Role
- Permission
- UserSession
- RefreshToken

## Merchants

- Merchant
- MerchantProfile
- MerchantAddress
- MerchantVerification
- MerchantPaymentAccount
- MerchantBankAccountReference
- MerchantDocumentReference

## Marketplace

- Store
- StoreCategory
- Category
- Product
- ProductImage
- ProductVariant
- Inventory
- Service
- Review

## Customers

- CustomerProfile
- CustomerAddress
- CustomerPreference

## Commerce

- Cart
- CartItem
- Order
- OrderItem
- MerchantOrder
- Shipment
- OrderStatusHistory

## Delivery

- StoreDeliverySettings
- DeliveryZone
- Delivery
- DeliveryEvent (append-only)

See [Delivery & Fulfillment Architecture](delivery-architecture.md) for the delivery financial snapshot on `MerchantOrder` and the delivery parts of allocations, refunds, chargebacks and ledger entries.

## Payments

- Payment
- PaymentAllocation
- PaymentProviderAccount
- PaymentWebhookEvent
- Refund
- Chargeback
- Commission
- Settlement

## Finance

- LedgerAccount
- LedgerTransaction
- LedgerEntry
- FinancialReconciliation

For the suggested ledger, commission, and settlement entity fields, see [Payment Architecture — Financial ledger](payment-architecture.md#3-financial-ledger).

For the merchant payment-account fields, see [Payment Architecture — Payment onboarding](payment-architecture.md#1-payment-onboarding).

## Administration

- AuditLog
- PlatformSetting
- Notification
- SupportTicket

## ORM conventions (SQLModel)

- Every table is a `SQLModel` subclass declared with `table=True`. Shared columns (`id`, `created_at`, `updated_at`) are non-table SQLModel mixins in `app/database/base.py`, which also sets the constraint naming convention on `SQLModel.metadata`.
- Columns are declared with `Field(...)`: `max_length` for `VARCHAR(n)`, `max_digits`/`decimal_places` for `NUMERIC`, `foreign_key`/`ondelete`, `index`, `unique`. `datetime` fields map to timezone-aware timestamps. `sa_type` is used only for types SQLModel does not infer (`BIGINT` halalas, `TEXT`, `SMALLINT`, PostgreSQL `JSONB`).
- Check constraints, composite unique constraints and partial indexes are declared in `__table_args__`. Triggers (ledger/audit immutability, ledger balance) live in the migrations.
- Many-to-many links are link models: `UserRole`, `RolePermission`, `StoreCategory`. Relationships use `Relationship(...)` (eager `selectin` loading, because the async session forbids lazy IO).
- Queries use `sqlmodel.select` and `AsyncSession.exec` (`sqlmodel.ext.asyncio.session`); column operators (`in_`, `is_`, `desc`, `ilike`, joins, aggregates) use `col(Model.field)`.
- SQLAlchemy is imported directly only where SQLModel has no equivalent: the async engine/sessionmaker factory, `postgresql.insert(...).on_conflict_do_nothing` for idempotent inserts, `JSONB`, `ColumnElement` type hints and exception classes.
- `alembic check` must report no changes: the SQLModel metadata and the migrations describe the same schema.

## Rules

Use UUID primary keys.

Use timezone-aware timestamps.

Use appropriate foreign keys, unique constraints, indexes, and database-level checks.

Use soft deletion only where it makes business sense.

Financial records must not be deleted through ordinary CRUD operations.
