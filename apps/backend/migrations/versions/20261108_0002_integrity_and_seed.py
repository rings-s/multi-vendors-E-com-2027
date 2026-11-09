"""Immutability triggers for financial/audit records and reference seed data.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-08
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IMMUTABLE_TABLES = ("ledger_entries", "ledger_transactions", "audit_logs", "merchant_verifications")

ROLES = ("CUSTOMER", "MERCHANT", "ADMIN", "SUPER_ADMIN")
PERMISSIONS = (
    "admin.merchants.view",
    "admin.merchants.manage",
    "admin.customers.view",
    "admin.customers.manage",
    "admin.catalog.moderate",
    "admin.categories.manage",
    "admin.orders.view",
    "admin.orders.manage",
    "admin.payments.view",
    "admin.refunds.manage",
    "admin.disputes.manage",
    "admin.reconciliation.run",
    "admin.settlements.view",
    "admin.settlements.reconcile",
    "admin.commissions.view",
    "admin.commissions.manage",
    "admin.settings.view",
    "admin.settings.manage",
    "admin.audit.view",
    "admin.support.manage",
    "admin.users.roles.manage",
)
SUPER_ADMIN_ONLY = {
    "admin.commissions.manage",
    "admin.settings.manage",
    "admin.settlements.reconcile",
    "admin.users.roles.manage",
}


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Records in % are immutable; post a reversing entry instead.', TG_TABLE_NAME
                USING ERRCODE = 'restrict_violation';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in IMMUTABLE_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION forbid_mutation();"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION forbid_mutation();"
        )

    # Every ledger transaction must balance (sum of debits = sum of credits).
    # Checked at commit time so all entries of a transaction can be inserted first.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_ledger_balanced() RETURNS trigger AS $$
        DECLARE
            imbalance BIGINT;
        BEGIN
            SELECT COALESCE(SUM(CASE WHEN direction = 'DEBIT' THEN amount ELSE -amount END), 0)
              INTO imbalance
              FROM ledger_entries WHERE transaction_id = NEW.transaction_id;
            IF imbalance <> 0 THEN
                RAISE EXCEPTION 'Ledger transaction % is not balanced (%).', NEW.transaction_id, imbalance;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER ledger_entries_balanced AFTER INSERT ON ledger_entries "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_ledger_balanced();"
    )

    roles = sa.table("roles", sa.column("id", sa.Uuid), sa.column("name", sa.String))
    permissions = sa.table(
        "permissions", sa.column("id", sa.Uuid), sa.column("code", sa.String), sa.column("description", sa.String)
    )
    role_permissions = sa.table("role_permissions", sa.column("role_id", sa.Uuid), sa.column("permission_id", sa.Uuid))
    role_ids = {name: uuid.uuid4() for name in ROLES}
    perm_ids = {code: uuid.uuid4() for code in PERMISSIONS}
    op.bulk_insert(roles, [{"id": rid, "name": name} for name, rid in role_ids.items()])
    op.bulk_insert(permissions, [{"id": pid, "code": code, "description": code} for code, pid in perm_ids.items()])
    links = [{"role_id": role_ids["SUPER_ADMIN"], "permission_id": pid} for pid in perm_ids.values()]
    links += [
        {"role_id": role_ids["ADMIN"], "permission_id": pid}
        for code, pid in perm_ids.items()
        if code not in SUPER_ADMIN_ONLY
    ]
    op.bulk_insert(role_permissions, links)

    rules = sa.table(
        "commission_rules",
        sa.column("id", sa.Uuid),
        sa.column("scope", sa.String),
        sa.column("rate_type", sa.String),
        sa.column("rate", sa.Numeric),
        sa.column("effective_from", sa.DateTime(timezone=True)),
        sa.column("note", sa.String),
    )
    op.bulk_insert(
        rules,
        [
            {
                "id": uuid.uuid4(),
                "scope": "GLOBAL",
                "rate_type": "PERCENTAGE",
                "rate": 10,
                "effective_from": datetime(2026, 1, 1, tzinfo=UTC),
                "note": "Initial global commission",
            }
        ],
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ledger_entries_balanced ON ledger_entries;")
    op.execute("DROP FUNCTION IF EXISTS check_ledger_balanced();")
    for table in IMMUTABLE_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS {table}_no_truncate ON {table};")
    op.execute("DROP FUNCTION IF EXISTS forbid_mutation();")
    op.execute("DELETE FROM commission_rules;")
    op.execute("DELETE FROM role_permissions;")
    op.execute("DELETE FROM permissions;")
    op.execute("DELETE FROM roles;")
