"""Permissions for the generic data admin.

* ``admin.data.view``: browse every table (ADMIN and SUPER_ADMIN).
* ``admin.data.manage``: create, change and delete raw records (SUPER_ADMIN only).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-09
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GRANTS = {
    "admin.data.view": ("ADMIN", "SUPER_ADMIN"),
    "admin.data.manage": ("SUPER_ADMIN",),
}


def upgrade() -> None:
    conn = op.get_bind()
    roles = dict(conn.execute(sa.text("SELECT name, id FROM roles")).all())
    for code, role_names in GRANTS.items():
        perm_id = uuid.uuid4()
        conn.execute(
            sa.text("INSERT INTO permissions (id, code, description) VALUES (:id, :code, :code)"),
            {"id": perm_id, "code": code},
        )
        for name in role_names:
            if name in roles:
                conn.execute(
                    sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role, :perm)"),
                    {"role": roles[name], "perm": perm_id},
                )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM permissions WHERE code IN ('admin.data.view', 'admin.data.manage')"))
