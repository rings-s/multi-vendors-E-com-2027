"""SQLModel metadata, UUID primary keys and timezone-aware timestamps.

Every table model is a ``SQLModel`` subclass declared with ``table=True``; the shared
columns below are plain (non-table) SQLModel mixins. Database-level constraints and
PostgreSQL-specific types that SQLModel does not model itself (check constraints,
partial indexes, JSONB) are passed through ``__table_args__`` and ``sa_type``.
"""

import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel, func

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Constraint names in the migrations follow this convention; it must be set before
# any table model is declared.
SQLModel.metadata.naming_convention = NAMING_CONVENTION


def _now() -> datetime:
    return datetime.now(UTC)


class UUIDPrimaryKey(SQLModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


# Timestamps are set in Python (and also have a server default for raw SQL inserts):
# server-generated values are expired after a flush and would trigger implicit IO
# on attribute access, which is not allowed with the async session.
class CreatedAt(SQLModel):
    created_at: datetime = Field(default_factory=_now, sa_column_kwargs={"server_default": func.now()})


class Timestamps(CreatedAt):
    updated_at: datetime = Field(
        default_factory=_now, sa_column_kwargs={"server_default": func.now(), "onupdate": _now}
    )
