"""Delivery & fulfillment module.

* New tables: store_delivery_settings, delivery_zones, deliveries, delivery_events.
* Store flat shipping (``stores.shipping_fee`` / ``free_shipping_threshold``) becomes a
  nationwide delivery zone per store with the same fee and threshold, so existing
  stores keep charging exactly what they charged before.
* Orders: ``shipping_*`` columns are renamed to ``delivery_*``; merchant orders get an
  explicit delivery financial snapshot (method, fee, waived fee, VAT on delivery,
  delivery commission, fee recipient and cost bearer).
* Payment allocations, refunds, chargebacks and commission transactions record their
  delivery part; ledger entries get a ``component`` (GOODS / DELIVERY).

Legacy (pre-0004) payments are not componentized: their allocations, refunds and
ledger entries carry no delivery part (0 / NULL), which keeps them consistent with
the immutable ledger. Their merchant orders still show the delivery fee charged.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TS = sa.DateTime(timezone=True)


def _timestamps() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
    ]


def _bigint(table: str, column: str) -> None:
    op.add_column(table, sa.Column(column, sa.BigInteger(), server_default="0", nullable=False))


def upgrade() -> None:
    # -- configuration --------------------------------------------------------------------
    op.create_table(
        "delivery_zones",
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("merchant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("cities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("districts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fee", sa.BigInteger(), nullable=False),
        sa.Column("free_delivery_threshold", sa.BigInteger(), nullable=True),
        sa.Column("eta_min_minutes", sa.Integer(), nullable=False),
        sa.Column("eta_max_minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "eta_min_minutes >= 0 AND eta_max_minutes >= eta_min_minutes", name=op.f("ck_delivery_zones_eta_valid")
        ),
        sa.CheckConstraint("fee >= 0 AND fee <= 1000000", name=op.f("ck_delivery_zones_fee_range")),
        sa.CheckConstraint(
            "free_delivery_threshold IS NULL OR free_delivery_threshold >= 0",
            name=op.f("ck_delivery_zones_threshold_valid"),
        ),
        sa.CheckConstraint(
            "jsonb_array_length(cities) = 0 OR region IS NOT NULL", name=op.f("ck_delivery_zones_cities_need_region")
        ),
        sa.CheckConstraint(
            "jsonb_array_length(districts) = 0 OR jsonb_array_length(cities) > 0",
            name=op.f("ck_delivery_zones_districts_need_city"),
        ),
        sa.ForeignKeyConstraint(
            ["merchant_id"], ["merchants.id"], name=op.f("fk_delivery_zones_merchant_id_merchants"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name=op.f("fk_delivery_zones_store_id_stores"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_zones")),
    )
    op.create_index(op.f("ix_delivery_zones_merchant_id"), "delivery_zones", ["merchant_id"], unique=False)
    op.create_index(op.f("ix_delivery_zones_store_id"), "delivery_zones", ["store_id"], unique=False)

    op.create_table(
        "store_delivery_settings",
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("merchant_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_enabled", sa.Boolean(), nullable=False),
        sa.Column("pickup_enabled", sa.Boolean(), nullable=False),
        sa.Column("pickup_preparation_minutes", sa.Integer(), nullable=False),
        sa.Column("delivery_policy", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "pickup_preparation_minutes >= 0 AND pickup_preparation_minutes <= 43200",
            name=op.f("ck_store_delivery_settings_preparation_range"),
        ),
        sa.ForeignKeyConstraint(
            ["merchant_id"],
            ["merchants.id"],
            name=op.f("fk_store_delivery_settings_merchant_id_merchants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name=op.f("fk_store_delivery_settings_store_id_stores"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_store_delivery_settings")),
        sa.UniqueConstraint("store_id", name=op.f("uq_store_delivery_settings_store_id")),
    )
    op.create_index(
        op.f("ix_store_delivery_settings_merchant_id"), "store_delivery_settings", ["merchant_id"], unique=False
    )

    # Existing stores: keep their flat fee and threshold as a nationwide zone; the
    # shipping policy text becomes the delivery policy.
    op.execute(
        """
        INSERT INTO store_delivery_settings
            (id, store_id, merchant_id, delivery_enabled, pickup_enabled, pickup_preparation_minutes, delivery_policy)
        SELECT gen_random_uuid(), s.id, s.merchant_id, TRUE, FALSE, 120, COALESCE(s.shipping_policy, '')
          FROM stores s
        """
    )
    op.execute(
        """
        INSERT INTO delivery_zones
            (id, store_id, merchant_id, name, region, cities, districts, fee, free_delivery_threshold,
             eta_min_minutes, eta_max_minutes, is_active)
        SELECT gen_random_uuid(), s.id, s.merchant_id, 'Saudi Arabia', NULL, '[]'::jsonb, '[]'::jsonb,
               s.shipping_fee, s.free_shipping_threshold, 1440, 7200, TRUE
          FROM stores s
        """
    )
    op.drop_constraint(op.f("ck_stores_shipping_fee_non_negative"), "stores", type_="check")
    op.drop_column("stores", "free_shipping_threshold")
    op.drop_column("stores", "shipping_fee")

    # -- customer addresses ---------------------------------------------------------------
    op.add_column("customer_addresses", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("customer_addresses", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column(
        "customer_addresses",
        sa.Column("delivery_instructions", sa.String(length=500), server_default="", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_customer_addresses_pin"),
        "customer_addresses",
        "(latitude IS NULL) = (longitude IS NULL)"
        " AND (latitude IS NULL OR latitude BETWEEN -90 AND 90)"
        " AND (longitude IS NULL OR longitude BETWEEN -180 AND 180)",
    )

    # -- orders ---------------------------------------------------------------------------
    op.drop_constraint(op.f("ck_orders_total_consistent"), "orders", type_="check")
    op.alter_column("orders", "shipping_total", new_column_name="delivery_total")
    op.alter_column("orders", "shipping_address", new_column_name="delivery_address")
    op.create_check_constraint(
        op.f("ck_orders_total_consistent"), "orders", "total = items_subtotal - discount_total + delivery_total + vat_total"
    )

    for name in ("amounts_non_negative", "total_consistent", "commission_range", "net_consistent"):
        op.drop_constraint(op.f(f"ck_merchant_orders_{name}"), "merchant_orders", type_="check")
    op.alter_column("merchant_orders", "shipping_total", new_column_name="delivery_fee")
    op.add_column(
        "merchant_orders",
        sa.Column("delivery_method", sa.String(length=20), server_default="NONE", nullable=False),
    )
    _bigint("merchant_orders", "delivery_fee_waived")
    _bigint("merchant_orders", "delivery_vat")
    op.add_column("merchant_orders", sa.Column("delivery_fee_recipient", sa.String(length=20), nullable=True))
    op.add_column("merchant_orders", sa.Column("delivery_cost_bearer", sa.String(length=20), nullable=True))
    _bigint("merchant_orders", "delivery_commission")
    op.add_column(
        "merchant_orders", sa.Column("delivery_commission_rate", sa.Numeric(precision=6, scale=3), nullable=True)
    )
    # Legacy physical orders were merchant-delivered; VAT on delivery is the part of
    # vat_total above VAT on the items (exact, since VAT was rounded on the sum).
    op.execute(
        """
        UPDATE merchant_orders mo
           SET delivery_method = 'DELIVERY',
               delivery_fee_recipient = 'MERCHANT',
               delivery_cost_bearer = 'MERCHANT',
               delivery_vat = GREATEST(
                   LEAST(mo.vat_total - ROUND((mo.items_subtotal - mo.discount_total) * mo.vat_rate / 100), mo.vat_total),
                   0)
         WHERE EXISTS (SELECT 1 FROM order_items oi WHERE oi.merchant_order_id = mo.id AND oi.requires_shipping)
        """
    )
    op.create_check_constraint(
        op.f("ck_merchant_orders_amounts_non_negative"),
        "merchant_orders",
        "items_subtotal >= 0 AND discount_total >= 0 AND delivery_fee >= 0 AND vat_total >= 0"
        " AND delivery_vat >= 0 AND delivery_vat <= vat_total AND delivery_fee_waived >= 0",
    )
    op.create_check_constraint(
        op.f("ck_merchant_orders_total_consistent"),
        "merchant_orders",
        "total = items_subtotal - discount_total + delivery_fee + vat_total",
    )
    op.create_check_constraint(
        op.f("ck_merchant_orders_commission_range"),
        "merchant_orders",
        "commission_total >= 0 AND delivery_commission >= 0 AND delivery_commission <= delivery_fee"
        " AND commission_total + delivery_commission <= total",
    )
    op.create_check_constraint(
        op.f("ck_merchant_orders_net_consistent"),
        "merchant_orders",
        "merchant_net = total - commission_total - delivery_commission"
        " - CASE WHEN delivery_fee_recipient = 'PLATFORM' THEN delivery_fee + delivery_vat ELSE 0 END",
    )
    op.create_check_constraint(
        op.f("ck_merchant_orders_delivery_method_valid"), "merchant_orders", "delivery_method IN ('NONE', 'DELIVERY', 'PICKUP')"
    )
    op.create_check_constraint(
        op.f("ck_merchant_orders_delivery_terms_recorded"),
        "merchant_orders",
        "(delivery_method = 'NONE') = (delivery_fee_recipient IS NULL AND delivery_cost_bearer IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_merchant_orders_delivery_fee_requires_delivery"),
        "merchant_orders",
        "delivery_method = 'DELIVERY' OR (delivery_fee = 0 AND delivery_vat = 0 AND delivery_fee_waived = 0)",
    )
    op.create_check_constraint(
        op.f("ck_merchant_orders_delivery_commission_merchant_only"),
        "merchant_orders",
        "delivery_fee_recipient IS DISTINCT FROM 'PLATFORM' OR delivery_commission = 0",
    )

    # -- financial records ----------------------------------------------------------------
    op.drop_constraint(op.f("ck_commission_transactions_net_consistent"), "commission_transactions", type_="check")
    _bigint("commission_transactions", "delivery_fee")
    op.add_column(
        "commission_transactions",
        sa.Column("delivery_commission_rate", sa.Numeric(precision=6, scale=3), nullable=True),
    )
    _bigint("commission_transactions", "delivery_commission_amount")
    _bigint("commission_transactions", "platform_delivery_amount")
    op.execute(
        "UPDATE commission_transactions ct SET delivery_fee = mo.delivery_fee"
        " FROM merchant_orders mo WHERE mo.id = ct.merchant_order_id"
    )
    op.create_check_constraint(
        op.f("ck_commission_transactions_net_consistent"),
        "commission_transactions",
        "seller_net_amount = gross_amount - commission_amount - delivery_commission_amount"
        " - platform_delivery_amount"
        " - CASE WHEN fee_bearer = 'MERCHANT' THEN COALESCE(processing_fee, 0) ELSE 0 END",
    )
    op.create_check_constraint(
        op.f("ck_commission_transactions_delivery_amounts_valid"),
        "commission_transactions",
        "delivery_fee >= 0 AND delivery_commission_amount >= 0 AND delivery_commission_amount <= delivery_fee"
        " AND platform_delivery_amount >= 0",
    )

    _bigint("payment_allocations", "delivery_amount")
    op.create_check_constraint(
        op.f("ck_payment_allocations_delivery_amount_range"),
        "payment_allocations",
        "delivery_amount >= 0 AND delivery_amount <= amount",
    )

    op.add_column("refunds", sa.Column("scope", sa.String(length=20), server_default="AUTO", nullable=False))
    _bigint("refunds", "delivery_portion")
    _bigint("refunds", "delivery_platform_portion")
    op.create_check_constraint(op.f("ck_refunds_scope_valid"), "refunds", "scope IN ('AUTO', 'ITEMS', 'DELIVERY')")
    op.create_check_constraint(
        op.f("ck_refunds_delivery_portions_valid"),
        "refunds",
        "delivery_portion >= 0 AND delivery_portion <= amount"
        " AND delivery_platform_portion >= 0 AND delivery_platform_portion <= delivery_portion"
        " AND delivery_platform_portion <= platform_portion"
        " AND delivery_portion - delivery_platform_portion <= merchant_portion",
    )
    _bigint("chargebacks", "delivery_portion")
    _bigint("chargebacks", "delivery_platform_portion")
    op.create_check_constraint(
        op.f("ck_chargebacks_delivery_portions_valid"),
        "chargebacks",
        "delivery_portion >= 0 AND delivery_portion <= amount"
        " AND delivery_platform_portion >= 0 AND delivery_platform_portion <= delivery_portion",
    )

    # Adding a nullable column rewrites no rows, so the immutability triggers do not fire.
    op.add_column("ledger_entries", sa.Column("component", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        op.f("ck_ledger_entries_component_valid"), "ledger_entries", "component IS NULL OR component IN ('GOODS', 'DELIVERY')"
    )

    # -- deliveries -----------------------------------------------------------------------
    op.create_table(
        "deliveries",
        *_timestamps(),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("merchant_order_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("merchant_id", sa.Uuid(), nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("customer_user_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_reference", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("zone_id", sa.Uuid(), nullable=True),
        sa.Column("zone_name", sa.String(length=100), nullable=True),
        sa.Column("address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("pickup_location_id", sa.Uuid(), nullable=True),
        sa.Column("pickup_location", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("eta_min_minutes", sa.Integer(), nullable=False),
        sa.Column("eta_max_minutes", sa.Integer(), nullable=False),
        sa.Column("estimated_earliest_at", TS, nullable=True),
        sa.Column("estimated_latest_at", TS, nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("confirmed_at", TS, nullable=True),
        sa.Column("ready_at", TS, nullable=True),
        sa.Column("out_for_delivery_at", TS, nullable=True),
        sa.Column("delivered_at", TS, nullable=True),
        sa.Column("failed_at", TS, nullable=True),
        sa.Column("cancelled_at", TS, nullable=True),
        sa.CheckConstraint(
            "method <> 'DELIVERY' OR address IS NOT NULL", name=op.f("ck_deliveries_delivery_has_address")
        ),
        sa.CheckConstraint(
            "method <> 'PICKUP' OR pickup_location IS NOT NULL", name=op.f("ck_deliveries_pickup_has_location")
        ),
        sa.CheckConstraint("method IN ('DELIVERY', 'PICKUP')", name=op.f("ck_deliveries_method_valid")),
        sa.CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'PREPARING', 'READY_FOR_PICKUP', 'OUT_FOR_DELIVERY',"
            " 'DELIVERED', 'FAILED', 'CANCELLED')",
            name=op.f("ck_deliveries_status_valid"),
        ),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)"
            " AND (latitude IS NULL OR latitude BETWEEN -90 AND 90)"
            " AND (longitude IS NULL OR longitude BETWEEN -180 AND 180)",
            name=op.f("ck_deliveries_pin_valid"),
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_deliveries_attempts_non_negative")),
        sa.CheckConstraint(
            "eta_min_minutes >= 0 AND eta_max_minutes >= eta_min_minutes", name=op.f("ck_deliveries_eta_valid")
        ),
        sa.ForeignKeyConstraint(
            ["customer_user_id"], ["users.id"], name=op.f("fk_deliveries_customer_user_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["merchant_id"], ["merchants.id"], name=op.f("fk_deliveries_merchant_id_merchants"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["merchant_order_id"],
            ["merchant_orders.id"],
            name=op.f("fk_deliveries_merchant_order_id_merchant_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_deliveries_order_id_orders"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["pickup_location_id"],
            ["merchant_addresses.id"],
            name=op.f("fk_deliveries_pickup_location_id_merchant_addresses"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name=op.f("fk_deliveries_store_id_stores"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"], ["delivery_zones.id"], name=op.f("fk_deliveries_zone_id_delivery_zones"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deliveries")),
        sa.UniqueConstraint("merchant_order_id", name=op.f("uq_deliveries_merchant_order_id")),
    )
    op.create_index(op.f("ix_deliveries_customer_user_id"), "deliveries", ["customer_user_id"], unique=False)
    op.create_index(op.f("ix_deliveries_merchant_id"), "deliveries", ["merchant_id"], unique=False)
    op.create_index(op.f("ix_deliveries_order_id"), "deliveries", ["order_id"], unique=False)
    op.create_index(op.f("ix_deliveries_status"), "deliveries", ["status"], unique=False)

    op.create_table(
        "delivery_events",
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("delivery_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name=op.f("fk_delivery_events_actor_user_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["delivery_id"], ["deliveries.id"], name=op.f("fk_delivery_events_delivery_id_deliveries"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_events")),
    )
    op.create_index(op.f("ix_delivery_events_delivery_id"), "delivery_events", ["delivery_id"], unique=False)
    # The delivery timeline is append-only, like the ledger and audit log.
    op.execute(
        "CREATE TRIGGER delivery_events_immutable BEFORE UPDATE OR DELETE ON delivery_events "
        "FOR EACH ROW EXECUTE FUNCTION forbid_mutation();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS delivery_events_immutable ON delivery_events;")
    op.drop_index(op.f("ix_delivery_events_delivery_id"), table_name="delivery_events")
    op.drop_table("delivery_events")
    for index in ("status", "order_id", "merchant_id", "customer_user_id"):
        op.drop_index(op.f(f"ix_deliveries_{index}"), table_name="deliveries")
    op.drop_table("deliveries")

    op.drop_constraint(op.f("ck_ledger_entries_component_valid"), "ledger_entries", type_="check")
    op.drop_column("ledger_entries", "component")
    op.drop_constraint(op.f("ck_chargebacks_delivery_portions_valid"), "chargebacks", type_="check")
    op.drop_column("chargebacks", "delivery_platform_portion")
    op.drop_column("chargebacks", "delivery_portion")
    op.drop_constraint(op.f("ck_refunds_delivery_portions_valid"), "refunds", type_="check")
    op.drop_constraint(op.f("ck_refunds_scope_valid"), "refunds", type_="check")
    op.drop_column("refunds", "delivery_platform_portion")
    op.drop_column("refunds", "delivery_portion")
    op.drop_column("refunds", "scope")
    op.drop_constraint(op.f("ck_payment_allocations_delivery_amount_range"), "payment_allocations", type_="check")
    op.drop_column("payment_allocations", "delivery_amount")

    op.drop_constraint(op.f("ck_commission_transactions_delivery_amounts_valid"), "commission_transactions", type_="check")
    op.drop_constraint(op.f("ck_commission_transactions_net_consistent"), "commission_transactions", type_="check")
    for column in ("platform_delivery_amount", "delivery_commission_amount", "delivery_commission_rate", "delivery_fee"):
        op.drop_column("commission_transactions", column)
    op.create_check_constraint(
        op.f("ck_commission_transactions_net_consistent"),
        "commission_transactions",
        "seller_net_amount = gross_amount - commission_amount"
        " - CASE WHEN fee_bearer = 'MERCHANT' THEN COALESCE(processing_fee, 0) ELSE 0 END",
    )

    for name in (
        "delivery_commission_merchant_only",
        "delivery_fee_requires_delivery",
        "delivery_terms_recorded",
        "delivery_method_valid",
        "net_consistent",
        "commission_range",
        "total_consistent",
        "amounts_non_negative",
    ):
        op.drop_constraint(op.f(f"ck_merchant_orders_{name}"), "merchant_orders", type_="check")
    for column in (
        "delivery_commission_rate",
        "delivery_commission",
        "delivery_cost_bearer",
        "delivery_fee_recipient",
        "delivery_vat",
        "delivery_fee_waived",
        "delivery_method",
    ):
        op.drop_column("merchant_orders", column)
    op.alter_column("merchant_orders", "delivery_fee", new_column_name="shipping_total")
    op.create_check_constraint(
        op.f("ck_merchant_orders_amounts_non_negative"),
        "merchant_orders",
        "items_subtotal >= 0 AND discount_total >= 0 AND shipping_total >= 0 AND vat_total >= 0",
    )
    op.create_check_constraint(
        op.f("ck_merchant_orders_total_consistent"),
        "merchant_orders",
        "total = items_subtotal - discount_total + shipping_total + vat_total",
    )
    op.create_check_constraint(
        op.f("ck_merchant_orders_commission_range"), "merchant_orders", "commission_total >= 0 AND commission_total <= total"
    )
    op.create_check_constraint(
        op.f("ck_merchant_orders_net_consistent"), "merchant_orders", "merchant_net = total - commission_total"
    )

    op.drop_constraint(op.f("ck_orders_total_consistent"), "orders", type_="check")
    op.alter_column("orders", "delivery_total", new_column_name="shipping_total")
    op.alter_column("orders", "delivery_address", new_column_name="shipping_address")
    op.create_check_constraint(
        op.f("ck_orders_total_consistent"), "orders", "total = items_subtotal - discount_total + shipping_total + vat_total"
    )

    op.drop_constraint(op.f("ck_customer_addresses_pin"), "customer_addresses", type_="check")
    for column in ("delivery_instructions", "longitude", "latitude"):
        op.drop_column("customer_addresses", column)

    op.add_column("stores", sa.Column("shipping_fee", sa.BigInteger(), server_default="0", nullable=False))
    op.add_column("stores", sa.Column("free_shipping_threshold", sa.BigInteger(), nullable=True))
    op.execute(
        """
        UPDATE stores s SET shipping_fee = z.fee, free_shipping_threshold = z.free_delivery_threshold
          FROM (SELECT DISTINCT ON (store_id) store_id, fee, free_delivery_threshold
                  FROM delivery_zones WHERE is_active ORDER BY store_id, region NULLS FIRST, created_at) z
         WHERE z.store_id = s.id
        """
    )
    op.create_check_constraint(op.f("ck_stores_shipping_fee_non_negative"), "stores", "shipping_fee >= 0")
    op.drop_index(op.f("ix_store_delivery_settings_merchant_id"), table_name="store_delivery_settings")
    op.drop_table("store_delivery_settings")
    op.drop_index(op.f("ix_delivery_zones_store_id"), table_name="delivery_zones")
    op.drop_index(op.f("ix_delivery_zones_merchant_id"), table_name="delivery_zones")
    op.drop_table("delivery_zones")
