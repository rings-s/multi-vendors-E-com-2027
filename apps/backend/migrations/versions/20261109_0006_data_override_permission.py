"""Permission to override append-only tables from the data admin.

``admin.data.override_immutable`` (SUPER_ADMIN only) allows changing or deleting rows of
append-only tables (ledger, audit log, merchant verifications, delivery events) through
``/admin/data``. Each override needs a reason, is audited, and lifts the table's
immutability trigger for that single statement only.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-09
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CODE = "admin.data.override_immutable"


def upgrade() -> None:
    conn = op.get_bind()
    perm_id = uuid.uuid4()
    conn.execute(
        sa.text("INSERT INTO permissions (id, code, description) VALUES (:id, :code, :code)"),
        {"id": perm_id, "code": CODE},
    )
    conn.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT id, :perm FROM roles WHERE name = 'SUPER_ADMIN'"
        ),
        {"perm": perm_id},
    )


def downgrade() -> None:
    op.execute(sa.text(f"DELETE FROM permissions WHERE code = '{CODE}'"))
